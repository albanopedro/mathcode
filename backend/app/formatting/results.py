"""Outcome of each intent -> the ``result`` and ``details`` of a MathResult."""

from dataclasses import dataclass
from fractions import Fraction
from typing import Any

import sympy as sp

from app.formatting.expressions import approx, latex, plain
from app.math_engine.algebra import DivisionOutcome, PrimeFactorization, RewriteOutcome
from app.math_engine.arithmetic import ArithmeticOutcome
from app.math_engine.calculus import (
    DerivativeOutcome,
    IntegralOutcome,
    LimitKind,
    LimitOutcome,
    show_value,
)
from app.math_engine.equations import EquationOutcome, SolutionKind
from app.math_engine.graphing import GraphOutcome
from app.math_engine.statistics import StatisticsOutcome, rational
from app.math_engine.systems import SystemKind, SystemOutcome
from app.models.intents import Measure
from app.models.result import ResultValue

_EMPTY = ResultValue(plain="∅", latex=r"\varnothing")


@dataclass(frozen=True)
class Presentation:
    result: ResultValue
    details: dict[str, Any]


def present_arithmetic(outcome: ArithmeticOutcome) -> Presentation:
    value = outcome.value
    return Presentation(
        ResultValue(plain=plain(value), latex=latex(value), approx=approx(value)), {}
    )


def present_rewrite(outcome: RewriteOutcome) -> Presentation:
    result = outcome.result
    return Presentation(
        ResultValue(plain=plain(result), latex=latex(result), approx=approx(result)),
        {"changed": outcome.changed},
    )


def present_factor(outcome: RewriteOutcome | PrimeFactorization) -> Presentation:
    if isinstance(outcome, RewriteOutcome):
        return present_rewrite(outcome)
    sign = "-" if outcome.number < 0 else ""
    as_plain = [f"{p}^{e}" if e > 1 else str(p) for p, e in outcome.factors]
    as_latex = [f"{p}^{{{e}}}" if e > 1 else str(p) for p, e in outcome.factors]
    return Presentation(
        ResultValue(plain=sign + " * ".join(as_plain), latex=sign + r" \cdot ".join(as_latex)),
        {
            "number": str(outcome.number),
            "prime_factors": [{"prime": str(p), "exponent": e} for p, e in outcome.factors],
        },
    )


# -- equations ----------------------------------------------------------------------------


def _is_exact_form(value: sp.Expr) -> bool:
    """False for roots that have no simple radical form (shown approximately)."""
    return not value.has(sp.CRootOf)


def _short(value: sp.Expr) -> str:
    return str(approx(value) or plain(value))


def present_equation(outcome: EquationOutcome) -> Presentation:
    var, name = outcome.variable, outcome.variable.name
    details: dict[str, Any] = {
        "variable": name,
        "solution_set": outcome.kind.value,
        "solutions": [plain(s) for s in outcome.solutions],
    }
    if outcome.multiplicities:
        details["multiplicities"] = list(outcome.multiplicities)
    if outcome.excluded:
        details["excluded"] = [plain(e) for e in outcome.excluded]

    match outcome.kind:
        case SolutionKind.FINITE:
            plains, latexes = [], []
            # One root per line (x_1, x_2...): a single line of roots would not
            # fit a phone screen.
            several = len(outcome.solutions) > 1
            for index, s in enumerate(outcome.solutions, start=1):
                lhs = f"{latex(var)}_{{{index}}} &" if several else latex(var)
                if _is_exact_form(s):
                    plains.append(f"{name} = {plain(s)}")
                    latexes.append(f"{lhs} = {latex(s)}")
                else:
                    plains.append(f"{name} ≈ {_short(s)}")
                    latexes.append(rf"{lhs} \approx {sp.N(s, 10)}")
            approximations = [approx(s) for s in outcome.solutions]
            joined = r" \\ ".join(latexes)
            value = ResultValue(
                plain=" ou ".join(plains),
                latex=rf"\begin{{aligned}} {joined} \end{{aligned}}" if several else joined,
                approx="; ".join(_short(s) for s in outcome.solutions)
                if any(approximations)
                else None,
            )
        case SolutionKind.NONE:
            value = _EMPTY
        case SolutionKind.ALL_REALS:
            if outcome.excluded:
                listed = ", ".join(plain(e) for e in outcome.excluded)
                set_latex = ", ".join(latex(e) for e in outcome.excluded)
                value = ResultValue(
                    plain=f"{name} ∈ ℝ, {name} ≠ {listed}",
                    latex=rf"{latex(var)} \in \mathbb{{R}} \setminus \{{{set_latex}\}}",
                )
            else:
                value = ResultValue(plain=f"{name} ∈ ℝ", latex=rf"{latex(var)} \in \mathbb{{R}}")
    return Presentation(value, details)


# -- systems -----------------------------------------------------------------------------


def present_system(outcome: SystemOutcome) -> Presentation:
    details: dict[str, Any] = {
        "variables": [v.name for v in outcome.variables],
        "solution_set": outcome.kind.value,
        "free_variables": [v.name for v in outcome.free],
    }
    if outcome.kind is SystemKind.NONE or outcome.solution is None:
        details["solutions"] = {}
        return Presentation(_EMPTY, details)

    pairs = list(zip(outcome.variables, outcome.solution, strict=True))
    details["solutions"] = {var.name: plain(value) for var, value in pairs}
    plains, latexes = [], []
    for var, value in pairs:
        if var in outcome.free:
            plains.append(f"{var.name} ∈ ℝ")
            latexes.append(rf"{latex(var)} \in \mathbb{{R}}")
        else:
            plains.append(f"{var.name} = {plain(value)}")
            latexes.append(f"{latex(var)} = {latex(value)}")

    approx_text = None
    if outcome.kind is SystemKind.UNIQUE and any(approx(value) for _, value in pairs):
        approx_text = "; ".join(f"{var.name} = {_short(value)}" for var, value in pairs)
    return Presentation(
        ResultValue(
            plain="; ".join(plains),
            latex=r"\begin{cases} " + r" \\ ".join(latexes) + r" \end{cases}",
            approx=approx_text,
        ),
        details,
    )


# -- polynomial division --------------------------------------------------------------------


def present_division(outcome: DivisionOutcome) -> Presentation:
    var = outcome.variable
    q, r = outcome.quotient, outcome.remainder
    return Presentation(
        ResultValue(
            plain=f"quociente: {plain(q)}; resto: {plain(r)}",
            latex=rf"Q({latex(var)}) = {latex(q)}, \quad R({latex(var)}) = {latex(r)}",
        ),
        {
            "variable": var.name,
            "quotient": plain(q),
            "remainder": plain(r),
            "exact": r == 0,
        },
    )


# -- calculus -------------------------------------------------------------------------------


def _value(value: sp.Expr) -> ResultValue:
    """A number or ±∞, with its decimal approximation when useful."""
    if value in (sp.oo, -sp.oo):
        return ResultValue(plain=show_value(value), latex=latex(value))
    return ResultValue(plain=plain(value), latex=latex(value), approx=approx(value))


def present_derivative(outcome: DerivativeOutcome) -> Presentation:
    result = outcome.result
    return Presentation(
        ResultValue(plain=plain(result), latex=latex(result), approx=approx(result)),
        {"variable": outcome.variable.name, "order": outcome.order},
    )


def present_integral(outcome: IntegralOutcome) -> Presentation:
    details: dict[str, Any] = {"variable": outcome.variable.name, "definite": outcome.definite}
    if not outcome.definite or outcome.value is None:
        antiderivative = outcome.antiderivative
        if antiderivative is None:
            raise AssertionError("an indefinite integral has an antiderivative")
        return Presentation(
            ResultValue(plain=f"{plain(antiderivative)} + C", latex=f"{latex(antiderivative)} + C"),
            details,
        )
    if outcome.lower is None or outcome.upper is None:
        raise AssertionError("a definite integral has bounds")
    details |= {
        "lower": show_value(outcome.lower),
        "upper": show_value(outcome.upper),
        "converges": outcome.converges,
    }
    return Presentation(_value(outcome.value), details)


def present_limit(outcome: LimitOutcome) -> Presentation:
    details: dict[str, Any] = {
        "variable": outcome.variable.name,
        "point": show_value(outcome.point),
        "side": outcome.side,
        "requested_side": outcome.requested_side,
        "exists": outcome.kind is not LimitKind.NONEXISTENT,
        "oscillates": outcome.oscillates,
    }
    if outcome.left is not None and outcome.right is not None:
        details |= {"left": show_value(outcome.left), "right": show_value(outcome.right)}
    if outcome.kind is LimitKind.NONEXISTENT or outcome.value is None:
        return Presentation(ResultValue(plain="não existe", latex=r"\nexists"), details)
    return Presentation(_value(outcome.value), details)


# -- graphs -----------------------------------------------------------------------------------


def present_graph(outcome: GraphOutcome) -> Presentation:
    functions = outcome.functions
    if len(functions) == 1:
        latex_text = f"y = {latex(functions[0].expr)}"
    else:
        lines = [f"y_{{{i}}} &= {latex(f.expr)}" for i, f in enumerate(functions, start=1)]
        latex_text = r"\begin{aligned} " + r" \\ ".join(lines) + r" \end{aligned}"
    details: dict[str, Any] = {
        "variable": outcome.variable.name,
        "x_range": [float(sp.N(outcome.x_min, 15)), float(sp.N(outcome.x_max, 15))],
        "x_range_text": list(outcome.x_range_text),
        "y_range": list(outcome.y_range),
        "y_clipped": outcome.y_clipped,
        "functions": [
            {"label": f.label, "latex": latex(f.expr), "x": list(f.xs), "y": list(f.ys)}
            for f in functions
        ],
        "points": [
            {
                "function": p.function,
                "kind": p.kind,
                "x": plain(p.x) if p.x is not None else _short_float(p.x_value),
                "y": plain(p.y) if p.y is not None else _short_float(p.y_value),
                "x_value": p.x_value,
                "y_value": p.y_value,
                "exact": p.exact,
            }
            for p in outcome.points
        ],
    }
    return Presentation(
        ResultValue(plain="; ".join(f"y = {f.label}" for f in functions), latex=latex_text),
        details,
    )


def _short_float(value: float) -> str:
    return f"{value:.10g}"


# -- statistics (Phase 10) ---------------------------------------------------------------------

# measure -> (label, LaTeX symbol, plain name)
_MEASURES: dict[Measure, tuple[str, str, str]] = {
    "count": ("Quantidade de valores", "n", "n"),
    "sum": ("Soma", r"\sum x", "soma"),
    "mean": ("Média", r"\bar{x}", "média"),
    "median": ("Mediana", r"\mathrm{Md}", "mediana"),
    "mode": ("Moda", r"\mathrm{Mo}", "moda"),
    "min": ("Mínimo", r"\min", "mínimo"),
    "max": ("Máximo", r"\max", "máximo"),
    "range": ("Amplitude", r"\mathrm{A}", "amplitude"),
    "variance": ("Variância populacional", r"\sigma^{2}", "σ²"),
    "std": ("Desvio padrão populacional", r"\sigma", "σ"),
    "sample_variance": ("Variância amostral", r"s^{2}", "s²"),
    "sample_std": ("Desvio padrão amostral", "s", "s"),
}


def _statistics_value(outcome: StatisticsOutcome, measure: Measure) -> sp.Expr | None:
    values: dict[Measure, sp.Expr | None] = {
        "count": sp.Integer(outcome.count),
        "sum": rational(outcome.total),
        "mean": rational(outcome.mean),
        "median": rational(outcome.median),
        "min": rational(outcome.minimum),
        "max": rational(outcome.maximum),
        "range": rational(outcome.spread),
        "variance": rational(outcome.variance),
        "std": outcome.std,
        "sample_variance": (
            None if outcome.sample_variance is None else rational(outcome.sample_variance)
        ),
        "sample_std": outcome.sample_std,
    }
    return values[measure]


def _statistics_entry(outcome: StatisticsOutcome, measure: Measure) -> dict[str, Any]:
    label, symbol, _ = _MEASURES[measure]
    entry: dict[str, Any] = {"name": measure, "label": label, "symbol": symbol}
    if measure == "mode":
        modes = [rational(m) for m in outcome.modes]
        if not modes:
            return entry | {"plain": "nenhuma", "latex": r"\text{nenhuma}", "approx": None}
        return entry | {
            "plain": "; ".join(plain(m) for m in modes),
            "latex": r";\ ".join(latex(m) for m in modes),
            "approx": None,
        }
    value = _statistics_value(outcome, measure)
    if value is None:
        return entry | {"plain": None, "latex": None, "approx": None}
    return entry | {"plain": plain(value), "latex": latex(value), "approx": approx(value)}


def _data_text(value: Fraction) -> str:
    """A value of the data as typed: 9.5, not 19/2, when the decimal is finite."""
    rest, twos, fives = value.denominator, 0, 0
    while rest % 2 == 0:
        rest, twos = rest // 2, twos + 1
    while rest % 5 == 0:
        rest, fives = rest // 5, fives + 1
    places = max(twos, fives)
    if rest != 1 or places == 0:
        return str(value)  # 1/3, or an integer
    digits = str(abs(value.numerator) * 10**places // value.denominator).rjust(places + 1, "0")
    sign = "-" if value < 0 else ""
    return f"{sign}{digits[:-places]}.{digits[-places:]}"


def present_statistics(outcome: StatisticsOutcome) -> Presentation:
    measures = [_statistics_entry(outcome, measure) for measure in _MEASURES]
    shown = outcome.measure or "mean"
    entry = next(m for m in measures if m["name"] == shown)
    _, symbol, name = _MEASURES[shown]
    if shown == "mode" and not outcome.modes:
        result = ResultValue(
            plain="moda: nenhuma (nenhum valor se repete)",
            latex=r"\text{Sem moda: nenhum valor se repete}",
        )
    else:
        result = ResultValue(
            plain=f"{name} = {entry['plain']}",
            latex=f"{symbol} = {entry['latex']}",
            approx=entry["approx"],
        )
    return Presentation(
        result,
        {
            "measure": outcome.measure,
            "count": outcome.count,
            "data": [_data_text(v) for v in outcome.values],
            "sorted": [_data_text(v) for v in sorted(outcome.values)],
            "modes": [_data_text(m) for m in outcome.modes],
            "measures": measures,
        },
    )

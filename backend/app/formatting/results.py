"""Outcome of each intent -> the ``result`` and ``details`` of a MathResult."""

import math
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
from app.math_engine.geometry import Classification, GeometryOutcome, Line
from app.math_engine.graphing import GraphOutcome
from app.math_engine.matrices import MatrixOutcome, VectorValue
from app.math_engine.probability import BinomialSummary, ProbabilityOutcome
from app.math_engine.statistics import StatisticsOutcome, rational
from app.math_engine.systems import SystemKind, SystemOutcome
from app.math_engine.vectors import VectorOutcome
from app.models.intents import Measure
from app.models.result import ResultValue
from app.parsing.build import symbol

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


# -- matrices (Phase 10) -----------------------------------------------------------------------


def _matrix_plain(matrix: sp.MatrixBase) -> str:
    rows = (", ".join(plain(matrix[i, j]) for j in range(matrix.cols)) for i in range(matrix.rows))
    return "[" + ", ".join(f"[{row}]" for row in rows) + "]"


def _matrix_approx(matrix: sp.MatrixBase) -> str | None:
    if all(entry.is_Rational for entry in matrix):
        return None
    rows = (
        ", ".join(approx(matrix[i, j]) or plain(matrix[i, j]) for j in range(matrix.cols))
        for i in range(matrix.rows)
    )
    return "[" + ", ".join(f"[{row}]" for row in rows) + "]"


# operation -> (plain prefix, LaTeX prefix); None: the matrix alone
_MATRIX_PREFIX: dict[str, tuple[str, str] | None] = {
    "evaluate": None,
    "determinant": ("det = ", r"\det(A) = "),
    "inverse": ("A⁻¹ = ", r"A^{-1} = "),
    "transpose": ("Aᵀ = ", r"A^{T} = "),
    "trace": ("traço = ", r"\operatorname{tr}(A) = "),
    "rank": ("posto = ", r"\operatorname{posto}(A) = "),
}


def vector_plain(vector: VectorValue) -> str:
    return "[" + ", ".join(plain(entry) for entry in vector.entries) + "]"


def vector_latex(vector: VectorValue) -> str:
    return r"\left(" + r",\ ".join(latex(entry) for entry in vector.entries) + r"\right)"


def vector_approx(vector: VectorValue) -> str | None:
    if all(entry.is_Rational for entry in vector.entries):
        return None
    return "[" + ", ".join(approx(e) or plain(e) for e in vector.entries) + "]"


def present_matrices(outcome: MatrixOutcome) -> Presentation:
    result = outcome.result
    if isinstance(result, VectorValue):  # A·v
        body_plain, body_latex, body_approx = (
            vector_plain(result),
            vector_latex(result),
            vector_approx(result),
        )
    elif isinstance(result, sp.MatrixBase):
        body_plain, body_latex, body_approx = (
            _matrix_plain(result),
            latex(result),
            _matrix_approx(result),
        )
    else:
        body_plain, body_latex, body_approx = plain(result), latex(result), approx(result)
    prefix = _MATRIX_PREFIX[outcome.operation]
    plain_prefix, latex_prefix = prefix if prefix is not None else ("", "")
    operand = outcome.operand
    if isinstance(operand, VectorValue):
        return Presentation(
            ResultValue(plain=body_plain, latex=body_latex, approx=body_approx),
            {
                "operation": outcome.operation,
                "rows": operand.size,
                "cols": 1,
                "matrix": vector_plain(operand),
                "matrix_latex": vector_latex(operand),
            },
        )
    return Presentation(
        ResultValue(
            plain=plain_prefix + body_plain, latex=latex_prefix + body_latex, approx=body_approx
        ),
        {
            "operation": outcome.operation,
            "rows": operand.rows,
            "cols": operand.cols,
            "matrix": _matrix_plain(operand),
            "matrix_latex": latex(operand),
        },
    )


# -- vectors (Phase 10) ------------------------------------------------------------------------

# operation -> (plain prefix, LaTeX prefix)
_VECTOR_PREFIX: dict[str, tuple[str, str]] = {
    "evaluate": ("", ""),
    "norm": ("‖u‖ = ", r"\lVert u \rVert = "),
    "unit": ("û = ", r"\hat{u} = "),
    "dot": ("u·v = ", r"u \cdot v = "),
    "cross": ("u×v = ", r"u \times v = "),
    "angle": ("θ = ", r"\theta = "),
}


def present_vectors(outcome: VectorOutcome) -> Presentation:
    result = outcome.result
    plain_prefix, latex_prefix = _VECTOR_PREFIX[outcome.operation]
    details: dict[str, Any] = {
        "operation": outcome.operation,
        "dimension": outcome.vectors[0].size,
        "vectors": [vector_plain(v) for v in outcome.vectors],
        "vectors_latex": [vector_latex(v) for v in outcome.vectors],
    }
    if isinstance(result, VectorValue):
        value = ResultValue(
            plain=plain_prefix + vector_plain(result),
            latex=latex_prefix + vector_latex(result),
            approx=vector_approx(result),
        )
        return Presentation(value, details)
    if outcome.operation != "angle":
        value = ResultValue(
            plain=plain_prefix + plain(result),
            latex=latex_prefix + latex(result),
            approx=approx(result),
        )
        return Presentation(value, details)

    # The angle: exact radians and degrees (ADR 0013). The headline keeps 6 significant
    # digits of the degrees; ``details`` has all of them.
    degrees = sp.simplify(result * 180 / sp.pi)
    exact_degrees = degrees.is_Rational
    radians_approx = approx(result)
    details |= {
        "degrees": plain(degrees) if exact_degrees else None,
        "degrees_approx": approx(degrees) or plain(degrees),
    }
    if exact_degrees:
        value = ResultValue(
            plain=f"θ = {plain(result)} rad = {plain(degrees)}°",
            latex=rf"\theta = {latex(result)} = {latex(degrees)}^\circ",
            approx=f"{radians_approx} rad" if radians_approx else None,
        )
    else:
        shown = str(sp.N(degrees, 6))
        value = ResultValue(
            plain=f"θ = {plain(result)} rad ≈ {shown}°",
            latex=rf"\theta = {latex(result)} \approx {shown}^\circ",
            approx=f"{radians_approx} rad" if radians_approx else None,
        )
    return Presentation(value, details)


# -- geometry (Phase 10) -----------------------------------------------------------------------

_QUANTITY: dict[str, str] = {
    "area": "area",
    "surface_area": "area",
    "polygon_area": "area",
    "perimeter": "length",
    "missing_side": "length",
    "distance": "length",
    "volume": "volume",
}


def _point_plain(point: tuple[sp.Expr, ...]) -> str:
    return "(" + ", ".join(plain(c) for c in point) + ")"


def _point_latex(point: tuple[sp.Expr, ...]) -> str:
    return r"\left(" + ", ".join(latex(c) for c in point) + r"\right)"


def present_geometry(outcome: GeometryOutcome) -> Presentation:
    result = outcome.result
    details: dict[str, Any] = {
        "figure": outcome.figure,
        "calculation": outcome.calculation,
        "measures": {name: plain(value) for name, value in outcome.measures.items()},
        "points": [_point_plain(point) for point in outcome.points],
        "formula": outcome.formula or None,
        "quantity": _QUANTITY.get(outcome.calculation),
    }
    if isinstance(result, Classification):
        text = f"triângulo {result.by_sides} e {result.by_angles}"
        details |= {"by_sides": result.by_sides, "by_angles": result.by_angles}
        return Presentation(ResultValue(plain=text, latex=rf"\text{{{text}}}"), details)
    if isinstance(result, Line):
        x, y = symbol("x"), symbol("y")
        details["equation"] = f"{plain(result.a * x + result.b * y)} = {plain(result.c)}"
        if result.slope is None:
            value = result.c / result.a
            details["slope"] = None
            shown = ResultValue(plain=f"x = {plain(value)}", latex=f"x = {latex(value)}")
            return Presentation(shown, details)
        line = result.slope * x + (result.intercept or 0)
        details["slope"] = plain(result.slope)
        return Presentation(
            ResultValue(plain=f"y = {plain(line)}", latex=f"y = {latex(line)}"), details
        )
    if isinstance(result, tuple):
        approximate = None
        if not all(c.is_Rational for c in result):
            approximate = "(" + ", ".join(approx(c) or plain(c) for c in result) + ")"
        return Presentation(
            ResultValue(
                plain=f"M = {_point_plain(result)}",
                latex=f"M = {_point_latex(result)}",
                approx=approximate,
            ),
            details,
        )
    return Presentation(
        ResultValue(
            plain=f"{outcome.symbol} = {plain(result)}",
            latex=f"{outcome.symbol} = {latex(result)}",
            approx=approx(result),
        ),
        details,
    )


# -- probability (ADR 0015) -----------------------------------------------------------------------

_LOG10_2 = math.log10(2)
_SUPERSCRIPTS = str.maketrans("0123456789-", "⁰¹²³⁴⁵⁶⁷⁸⁹⁻")
_VALUE_NAMES = {"A": "P(A)", "B": "P(B)", "A∩B": "P(A ∩ B)", "A∪B": "P(A ∪ B)"}


def _with_comma(scaled: int, decimals: int) -> str:
    """The integer ``scaled`` divided by 10^decimals, written with a decimal comma."""
    digits = str(scaled).rjust(decimals + 1, "0")
    if decimals == 0:
        return digits
    return f"{digits[:-decimals]},{digits[-decimals:]}"


def percent(value: sp.Rational) -> tuple[str, bool]:
    """The value in percent, with a decimal comma, and whether it is exact.

    Exact when it has up to 6 decimals ('37,5%', '0,03125%'); otherwise 2
    decimals from 1% up ('16,67%') and 4 significant digits below it
    ('0,01429%', '9,333·10⁻³⁰⁰%').
    """
    hundred = Fraction(int(value.p), int(value.q)) * 100
    for decimals in range(7):
        scaled = hundred * 10**decimals
        if scaled.denominator == 1:
            return _with_comma(scaled.numerator, decimals) + "%", True
    if hundred >= 1:
        rounded = int(hundred * 100 + Fraction(1, 2))  # half up: probabilities are >= 0
        return _with_comma(rounded, 2).rstrip("0").rstrip(",") + "%", False
    # Below 1%: 4 significant digits, from the first one that is not zero.
    # hundred = mantissa·10^-exponent, 1 <= mantissa < 10; first guess from the sizes.
    gap = hundred.denominator.bit_length() - hundred.numerator.bit_length()
    exponent = max(0, int(gap * _LOG10_2) - 1)
    while hundred * 10**exponent < 1:
        exponent += 1
    rounded = int(hundred * 10 ** (exponent + 3) + Fraction(1, 2))
    if rounded == 10_000:  # 9,9996 rounds up to 10
        rounded, exponent = 1000, exponent - 1
    if exponent <= 4:
        return _with_comma(rounded, exponent + 3).rstrip("0").rstrip(",") + "%", False
    mantissa = _with_comma(rounded, 3).rstrip("0").rstrip(",")
    return f"{mantissa}·10{str(-exponent).translate(_SUPERSCRIPTS)}%", False


def present_probability(outcome: ProbabilityOutcome) -> Presentation:
    result = outcome.result
    details: dict[str, Any] = {
        "calculation": outcome.calculation,
        "group": outcome.group,
        "values": {
            _VALUE_NAMES.get(name, name): plain(value) for name, value in outcome.values.items()
        },
        "formula": outcome.formula,
        "percent": None,
        "percent_exact": None,
    }
    if outcome.letters:
        details["letters"] = [
            {"letter": letter, "count": count} for letter, count in outcome.letters
        ]
    if isinstance(result, BinomialSummary):
        # 6 significant digits: the three lines must fit a phone screen.
        short = None if result.std.is_Rational else str(sp.N(result.std, 6))
        std = plain(result.std) if short is None else f"{plain(result.std)} ≈ {short}"
        std_latex = latex(result.std) if short is None else rf"{latex(result.std)} \approx {short}"
        details["summary"] = {
            "mean": plain(result.mean),
            "variance": plain(result.variance),
            "std": plain(result.std),
        }
        return Presentation(
            ResultValue(
                plain=f"μ = {plain(result.mean)}; σ² = {plain(result.variance)}; σ = {std}",
                latex=(
                    rf"\begin{{aligned}} \mu &= {latex(result.mean)} \\ "
                    rf"\sigma^2 &= {latex(result.variance)} \\ "
                    rf"\sigma &= {std_latex} \end{{aligned}}"
                ),
            ),
            details,
        )
    if outcome.group != "counting":
        details["percent"], details["percent_exact"] = percent(result)
    return Presentation(
        ResultValue(
            plain=f"{outcome.plain_symbol} = {plain(result)}",
            latex=f"{outcome.symbol} = {latex(result)}",
        ),
        details,
    )

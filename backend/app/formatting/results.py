"""Outcome of each intent -> the ``result`` and ``details`` of a MathResult."""

from dataclasses import dataclass
from typing import Any

import sympy as sp

from app.formatting.expressions import approx, latex, plain
from app.math_engine.algebra import DivisionOutcome, PrimeFactorization, RewriteOutcome
from app.math_engine.arithmetic import ArithmeticOutcome
from app.math_engine.equations import EquationOutcome, SolutionKind
from app.math_engine.systems import SystemKind, SystemOutcome
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

"""Outcome of each intent -> the ``result`` and ``details`` of a MathResult."""

from dataclasses import dataclass
from typing import Any

from app.formatting.expressions import approx, latex, plain
from app.math_engine.algebra import EquationOutcome, SimplifyOutcome, SolutionKind
from app.math_engine.arithmetic import ArithmeticOutcome
from app.models.result import ResultValue


@dataclass(frozen=True)
class Presentation:
    result: ResultValue
    details: dict[str, Any]


def present_arithmetic(outcome: ArithmeticOutcome) -> Presentation:
    value = outcome.value
    return Presentation(
        ResultValue(plain=plain(value), latex=latex(value), approx=approx(value)), {}
    )


def present_simplify(outcome: SimplifyOutcome) -> Presentation:
    result = outcome.result
    return Presentation(
        ResultValue(plain=plain(result), latex=latex(result), approx=approx(result)), {}
    )


def present_equation(outcome: EquationOutcome) -> Presentation:
    var = outcome.variable
    name = var.name
    details: dict[str, Any] = {"variable": name, "solution_set": outcome.kind.value}
    match outcome.kind:
        case SolutionKind.UNIQUE if outcome.solution is not None:
            solution = outcome.solution
            details["solutions"] = [plain(solution)]
            value = ResultValue(
                plain=f"{name} = {plain(solution)}",
                latex=f"{latex(var)} = {latex(solution)}",
                approx=approx(solution),
            )
        case SolutionKind.NONE:
            details["solutions"] = []
            value = ResultValue(plain="∅", latex=r"\varnothing")
        case _:
            details["solutions"] = []
            value = ResultValue(plain=f"{name} ∈ ℝ", latex=rf"{latex(var)} \in \mathbb{{R}}")
    return Presentation(value, details)

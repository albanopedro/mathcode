"""One entry per intent: input schema, executor, verifier and presenter (architecture, §3).

Adding an intent means writing those four pieces and registering them here;
the pipeline in ``app.calculator`` does not change.
"""

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, Protocol

from pydantic import BaseModel

from app.core.notices import Notice
from app.formatting.results import (
    Presentation,
    present_arithmetic,
    present_derivative,
    present_division,
    present_equation,
    present_factor,
    present_graph,
    present_integral,
    present_limit,
    present_rewrite,
    present_system,
)
from app.math_engine.algebra import divide, expand, factor, simplify
from app.math_engine.arithmetic import evaluate
from app.math_engine.calculus import derivative, integral, limit
from app.math_engine.equations import solve_equation
from app.math_engine.graphing import graph
from app.math_engine.systems import solve_system
from app.models.intents import (
    ArithmeticParams,
    DerivativeParams,
    ExpandParams,
    FactorParams,
    GraphParams,
    IntegralParams,
    IntentName,
    LimitParams,
    PolynomialDivisionParams,
    SimplifyParams,
    SolveEquationParams,
    SolveSystemParams,
)
from app.models.result import VerificationReport
from app.parsing import ParseResult
from app.verification.algebra import verify_division, verify_factor, verify_rewrite
from app.verification.arithmetic import verify_arithmetic
from app.verification.calculus import verify_derivative, verify_integral, verify_limit
from app.verification.equations import verify_equation, verify_system
from app.verification.graphing import verify_graph


class Outcome(Protocol):
    @property
    def parsed(self) -> ParseResult: ...

    @property
    def notices(self) -> tuple[Notice, ...]: ...


@dataclass(frozen=True)
class IntentSpec[P: BaseModel, O: Outcome]:
    name: IntentName
    params_model: type[P]
    execute: Callable[[P], O]
    verify: Callable[[O], VerificationReport]
    present: Callable[[O], Presentation]


REGISTRY: dict[IntentName, IntentSpec[Any, Any]] = {
    spec.name: spec
    for spec in (
        IntentSpec(
            IntentName.ARITHMETIC, ArithmeticParams, evaluate, verify_arithmetic, present_arithmetic
        ),
        IntentSpec(IntentName.SIMPLIFY, SimplifyParams, simplify, verify_rewrite, present_rewrite),
        IntentSpec(IntentName.FACTOR, FactorParams, factor, verify_factor, present_factor),
        IntentSpec(IntentName.EXPAND, ExpandParams, expand, verify_rewrite, present_rewrite),
        IntentSpec(
            IntentName.SOLVE_EQUATION,
            SolveEquationParams,
            solve_equation,
            verify_equation,
            present_equation,
        ),
        IntentSpec(
            IntentName.SOLVE_SYSTEM, SolveSystemParams, solve_system, verify_system, present_system
        ),
        IntentSpec(
            IntentName.POLYNOMIAL_DIVISION,
            PolynomialDivisionParams,
            divide,
            verify_division,
            present_division,
        ),
        IntentSpec(
            IntentName.DERIVATIVE,
            DerivativeParams,
            derivative,
            verify_derivative,
            present_derivative,
        ),
        IntentSpec(
            IntentName.INTEGRAL, IntegralParams, integral, verify_integral, present_integral
        ),
        IntentSpec(IntentName.LIMIT, LimitParams, limit, verify_limit, present_limit),
        IntentSpec(IntentName.GRAPH, GraphParams, graph, verify_graph, present_graph),
    )
}

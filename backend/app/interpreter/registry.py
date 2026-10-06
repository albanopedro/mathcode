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
    present_equation,
    present_simplify,
)
from app.math_engine.algebra import simplify, solve_linear
from app.math_engine.arithmetic import evaluate
from app.models.intents import ArithmeticParams, IntentName, SimplifyParams, SolveEquationParams
from app.models.result import VerificationReport
from app.parsing import ParseResult
from app.verification.algebra import verify_equation, verify_simplify
from app.verification.arithmetic import verify_arithmetic


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
        IntentSpec(
            IntentName.SIMPLIFY, SimplifyParams, simplify, verify_simplify, present_simplify
        ),
        IntentSpec(
            IntentName.SOLVE_EQUATION,
            SolveEquationParams,
            solve_linear,
            verify_equation,
            present_equation,
        ),
    )
}

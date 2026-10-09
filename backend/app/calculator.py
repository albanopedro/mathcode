"""The pipeline: interpret -> execute -> verify -> present (docs/architecture.md, §2).

Phase 2 runs it in-process. Phase 3 moves execution to worker processes with a
timeout (ADR 0002, section 4). Phase 8 adds requests in Portuguese, read by
local rules (``interpreter/language.py``) before the math parser. Phase 9 gives
the verification a time budget: a verification that runs out of time, or breaks,
leaves the result "unverified" instead of losing it (ADR 0010).
"""

import logging
import time
from dataclasses import dataclass
from typing import Any

from app.assistant import ASSISTANT_HELP, compose
from app.core.errors import ErrorCode, MathError
from app.core.limits import MAX_INPUT_LENGTH
from app.core.notices import unique
from app.interpreter.detect import Options, interpret
from app.interpreter.language import match_language
from app.interpreter.planner import plan_request
from app.interpreter.registry import REGISTRY, IntentSpec
from app.models.intents import IntentName
from app.models.result import (
    CheckKind,
    Interpretation,
    MathResult,
    ReasonCode,
    ResultError,
    ResultWarning,
    VerificationReport,
    VerificationStatus,
)
from app.verification.deadline import VerificationTimeout, time_limit
from app.verification.reports import unverified

logger = logging.getLogger(__name__)


@dataclass
class _Context:
    """What is known so far, to build a failure as precise as a success."""

    text: str
    intent: IntentName | None = None
    normalized: str | None = None
    interpretation: Interpretation | None = None
    # Shift from positions in the math text to positions in the request; None
    # when the math text was rewritten and positions would point at nothing.
    offset: int | None = 0


def calculate(
    text: str,
    intent: str | None = None,
    options: Options | None = None,
    verify_until: float | None = None,
) -> MathResult:
    """``verify_until``: a ``time.monotonic()`` instant by which verification must end."""
    context = _Context(text)
    if intent in (None, IntentName.ASSISTANT) and not options:
        compound = _compound(text, intent, verify_until)
        if compound is not None:
            return compound
    try:
        math_text, math_intent, math_options = text, intent, options
        language = match_language(text) if intent is None else None
        if language is not None:
            math_text = language.text
            math_intent = language.intent.value if language.intent else None
            math_options = language.options or None
            context.offset = language.offset
            context.interpretation = Interpretation(
                method="rules", expression=math_text, options=dict(language.options)
            )

        request = interpret(math_text, math_intent, math_options)
        context.intent = request.intent
        if context.interpretation is not None:
            context.interpretation.intent = request.intent

        spec = REGISTRY[request.intent]
        outcome = spec.execute(request.params)
        context.normalized = outcome.parsed.canonical
        verification = _verify(spec, outcome, verify_until)
        if verification.status is VerificationStatus.FAILED:
            return _failure(
                context,
                MathError(
                    ErrorCode.VERIFICATION_FAILED,
                    "A verificação independente não confirmou o resultado, "
                    "por isso ele não é exibido.",
                ),
                verification,
            )
        presentation = spec.present(outcome)
        return MathResult(
            success=True,
            intent=request.intent,
            input=text,
            normalized_input=context.normalized,
            result=presentation.result,
            details=presentation.details,
            verification=verification,
            warnings=[
                ResultWarning(code=n.code, message=n.message) for n in unique(outcome.notices)
            ],
            interpretation=context.interpretation,
        )
    except MathError as exc:
        return _failure(context, exc)
    except Exception:
        logger.exception("unexpected failure while calculating %r", text)
        return _failure(context, MathError(ErrorCode.INTERNAL_ERROR, "Erro interno ao calcular."))


def _compound(text: str, intent: str | None, verify_until: float | None) -> MathResult | None:
    """A compound request, one step after the other (Phase 12, ADR 0021).

    The API runs the steps of a plan in parallel in the pool (``app.assistant.run_plan``);
    this is the same plan in-process, so the pipeline answers it on its own too.
    """
    asked = intent == IntentName.ASSISTANT
    try:
        plan = plan_request(text) if len(text) <= MAX_INPUT_LENGTH else None
    except MathError as error:
        return _assistant_failure(text, error)
    if plan is None:
        if asked:
            message = MathError(ErrorCode.INVALID_INPUT_FOR_INTENT, ASSISTANT_HELP)
            return _assistant_failure(text, message)
        return None
    results = [
        calculate(step.input, step.intent, step.options or None, verify_until)
        for step in plan.steps
    ]
    interpretation = Interpretation(
        method="rules", intent=IntentName.ASSISTANT, expression=plan.function
    )
    return compose(text, plan, results, interpretation)


def _assistant_failure(text: str, error: MathError) -> MathResult:
    return MathResult(
        success=False,
        intent=IntentName.ASSISTANT,
        input=text,
        error=ResultError(code=error.code, message=error.message),
    )


def _verify(spec: IntentSpec[Any, Any], outcome: Any, until: float | None) -> VerificationReport:
    """The intent's verification, within its budget; never lets the result be lost."""
    seconds = None if until is None else until - time.monotonic()
    try:
        with time_limit(seconds):
            return spec.verify(outcome)
    except VerificationTimeout:
        return unverified(
            ReasonCode.DEADLINE,
            CheckKind.EXECUTION,
            "A verificação foi interrompida por exceder o tempo reservado a ela; o resultado "
            "foi calculado, mas não foi conferido.",
        )
    except Exception:
        logger.exception("the verification of %s failed", spec.name)
        return unverified(
            ReasonCode.INTERNAL_ERROR,
            CheckKind.EXECUTION,
            "A verificação encontrou um erro interno; o resultado foi calculado, mas não foi "
            "conferido.",
        )


def _failure(
    context: _Context, error: MathError, verification: VerificationReport | None = None
) -> MathResult:
    position = error.position
    if position is not None:
        position = None if context.offset is None else position + context.offset
    return MathResult(
        success=False,
        intent=context.intent,
        input=context.text,
        normalized_input=context.normalized,
        verification=verification,
        error=ResultError(code=error.code, message=error.message, position=position),
        interpretation=context.interpretation,
    )

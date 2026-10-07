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

from app.core.errors import ErrorCode, MathError
from app.core.notices import unique
from app.interpreter.detect import Options, interpret
from app.interpreter.language import match_language
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

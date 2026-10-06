"""The pipeline: interpret -> execute -> verify -> present (docs/architecture.md, §2).

Phase 2 runs it in-process. Phase 3 moves execution to worker processes with a
timeout (ADR 0002, section 4).
"""

import logging

from app.core.errors import ErrorCode, MathError
from app.core.notices import unique
from app.interpreter.detect import interpret
from app.interpreter.registry import REGISTRY
from app.models.intents import IntentName
from app.models.result import (
    MathResult,
    ResultError,
    ResultWarning,
    VerificationReport,
    VerificationStatus,
)

logger = logging.getLogger(__name__)


def calculate(text: str, intent: str | None = None) -> MathResult:
    name: IntentName | None = None
    normalized: str | None = None
    try:
        request = interpret(text, intent)
        name = request.intent
        spec = REGISTRY[name]
        outcome = spec.execute(request.params)
        normalized = outcome.parsed.canonical
        verification = spec.verify(outcome)
        if verification.status is VerificationStatus.FAILED:
            return _failure(
                text,
                name,
                normalized,
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
            intent=name,
            input=text,
            normalized_input=normalized,
            result=presentation.result,
            details=presentation.details,
            verification=verification,
            warnings=[
                ResultWarning(code=n.code, message=n.message) for n in unique(outcome.notices)
            ],
        )
    except MathError as exc:
        return _failure(text, name, normalized, exc)
    except Exception:
        logger.exception("unexpected failure while calculating %r", text)
        return _failure(
            text,
            name,
            normalized,
            MathError(ErrorCode.INTERNAL_ERROR, "Erro interno ao calcular."),
        )


def _failure(
    text: str,
    intent: IntentName | None,
    normalized: str | None,
    error: MathError,
    verification: VerificationReport | None = None,
) -> MathResult:
    return MathResult(
        success=False,
        intent=intent,
        input=text,
        normalized_input=normalized,
        verification=verification,
        error=ResultError(code=error.code, message=error.message, position=error.position),
    )

"""Building verification reports: checks, status and the message shown (ADR 0010)."""

from mpmath import mpf, nstr

from app.models.result import (
    CheckKind,
    CheckOutcome,
    ReasonCode,
    VerificationCheck,
    VerificationReport,
    VerificationStatus,
)

_MESSAGES = {
    VerificationStatus.VERIFIED_SYMBOLIC: "Resultado verificado simbolicamente.",
    VerificationStatus.VERIFIED_NUMERIC: (
        "Resultado conferido numericamente por um avaliador independente."
    ),
    VerificationStatus.PARTIAL: (
        "Verificação parcial: há evidência a favor do resultado, mas não uma prova "
        "completa. Veja como foi verificado."
    ),
    VerificationStatus.UNVERIFIED: "Não foi possível verificar este resultado.",
    VerificationStatus.NOT_APPLICABLE: "Não há um resultado único a verificar aqui.",
    VerificationStatus.FAILED: "A verificação independente contradiz o resultado.",
}

# Unverified results say why in the headline; the checks give the details.
_UNVERIFIED_MESSAGES = {
    ReasonCode.DEADLINE: (
        "Não foi possível verificar este resultado: a verificação não terminou a tempo."
    ),
    ReasonCode.INTERNAL_ERROR: (
        "Não foi possível verificar este resultado: a verificação encontrou um erro interno."
    ),
    ReasonCode.TOO_LARGE: (
        "Não foi possível verificar este resultado: os números são grandes demais para a "
        "verificação independente."
    ),
}

# -- checks ---------------------------------------------------------------------------------------


def passed(kind: CheckKind, message: str) -> VerificationCheck:
    return VerificationCheck(kind=kind, outcome=CheckOutcome.PASSED, message=message)


def failed(kind: CheckKind, message: str) -> VerificationCheck:
    return VerificationCheck(kind=kind, outcome=CheckOutcome.FAILED, message=message)


def inconclusive(kind: CheckKind, message: str) -> VerificationCheck:
    return VerificationCheck(kind=kind, outcome=CheckOutcome.INCONCLUSIVE, message=message)


# -- reports --------------------------------------------------------------------------------------


def message_for(status: VerificationStatus, reason: ReasonCode | None = None) -> str:
    """The headline the user reads above the checks."""
    if status is VerificationStatus.UNVERIFIED and reason in _UNVERIFIED_MESSAGES:
        return _UNVERIFIED_MESSAGES[reason]
    return _MESSAGES[status]


def report(
    status: VerificationStatus,
    checks: list[VerificationCheck],
    reason: ReasonCode | None = None,
) -> VerificationReport:
    return VerificationReport(
        status=status, checks=checks, message=message_for(status, reason), reason=reason
    )


def failure(kind: CheckKind, message: str, *before: VerificationCheck) -> VerificationReport:
    """The verification contradicts the result: the checks that passed, then the one that failed."""
    return report(VerificationStatus.FAILED, [*before, failed(kind, message)])


def unverified(
    reason: ReasonCode, kind: CheckKind, message: str, *before: VerificationCheck
) -> VerificationReport:
    return report(
        VerificationStatus.UNVERIFIED, [*before, inconclusive(kind, message)], reason=reason
    )


def show(value: mpf) -> str:
    text = nstr(value, 15)
    return text.removesuffix(".0")  # 17, not 17.0

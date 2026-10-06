from mpmath import mpf, nstr

from app.models.result import VerificationReport, VerificationStatus

_MESSAGES = {
    VerificationStatus.VERIFIED_SYMBOLIC: "Resultado verificado simbolicamente.",
    VerificationStatus.VERIFIED_NUMERIC: (
        "Resultado conferido numericamente por um avaliador independente."
    ),
    VerificationStatus.UNVERIFIED: "Não foi possível verificar este resultado.",
    VerificationStatus.FAILED: "A verificação independente contradiz o resultado.",
}


def report(status: VerificationStatus, method: str, checks: list[str]) -> VerificationReport:
    return VerificationReport(
        status=status, method=method, checks=checks, message=_MESSAGES[status]
    )


def show(value: mpf) -> str:
    text = nstr(value, 15)
    return text.removesuffix(".0")  # 17, not 17.0

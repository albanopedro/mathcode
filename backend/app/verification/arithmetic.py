from app.math_engine.arithmetic import ArithmeticOutcome
from app.models.result import VerificationReport, VerificationStatus
from app.verification.numeric import OutsideDomain, TooLarge, agrees, evaluate, to_mpf
from app.verification.reports import report, show

_METHOD = "independent_numeric"


def verify_arithmetic(outcome: ArithmeticOutcome) -> VerificationReport:
    try:
        expected = evaluate(outcome.tree)
    except OutsideDomain:
        return report(
            VerificationStatus.FAILED,
            _METHOD,
            ["O avaliador independente considera a expressão indefinida."],
        )
    except TooLarge:
        return report(
            VerificationStatus.UNVERIFIED,
            _METHOD,
            ["Os valores intermediários são grandes demais para uma avaliação independente."],
        )
    actual = to_mpf(outcome.value)
    if actual is None or not agrees(expected, actual):
        return report(
            VerificationStatus.FAILED,
            _METHOD,
            [f"O avaliador independente obteve {show(expected.value)}."],
        )
    return report(
        VerificationStatus.VERIFIED_NUMERIC,
        _METHOD,
        [
            "Um avaliador independente (mpmath, com precisão ajustada ao tamanho dos números) "
            f"obteve {show(expected.value)}, igual ao resultado em pelo menos 30 algarismos "
            "significativos."
        ],
    )

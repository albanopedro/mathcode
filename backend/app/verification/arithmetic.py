"""Verification of numeric calculations (ADR 0003, ADR 0010).

Two independent methods, besides SymPy:

- the AST evaluator (mpmath, adaptive precision): every calculation;
- exact rational arithmetic (``Fraction``): calculations made only of
  rational numbers, + − × ÷ and integer powers. Two exact methods that agree
  are a proof, so those results are ``verified_symbolic``.
"""

import sympy as sp

from app.formatting.expressions import plain
from app.math_engine.arithmetic import ArithmeticOutcome
from app.models.result import CheckKind, ReasonCode, VerificationReport, VerificationStatus
from app.verification.exact import exact_value
from app.verification.numeric import OutsideDomain, TooLarge, agrees, evaluate, to_mpf
from app.verification.reports import failure, passed, report, show, unverified


def verify_arithmetic(outcome: ArithmeticOutcome) -> VerificationReport:
    try:
        expected = evaluate(outcome.tree)
    except OutsideDomain:
        return failure(
            CheckKind.NUMERIC, "O avaliador independente considera a expressão indefinida."
        )
    except TooLarge:
        return unverified(
            ReasonCode.TOO_LARGE,
            CheckKind.NUMERIC,
            "Os valores intermediários são grandes demais para uma avaliação independente.",
        )
    actual = to_mpf(outcome.value)
    if actual is None or not agrees(expected, actual):
        return failure(
            CheckKind.NUMERIC, f"O avaliador independente obteve {show(expected.value)}."
        )
    numeric = passed(
        CheckKind.NUMERIC,
        "Um avaliador independente (mpmath, com precisão ajustada ao tamanho dos números) "
        f"obteve {show(expected.value)}, igual ao resultado em pelo menos 30 algarismos "
        "significativos.",
    )

    exact = exact_value(outcome.tree)
    if exact is None:
        return report(VerificationStatus.VERIFIED_NUMERIC, [numeric])
    value = sp.Rational(exact.numerator, exact.denominator)
    if value != outcome.value:
        return failure(
            CheckKind.COMPARISON,
            f"Refazendo a conta com frações exatas, obtém-se {plain(value)}, e não o resultado.",
            numeric,
        )
    return report(
        VerificationStatus.VERIFIED_SYMBOLIC,
        [
            numeric,
            passed(
                CheckKind.COMPARISON,
                "Refazendo a conta com frações exatas (aritmética racional do Python, sem o "
                "SymPy), obtém-se exatamente o mesmo número.",
            ),
        ],
    )

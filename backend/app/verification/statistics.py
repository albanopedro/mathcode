"""Verification of descriptive statistics (ADR 0011).

Nothing is taken from the engine's own computation:

- the values are read again from the parser's tree with exact fractions
  (``verification/exact.py``, no SymPy) and compared with the engine's;
- every measure is recomputed by Python's ``statistics`` module, which is
  exact on fractions, and compared exactly (comparison of methods);
- exact properties are checked: the deviations from the mean add up to 0, the
  median splits the data in halves, Q1 and Q3 are the medians of the halves,
  the IQR is Q3 − Q1, and σ² and s² are the variances.
"""

import statistics as stdlib
from collections.abc import Sequence
from fractions import Fraction

from app.math_engine.statistics import StatisticsOutcome
from app.math_engine.values import to_rational
from app.models.result import CheckKind, VerificationCheck, VerificationReport, VerificationStatus
from app.verification.exact import exact_value
from app.verification.reports import failure, inconclusive, passed, report


def _show(value: Fraction) -> str:
    return str(value)  # "7/3", "-2"


def verify_statistics(outcome: StatisticsOutcome) -> VerificationReport:
    checks: list[VerificationCheck] = []

    reread = [exact_value(item) for item in outcome.items]
    if any(value is None for value in reread):
        checks.append(
            inconclusive(
                CheckKind.COMPARISON,
                "Alguns valores não são frações simples (como sqrt(4)) e foram lidos só pelo "
                "motor; as medidas foram conferidas a partir deles.",
            )
        )
        data = list(outcome.values)
    else:
        data = [value for value in reread if value is not None]
        if data != list(outcome.values):
            return failure(
                CheckKind.COMPARISON,
                "Relendo os valores com frações exatas, eles não são os usados no cálculo.",
            )
        checks.append(
            passed(
                CheckKind.COMPARISON,
                f"Os {len(data)} valores, relidos da expressão com frações exatas (sem o "
                "SymPy), são os mesmos usados no cálculo.",
            )
        )

    mismatch = _compare_with_stdlib(outcome, data)
    if mismatch is not None:
        return failure(CheckKind.COMPARISON, mismatch, *checks)
    checks.append(
        passed(
            CheckKind.COMPARISON,
            "O módulo statistics do Python (aritmética exata com frações, independente do "
            "motor) obtém os mesmos valores para média, mediana, quartis, moda, variâncias, "
            "mínimo, máximo, amplitude e soma.",
        )
    )

    deviations = sum((value - outcome.mean for value in data), Fraction(0))
    if deviations != 0:
        return failure(
            CheckKind.SYMBOLIC,
            f"A soma dos desvios em relação à média é {_show(deviations)}, e não 0.",
            *checks,
        )
    checks.append(
        passed(CheckKind.SYMBOLIC, "A soma dos desvios em relação à média é exatamente 0.")
    )

    half = len(data) / 2
    below = sum(1 for value in data if value <= outcome.median)
    above = sum(1 for value in data if value >= outcome.median)
    if below < half or above < half:
        return failure(
            CheckKind.SYMBOLIC, "A mediana não divide os dados em duas metades.", *checks
        )
    checks.append(
        passed(
            CheckKind.SYMBOLIC,
            f"A mediana divide os dados: {below} valor(es) são ≤ a ela e {above} são ≥ a ela, "
            f"de {len(data)}.",
        )
    )

    quartiles_problem = _check_quartiles(outcome, len(data))
    if quartiles_problem is not None:
        return failure(CheckKind.SYMBOLIC, quartiles_problem, *checks)
    if len(data) >= 4:
        checks.append(
            passed(
                CheckKind.SYMBOLIC,
                "Q1 e Q3 são as medianas das metades, Q1 ≤ mediana ≤ Q3, e o IQR é "
                "exatamente Q3 − Q1.",
            )
        )

    roots_problem = _check_roots(outcome)
    if roots_problem is not None:
        return failure(CheckKind.SYMBOLIC, roots_problem, *checks)
    checks.append(
        passed(
            CheckKind.SYMBOLIC,
            "Os desvios padrão são as raízes não negativas das variâncias: σ² e s² são "
            "exatamente as variâncias.",
        )
    )
    return report(VerificationStatus.VERIFIED_SYMBOLIC, checks)


def _compare_with_stdlib(outcome: StatisticsOutcome, data: Sequence[Fraction]) -> str | None:
    """None if everything agrees; otherwise which measure differs."""
    n = len(data)
    mean = stdlib.mean(data)
    modes = sorted(stdlib.multimode(data)) if len(set(data)) < n else []
    lower, upper = _halves(sorted(data))
    q1 = stdlib.median(lower) if n >= 4 else None
    q3 = stdlib.median(upper) if n >= 4 else None
    iqr = q3 - q1 if q1 is not None and q3 is not None else None
    expected: list[tuple[str, object, object]] = [
        ("quantidade", n, outcome.count),
        ("média", mean, outcome.mean),
        ("soma", mean * n, outcome.total),
        ("mediana", stdlib.median(data), outcome.median),
        ("primeiro quartil", q1, outcome.q1),
        ("terceiro quartil", q3, outcome.q3),
        ("intervalo interquartil", iqr, outcome.iqr),
        ("moda", modes, list(outcome.modes)),
        ("mínimo", min(data), outcome.minimum),
        ("máximo", max(data), outcome.maximum),
        ("amplitude", max(data) - min(data), outcome.spread),
        ("variância populacional", stdlib.pvariance(data), outcome.variance),
        (
            "variância amostral",
            stdlib.variance(data) if n > 1 else None,
            outcome.sample_variance,
        ),
    ]
    for name, theirs, ours in expected:
        if theirs != ours:
            return f"O módulo statistics obtém {name} = {theirs}, e não {ours}."
    return None


def _halves(data: Sequence[Fraction]) -> tuple[Sequence[Fraction], Sequence[Fraction]]:
    """The lower and upper halves; an odd count leaves the median out of both."""
    middle = len(data) // 2
    if len(data) % 2:
        return data[:middle], data[middle + 1 :]
    return data[:middle], data[middle:]


def _check_quartiles(outcome: StatisticsOutcome, n: int) -> str | None:
    """None if the quartiles obey the convention and the IQR follows from them."""
    if n < 4:
        if outcome.q1 is not None or outcome.q3 is not None or outcome.iqr is not None:
            return "Com menos de 4 valores, os quartis e o IQR não deveriam existir."
        return None
    if outcome.q1 is None or outcome.q3 is None or outcome.iqr is None:
        return "Faltam os quartis ou o IQR."
    if not outcome.q1 <= outcome.median <= outcome.q3:
        return "Os quartis não estão em ordem: Q1 ≤ mediana ≤ Q3 não vale."
    if outcome.iqr != outcome.q3 - outcome.q1:
        return f"O IQR é {_show(outcome.iqr)}, e não Q3 − Q1 = {_show(outcome.q3 - outcome.q1)}."
    return None


def _check_roots(outcome: StatisticsOutcome) -> str | None:
    std, sample_std = outcome.std, outcome.sample_std
    if std.is_negative or std**2 != to_rational(outcome.variance):
        return "O desvio padrão populacional ao quadrado não é a variância."
    if outcome.sample_variance is None:
        return None if sample_std is None else "Há desvio amostral sem variância amostral."
    if sample_std is None or sample_std.is_negative:
        return "Falta o desvio padrão amostral."
    if sample_std**2 != to_rational(outcome.sample_variance):
        return "O desvio padrão amostral ao quadrado não é a variância amostral."
    return None

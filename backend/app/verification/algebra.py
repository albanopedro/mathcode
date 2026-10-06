"""Verification of rewrites (simplify, factor, expand), prime factorization and division."""

from collections.abc import Iterator, Mapping

import sympy as sp
from mpmath import mp

from app.formatting.expressions import plain
from app.math_engine.algebra import DivisionOutcome, PrimeFactorization, RewriteOutcome
from app.models.intents import IntentName
from app.models.result import VerificationReport, VerificationStatus
from app.parsing.ast import Node, variables
from app.parsing.build import symbol
from app.verification.numeric import (
    BASE_PRECISION,
    Evaluation,
    OutsideDomain,
    Point,
    TooLarge,
    agrees,
    evaluate,
    sample_points,
    to_mpf,
)
from app.verification.reports import report, show

REQUIRED_POINTS = 6
MAX_ATTEMPTS = 40

_WORDS = {
    IntentName.SIMPLIFY: "simplificada",
    IntentName.FACTOR: "fatorada",
    IntentName.EXPAND: "expandida",
}


def points(key: str, names: list[str]) -> Iterator[dict[str, str]]:
    for attempt, point in enumerate(sample_points(key, names)):
        if attempt >= MAX_ATTEMPTS:
            return
        yield point


def describe(point: Mapping[str, str]) -> str:
    return ", ".join(f"{name} = {value}" for name, value in point.items())


def try_evaluate(node: Node, point: Point) -> Evaluation | None:
    try:
        return evaluate(node, point)
    except OutsideDomain, TooLarge:
        return None


# -- rewrites ---------------------------------------------------------------------------


def verify_rewrite(outcome: RewriteOutcome) -> VerificationReport:
    """The result must be equal to the original wherever the original is defined."""
    names = sorted(variables(outcome.tree))
    needed = REQUIRED_POINTS if names else 1
    agreeing = 0
    for point in points(outcome.parsed.canonical, names):
        expected = try_evaluate(outcome.tree, point)
        if expected is None:
            continue  # outside the original's domain: nothing to compare
        actual = to_mpf(outcome.result, {symbol(n): v for n, v in point.items()})
        if actual is None or not agrees(expected, actual):
            where = f"Em {describe(point)}, a" if names else "A"
            got = "não tem valor real" if actual is None else f"vale {show(actual)}"
            return report(
                VerificationStatus.FAILED,
                "independent_numeric",
                [f"{where} expressão original vale {show(expected.value)} e o resultado {got}."],
            )
        agreeing += 1
        if agreeing == needed:
            break

    if agreeing < needed:
        return report(
            VerificationStatus.UNVERIFIED,
            "independent_numeric",
            [f"Só {agreeing} ponto(s) do domínio foram encontrados para comparar."],
        )

    checks = [
        "Avaliador independente: a expressão original e o resultado coincidem em "
        f"{agreeing} ponto(s)" + (" sorteados." if names else ".")
    ]
    difference = outcome.original - outcome.result
    # Factor and expand are polynomial identities: expanding the difference is
    # an exact test. Simplify may involve functions, so it also tries simplify.
    if sp.expand(difference) == 0 or sp.simplify(difference) == 0:
        word = _WORDS.get(outcome.operation, "reescrita")
        checks.append(f"A diferença entre a expressão original e a forma {word} se reduz a 0.")
        return report(VerificationStatus.VERIFIED_SYMBOLIC, "symbolic+numeric", checks)
    return report(VerificationStatus.VERIFIED_NUMERIC, "independent_numeric", checks)


# -- prime factorization ------------------------------------------------------------------

_DETERMINISTIC_PRIME_LIMIT = 2**64


def verify_prime_factorization(outcome: PrimeFactorization) -> VerificationReport:
    product = 1
    for prime, exponent in outcome.factors:
        product *= prime**exponent
    if product != abs(outcome.number):
        return report(
            VerificationStatus.FAILED,
            "exact_product",
            [f"O produto dos fatores é {product}, não {abs(outcome.number)}."],
        )
    composite = [prime for prime, _ in outcome.factors if not sp.isprime(prime)]
    if composite:
        return report(VerificationStatus.FAILED, "primality", [f"{composite[0]} não é primo."])
    largest = max(prime for prime, _ in outcome.factors)
    method = (
        "teste determinístico"
        if largest < _DETERMINISTIC_PRIME_LIMIT
        else "teste BPSW, que não tem contraexemplo conhecido"
    )
    return report(
        VerificationStatus.VERIFIED_SYMBOLIC,
        "exact_product+primality",
        [
            f"Multiplicando os fatores com inteiros exatos, obtém-se {abs(outcome.number)}.",
            f"Cada fator foi confirmado primo ({method}).",
        ],
    )


def verify_factor(outcome: RewriteOutcome | PrimeFactorization) -> VerificationReport:
    if isinstance(outcome, PrimeFactorization):
        return verify_prime_factorization(outcome)
    return verify_rewrite(outcome)


# -- polynomial division ------------------------------------------------------------------


def verify_division(outcome: DivisionOutcome) -> VerificationReport:
    var = outcome.variable
    a, b, q, r = outcome.dividend, outcome.divisor, outcome.quotient, outcome.remainder

    identity = sp.expand(b * q + r - a)
    if identity != 0:
        return report(
            VerificationStatus.FAILED, "identity", [f"B·Q + R − A = {plain(identity)}, e não 0."]
        )
    degree_r = sp.degree(r, var) if r != 0 else None
    degree_b = sp.degree(b, var)
    if degree_r is not None and degree_r >= degree_b:
        return report(
            VerificationStatus.FAILED,
            "degree",
            [f"O resto tem grau {degree_r}, que não é menor que o grau {degree_b} do divisor."],
        )

    agreeing = 0
    for point in points(outcome.parsed.canonical, [var.name]):
        dividend = try_evaluate(outcome.dividend_tree, point)
        divisor = try_evaluate(outcome.divisor_tree, point)
        if dividend is None or divisor is None:
            continue
        subs = {var: point[var.name]}
        q_value, r_value = to_mpf(q, subs), to_mpf(r, subs)
        if q_value is None or r_value is None:
            continue
        # Combine at full precision: outside workdps, mpmath rounds to 15 digits.
        with mp.workdps(BASE_PRECISION):
            rebuilt = divisor.value * q_value + r_value
        if not agrees(dividend, rebuilt, divisor.error_bound * abs(q_value)):
            return report(
                VerificationStatus.FAILED,
                "independent_numeric",
                [f"Em {describe(point)}, A vale {show(dividend.value)}, mas B·Q + R não."],
            )
        agreeing += 1
        if agreeing == REQUIRED_POINTS:
            break

    remainder_check = (
        "O resto é 0: a divisão é exata."
        if r == 0
        else f"O resto tem grau {degree_r}, menor que o grau {degree_b} do divisor."
    )
    return report(
        VerificationStatus.VERIFIED_SYMBOLIC,
        "identity+numeric",
        [
            "Expandindo B·Q + R, obtém-se exatamente o dividendo A.",
            remainder_check,
            f"O avaliador independente confirma A = B·Q + R em {agreeing} pontos sorteados.",
        ],
    )

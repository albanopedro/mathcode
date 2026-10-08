"""Verification of counting and probability (ADR 0015).

Nothing is taken from the engine's own computation (SymPy):

- the values are read again from the parser's tree with exact fractions
  (``verification/exact.py``) and compared with the engine's;
- counts are checked by another formula with Python integers (C(n, k)·k! is the
  product of k consecutive integers; anagrams choose the places of each letter
  in turn) and, when there are at most ``MAX_LISTED`` of them, by listing the
  arrangements one by one;
- events are checked on the regions of the Venn diagram, which must be
  probabilities adding up to 1, and by rules the engine does not use (the
  multiplication rule, P(nem A nem B) = P(não A)·P(não B) for independent events);
- the binomial distribution is rebuilt term by term with the recurrence
  P(i + 1) = P(i)·(n − i)/(i + 1)·p/(1 − p); it must add up to 1, P(X ≥ k)
  is 1 − P(X < k), and the mean and variance are the sums Σ i·P(i) and
  Σ i²·P(i) − μ².
"""

import itertools
from collections.abc import Iterator
from fractions import Fraction

import sympy as sp

from app.math_engine.probability import BinomialSummary, ProbabilityOutcome
from app.models.result import CheckKind, VerificationCheck, VerificationReport, VerificationStatus
from app.verification.exact import exact_value
from app.verification.reports import failure, inconclusive, passed, report

# Counts up to this size are also listed one by one.
MAX_LISTED = 100_000

_SHOWN = {"A": "P(A)", "B": "P(B)", "A∩B": "P(A ∩ B)", "A∪B": "P(A ∪ B)"}


class _Mismatch(Exception):
    """The second method disagrees: the message says how."""


def _fraction(value: sp.Rational) -> Fraction:
    return Fraction(int(value.p), int(value.q))


def verify_probability(outcome: ProbabilityOutcome) -> VerificationReport:
    checks: list[VerificationCheck] = []
    try:
        values = _reread(outcome, checks)
        match outcome.group:
            case "counting":
                _verify_counting(outcome, values, checks)
            case "events":
                _verify_events(outcome, values, checks)
            case "binomial":
                _verify_binomial(outcome, values, checks)
    except _Mismatch as mismatch:
        return failure(CheckKind.COMPARISON, str(mismatch), *checks)
    return report(VerificationStatus.VERIFIED_SYMBOLIC, checks)


def _reread(outcome: ProbabilityOutcome, checks: list[VerificationCheck]) -> dict[str, Fraction]:
    engine = {name: _fraction(value) for name, value in outcome.values.items()}
    if outcome.calculation == "anagrams":
        counted: dict[str, int] = {}
        for letter in outcome.parsed.canonical:
            counted[letter] = counted.get(letter, 0) + 1
        if tuple(counted.items()) != outcome.letters:
            raise _Mismatch("Contando de novo as letras da palavra, as repetições são outras.")
        checks.append(
            passed(
                CheckKind.COMPARISON,
                f"As letras de {outcome.parsed.canonical}, contadas de novo uma a uma, repetem "
                "como no cálculo.",
            )
        )
        return engine

    reread: dict[str, Fraction] = {}
    for name, node in outcome.value_nodes.items():
        value = exact_value(node)
        if value is None:
            checks.append(
                inconclusive(
                    CheckKind.COMPARISON,
                    "Alguns valores não são frações simples (como sqrt(4)) e foram lidos só pelo "
                    "motor; o resultado foi conferido a partir deles.",
                )
            )
            return engine
        reread[name] = value / 100 if name in outcome.percent else value
    if reread != engine:
        raise _Mismatch("Relendo os valores com frações exatas, eles não são os usados no cálculo.")
    shown = ", ".join(f"{_SHOWN.get(name, name)} = {value}" for name, value in reread.items())
    checks.append(
        passed(
            CheckKind.COMPARISON,
            f"Os valores, relidos da entrada com frações exatas (sem o SymPy), são os usados no "
            f"cálculo: {shown}.",
        )
    )
    return reread


# -- counting -------------------------------------------------------------------------------------


def _falling(n: int, k: int) -> int:
    """n·(n − 1)···(n − k + 1), one factor at a time (0 when k > n ≥ 0)."""
    result = 1
    for factor in range(n - k + 1, n + 1):
        result *= factor
    return result


def _factorial(n: int) -> int:
    return _falling(n, n)


def _verify_counting(
    outcome: ProbabilityOutcome, values: dict[str, Fraction], checks: list[VerificationCheck]
) -> None:
    count = int(outcome.result)  # every count is an integer
    n = int(values["n"])
    k = int(values["k"]) if "k" in values else 0
    shown = outcome.plain_symbol

    match outcome.calculation:
        case "factorial":
            expected = _falling(n, n)
            rule = f"o produto 1 · 2 · … · {n}, feito fator a fator com inteiros do Python"
        case "arrangement":
            expected = _falling(n, k)
            rule = f"o produto de {k} inteiros consecutivos a partir de {n}, para baixo"
        case "arrangement_repetition":
            expected = 1
            for _ in range(k):
                expected *= n
            rule = f"{n} escolhas para cada uma das {k} posições, multiplicadas uma a uma"
        case "combination" | "combination_repetition":
            top = n if outcome.calculation == "combination" else n + k - 1
            # C(top, k)·k! counts the ordered choices: top·(top − 1)···(top − k + 1).
            if count * _factorial(k) != _falling(top, k):
                raise _Mismatch(f"{shown} · {k}! não é o número de escolhas em ordem.")
            expected = count
            rule = (
                f"{shown} · {k}! é o produto de {k} inteiros consecutivos a partir de {top} "
                "(as mesmas escolhas, agora em ordem)"
            )
        case _:  # anagrams: choose the places of each letter, one letter at a time
            expected, free = 1, len(outcome.parsed.canonical)
            for _, times in outcome.letters:
                expected *= _falling(free, times) // _factorial(times)
                free -= times
            rule = "a escolha das posições de cada letra, uma letra por vez"
    if expected != count:
        raise _Mismatch(f"Por outro caminho ({rule}), obtém-se {expected}, e não {count}.")
    checks.append(
        passed(CheckKind.COMPARISON, f"Por outro caminho, {rule}, obtém-se o mesmo número.")
    )

    if count <= MAX_LISTED:
        listed = sum(1 for _ in _listing(outcome, n, k))
        if listed != count:
            raise _Mismatch(f"Listando uma a uma, há {listed} possibilidades, e não {count}.")
        checks.append(
            passed(
                CheckKind.COMPARISON,
                f"Listando as possibilidades uma a uma (itertools), há exatamente {count}.",
            )
        )


def _listing(outcome: ProbabilityOutcome, n: int, k: int) -> Iterator[object]:
    items = range(n)
    match outcome.calculation:
        case "factorial":
            return itertools.permutations(items)
        case "arrangement":
            return itertools.permutations(items, k)
        case "arrangement_repetition":
            return itertools.product(items, repeat=k)
        case "combination":
            return itertools.combinations(items, k)
        case "combination_repetition":
            return itertools.combinations_with_replacement(items, k)
    return _distinct_orders(dict(outcome.letters))


def _distinct_orders(left: dict[str, int]) -> Iterator[str]:
    """Each different ordering of the letters, once: the anagrams themselves."""
    if not any(left.values()):
        yield ""
        return
    for letter, times in left.items():
        if times:
            left[letter] -= 1
            for rest in _distinct_orders(left):
                yield letter + rest
            left[letter] += 1


# -- events ---------------------------------------------------------------------------------------


def _verify_events(
    outcome: ProbabilityOutcome, values: dict[str, Fraction], checks: list[VerificationCheck]
) -> None:
    result = _fraction(outcome.result)  # a probability
    match outcome.calculation:
        case "complement":
            if result + values["A"] != 1:
                raise _Mismatch("P(A) + P(não A) não dá 1.")
            checks.append(passed(CheckKind.SYMBOLIC, "P(A) + P(não A) = 1, exatamente."))
            return
        case "conditional":
            if not 0 <= result <= 1 or result * values["B"] != values["A∩B"]:
                raise _Mismatch("Pela regra do produto, P(A | B) · P(B) não dá P(A ∩ B).")
            checks.append(
                passed(
                    CheckKind.SYMBOLIC,
                    "Pela regra do produto, P(A | B) · P(B) = P(A ∩ B), exatamente, e P(A | B) "
                    "está entre 0 e 1.",
                )
            )
            return
    a, b = values["A"], values["B"]
    if outcome.calculation in ("intersection", "intersection_independent"):
        both = result
    else:  # a union: A ∩ B given, or from the definition of independent events
        both = values.get("A∩B", a * b)
    regions = {
        "só A": a - both,
        "só B": b - both,
        "A e B": both,
        "nem A nem B": 1 - a - b + both,
    }
    if any(not 0 <= region <= 1 for region in regions.values()) or sum(regions.values()) != 1:
        raise _Mismatch("As regiões do diagrama de Venn não são probabilidades que somam 1.")
    listed = ", ".join(f"{name} = {value}" for name, value in regions.items())
    checks.append(
        passed(
            CheckKind.SYMBOLIC,
            f"As quatro regiões do diagrama de Venn são probabilidades que somam 1: {listed}.",
        )
    )

    match outcome.calculation:
        case "intersection":
            if regions["só A"] + regions["só B"] + both != values["A∪B"]:
                raise _Mismatch("Somando as regiões, a união não é a informada.")
            message = "Somando as regiões só A, só B e A e B, obtém-se a P(A ∪ B) informada."
        case "union":
            if regions["só A"] + regions["só B"] + both != result:
                raise _Mismatch("Somando as regiões, a união é outra.")
            message = "Somando as regiões só A, só B e A e B, obtém-se o resultado."
        case _:  # independent events
            neither = regions["nem A nem B"]
            if both * neither != regions["só A"] * regions["só B"]:
                raise _Mismatch("As regiões não são as de eventos independentes.")
            if outcome.calculation == "union_independent" and 1 - result != (1 - a) * (1 - b):
                raise _Mismatch("1 − P(A ∪ B) não é P(não A) · P(não B).")
            message = (
                "As regiões são as de eventos independentes: P(A e B) · P(nem A nem B) = "
                "P(só A) · P(só B)."
            )
            if outcome.calculation == "union_independent":
                message += " E 1 − P(A ∪ B) = P(não A) · P(não B), outra fórmula da união."
    checks.append(passed(CheckKind.SYMBOLIC, message))


# -- the binomial distribution --------------------------------------------------------------------


def _distribution(n: int, p: Fraction) -> list[Fraction]:
    """P(X = 0), ..., P(X = n) by the recurrence between neighboring terms."""
    if p in (0, 1):
        certain = 0 if p == 0 else n
        return [Fraction(int(i == certain)) for i in range(n + 1)]
    terms = [(1 - p) ** n]
    ratio = p / (1 - p)
    for i in range(n):
        terms.append(terms[-1] * (n - i) / (i + 1) * ratio)
    return terms


def _verify_binomial(
    outcome: ProbabilityOutcome, values: dict[str, Fraction], checks: list[VerificationCheck]
) -> None:
    n, p = int(values["n"]), values["p"]
    terms = _distribution(n, p)
    if sum(terms) != 1:
        raise _Mismatch("A distribuição refeita não soma 1.")
    checks.append(
        passed(
            CheckKind.SYMBOLIC,
            f"A distribuição, refeita termo a termo pela recorrência P(i + 1) = P(i) · "
            f"(n − i)/(i + 1) · p/(1 − p) com frações exatas, soma exatamente 1 "
            f"({n + 1} termos).",
        )
    )

    if isinstance(outcome.result, BinomialSummary):
        summary = outcome.result
        mean = sum((i * term for i, term in enumerate(terms)), Fraction(0))
        variance = sum((i * i * term for i, term in enumerate(terms)), Fraction(0)) - mean**2
        if mean != _fraction(summary.mean) or variance != _fraction(summary.variance):
            raise _Mismatch(f"Pelas somas, μ = {mean} e σ² = {variance}.")
        if summary.std.is_negative or sp.expand(summary.std**2) != summary.variance:
            raise _Mismatch("σ não é a raiz quadrada da variância.")
        checks.append(
            passed(
                CheckKind.COMPARISON,
                "Pelas somas Σ i · P(i) e Σ i² · P(i) − μ² sobre a distribuição refeita, obtêm-se "
                "a mesma média e a mesma variância; σ² é a variância.",
            )
        )
        return

    k = int(values["k"])
    result = _fraction(outcome.result)  # a probability
    match outcome.calculation:
        case "binomial_exact":
            expected, how = terms[k], f"o termo {k} da distribuição refeita"
        case "binomial_at_most":
            expected, how = sum(terms[: k + 1], Fraction(0)), f"a soma dos termos de 0 a {k}"
        case _:
            expected = 1 - sum(terms[:k], Fraction(0))
            how = f"1 − P(X < {k}), pelo complementar"
    if expected != result:
        raise _Mismatch(f"Por {how}, obtém-se {expected}.")
    checks.append(passed(CheckKind.COMPARISON, f"Por {how}, obtém-se exatamente o resultado."))

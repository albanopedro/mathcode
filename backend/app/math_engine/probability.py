"""Counting and probability with exact numbers (Phase 10, ADR 0015).

One operation, three groups of calculations:

- counting: n!, A(n, k), AR(n, k) = nᵏ, C(n, k), CR(n, k) and the anagrams of
  a word;
- events: P(não A), P(A ∩ B), P(A ∪ B) and P(A | B), from the probabilities
  given as "P(A) = 1/2; P(B) = 1/3; P(A e B) = 1/6";
- the binomial distribution: P(X = k), P(X ≤ k), P(X ≥ k), mean and variance,
  from "n = 5; k = 3; p = 1/2".

Every value is read by the safe parser (ADR 0002); a probability may end in
"%". Values the calculation does not use are accepted with a notice, and the
probabilities given are checked for coherence (0 ≤ P ≤ 1, P(A ∩ B) ≤ P(A)...).
Results are exact: integers for counts, fractions for probabilities.
"""

import math
import re
import unicodedata
from collections import Counter
from dataclasses import dataclass, field
from typing import Literal

import sympy as sp

from app.core.errors import ErrorCode, MathError
from app.core.limits import MAX_RESULT_DIGITS
from app.core.notices import Notice, NoticeCode
from app.models.intents import ProbabilityCalculation, ProbabilityParams
from app.parsing import parse
from app.parsing.ast import Equation, ExpressionList, Node, System, has_brackets, has_points
from app.parsing.build import ExpressionBuilder, ensure_within_limits, log10_falling
from app.parsing.printer import to_text

type Group = Literal["counting", "events", "binomial"]

# Trials of a binomial distribution, and letters of a word for anagrams.
MAX_TRIALS = 1000
MAX_WORD_LETTERS = 30

# Names of the values. Events are stored as "A", "B", "A∩B" and "A∪B".
_GROUP_NAMES: dict[Group, tuple[str, ...]] = {
    "counting": ("n", "k"),
    "events": ("A", "B", "A∩B", "A∪B"),
    "binomial": ("n", "k", "p"),
}
_SHOWN = {"A": "P(A)", "B": "P(B)", "A∩B": "P(A ∩ B)", "A∪B": "P(A ∪ B)"}


@dataclass(frozen=True)
class CalculationSpec:
    group: Group
    label: str  # with its article: "a combinação"
    needs: tuple[str, ...]  # names of the values, in the order of the example
    example: str


CATALOG: dict[ProbabilityCalculation, CalculationSpec] = {
    "factorial": CalculationSpec("counting", "o fatorial", ("n",), "n = 5"),
    "arrangement": CalculationSpec("counting", "o arranjo", ("n", "k"), "n = 6; k = 2"),
    "arrangement_repetition": CalculationSpec(
        "counting", "o arranjo com repetição", ("n", "k"), "n = 3; k = 2"
    ),
    "combination": CalculationSpec("counting", "a combinação", ("n", "k"), "n = 10; k = 3"),
    "combination_repetition": CalculationSpec(
        "counting", "a combinação com repetição", ("n", "k"), "n = 3; k = 2"
    ),
    "anagrams": CalculationSpec("counting", "os anagramas", (), "BANANA"),
    "complement": CalculationSpec("events", "a probabilidade de não A", ("A",), "P(A) = 1/4"),
    "intersection": CalculationSpec(
        "events",
        "a probabilidade de A e B",
        ("A", "B", "A∪B"),
        "P(A) = 1/2; P(B) = 1/3; P(A ou B) = 2/3",
    ),
    "intersection_independent": CalculationSpec(
        "events",
        "a probabilidade de A e B, independentes",
        ("A", "B"),
        "P(A) = 1/2; P(B) = 1/3",
    ),
    "union": CalculationSpec(
        "events",
        "a probabilidade de A ou B",
        ("A", "B", "A∩B"),
        "P(A) = 1/2; P(B) = 1/3; P(A e B) = 1/6",
    ),
    "union_independent": CalculationSpec(
        "events",
        "a probabilidade de A ou B, independentes",
        ("A", "B"),
        "P(A) = 1/2; P(B) = 1/3",
    ),
    "conditional": CalculationSpec(
        "events",
        "a probabilidade de A dado B",
        ("A∩B", "B"),
        "P(A e B) = 1/6; P(B) = 1/3",
    ),
    "binomial_exact": CalculationSpec(
        "binomial", "a probabilidade P(X = k)", ("n", "k", "p"), "n = 5; k = 3; p = 1/2"
    ),
    "binomial_at_most": CalculationSpec(
        "binomial", "a probabilidade P(X ≤ k)", ("n", "k", "p"), "n = 5; k = 3; p = 1/2"
    ),
    "binomial_at_least": CalculationSpec(
        "binomial", "a probabilidade P(X ≥ k)", ("n", "k", "p"), "n = 5; k = 3; p = 1/2"
    ),
    "binomial_summary": CalculationSpec(
        "binomial", "a média e a variância", ("n", "p"), "n = 10; p = 30%"
    ),
}


@dataclass(frozen=True)
class ReadInput:
    """How the input was read: the ``parsed`` of other outcomes (canonical text)."""

    source: str
    canonical: str


@dataclass(frozen=True)
class BinomialSummary:
    mean: sp.Rational
    variance: sp.Rational
    std: sp.Expr


@dataclass(frozen=True)
class ProbabilityOutcome:
    parsed: ReadInput
    calculation: ProbabilityCalculation
    values: dict[str, sp.Rational]  # name -> value (a percentage already divided by 100)
    value_nodes: dict[str, Node]  # the expression of each value, for the verifier
    percent: frozenset[str]  # values written with %
    letters: tuple[tuple[str, int], ...]  # anagrams: each letter and how many times
    result: sp.Rational | BinomialSummary
    symbol: str  # LaTeX: "C(10, 3)", "P(A \cup B)"
    plain_symbol: str  # "C(10, 3)", "P(A ∪ B)"
    formula: str  # LaTeX of the formula used
    notices: tuple[Notice, ...] = field(default_factory=tuple)

    @property
    def group(self) -> Group:
        return CATALOG[self.calculation].group


def probability(params: ProbabilityParams) -> ProbabilityOutcome:
    spec = CATALOG[params.calculation]
    if params.calculation == "anagrams":
        return _anagrams(params.data)

    reader = _Reader(params.data, spec)
    values = reader.values
    match spec.group:
        case "counting":
            result, symbol, plain_symbol, formula = _counting(params.calculation, values)
        case "events":
            _check_events(values)
            result, symbol, plain_symbol, formula = _events(params.calculation, values)
        case "binomial":
            result, symbol, plain_symbol, formula = _binomial(params.calculation, values)
    numbers = [result] if isinstance(result, sp.Rational) else [result.mean, result.variance]
    for number in numbers:
        ensure_within_limits(number)
    notices = [*reader.notices, *reader.builder.notices]
    if params.calculation in ("arrangement", "combination") and values["k"] > values["n"]:
        name = "A" if params.calculation == "arrangement" else "C"
        notices.append(_count_is_zero(name, int(values["n"]), int(values["k"])))
    return ProbabilityOutcome(
        parsed=ReadInput(params.data, reader.canonical),
        calculation=params.calculation,
        values=values,
        value_nodes=reader.nodes,
        percent=frozenset(reader.percent),
        letters=(),
        result=result,
        symbol=symbol,
        plain_symbol=plain_symbol,
        formula=formula,
        notices=tuple(notices),
    )


# -- reading the values -----------------------------------------------------------------------


# One item: "n = 10", "p = 30%" or "P(A e B) = 1/6".
_ITEM = re.compile(
    r"\s*(?:(?P<name>[a-zA-Z])|[Pp]\s*\((?P<event>[^)]*)\))\s*=\s*(?P<value>.*?)\s*", re.DOTALL
)
_EVENTS = {
    "a": "A",
    "b": "B",
    "a e b": "A∩B",
    "b e a": "A∩B",
    "a∩b": "A∩B",
    "b∩a": "A∩B",
    "a ou b": "A∪B",
    "b ou a": "A∪B",
    "a∪b": "A∪B",
    "b∪a": "A∪B",
}


class _Reader:
    """Splits "n = 10; k = 3" into items and reads each value with the safe parser."""

    def __init__(self, text: str, spec: CalculationSpec) -> None:
        self.builder = ExpressionBuilder()
        self.values: dict[str, sp.Rational] = {}
        self.nodes: dict[str, Node] = {}
        self.percent: set[str] = set()
        self.notices: list[Notice] = []
        self._spec = spec
        shown: list[str] = []

        items = _split(text)
        if len(items) == 1 and "=" not in items[0][1] and len(spec.needs) == 1:
            # "5" for the factorial: the only value needed.
            start, item = items[0]
            name = spec.needs[0]
            self._read(name, item, start)
            shown.append(self._show(name))
        else:
            for start, item in items:
                found = _ITEM.fullmatch(item)
                if found is None:
                    raise MathError(
                        ErrorCode.INVALID_INPUT_FOR_INTENT,
                        f"Escreva cada valor com o seu nome, como em {spec.example}.",
                        start,
                    )
                name = self._name(found, start)
                if name in self.values:
                    raise MathError(
                        ErrorCode.INVALID_INPUT_FOR_INTENT,
                        f"{_SHOWN.get(name, name)} foi informado duas vezes.",
                        start,
                    )
                self._read(name, found.group("value"), start + found.start("value"))
                shown.append(self._show(name))

        missing = [name for name in spec.needs if name not in self.values]
        if missing:
            hint = ""
            if "A∪B" in missing or ("A∩B" in missing and "A" in spec.needs):
                hint = " Se A e B forem independentes, escolha o cálculo com 'independentes'."
            raise MathError(
                ErrorCode.INVALID_INPUT_FOR_INTENT,
                f"Para {spec.label}, informe: {spec.example}.{hint}",
            )
        unused = [name for name in self.values if name not in spec.needs]
        if unused and spec.group != "events":  # events: extra values are checked for coherence
            listed = ", ".join(_SHOWN.get(name, name) for name in unused)
            self.notices.append(
                Notice(NoticeCode.UNUSED_VALUES, f"Não usado em {spec.label}: {listed}.")
            )
        self.canonical = "; ".join(shown)

    def _name(self, found: re.Match[str], start: int) -> str:
        names = _GROUP_NAMES[self._spec.group]
        if found.group("event") is not None:
            folded = re.sub(r"\s+", " ", _fold(found.group("event")).strip())
            folded = re.sub(r"\s*([∩∪])\s*", r"\1", folded)
            name = _EVENTS.get(folded)
            if name is None:
                raise MathError(
                    ErrorCode.INVALID_INPUT_FOR_INTENT,
                    "Os eventos são P(A), P(B), P(A e B) e P(A ou B).",
                    start,
                )
        else:
            name = found.group("name")
        if name not in names:
            raise MathError(
                ErrorCode.INVALID_INPUT_FOR_INTENT,
                f"{_SHOWN.get(name, name)} não é um valor deste cálculo. Para "
                f"{self._spec.label}, informe: {self._spec.example}.",
                start,
            )
        return name

    def _read(self, name: str, text: str, start: int) -> None:
        stripped = text.rstrip()
        percent = stripped.endswith("%")
        if percent:
            if name not in ("A", "B", "A∩B", "A∪B", "p"):
                raise MathError(
                    ErrorCode.INVALID_INPUT_FOR_INTENT,
                    f"Só probabilidades podem ser escritas com %; {name} não é uma.",
                    start + len(stripped) - 1,
                )
            stripped = stripped[:-1]
        if not stripped.strip():
            raise MathError(
                ErrorCode.INVALID_INPUT_FOR_INTENT,
                f"Falta o valor de {_SHOWN.get(name, name)}.",
                start,
            )
        try:
            parsed = parse(stripped)
        except MathError as exc:
            position = None if exc.position is None else exc.position + start
            raise MathError(exc.code, exc.message, position) from None
        tree = parsed.tree
        self.notices.extend(parsed.notices)
        if isinstance(tree, Equation | System | ExpressionList):
            raise MathError(
                ErrorCode.INVALID_INPUT_FOR_INTENT,
                f"Escreva cada valor com o seu nome, como em {self._spec.example}.",
                start,
            )
        value = self._number(name, tree, start)
        if percent:
            value = value / 100
            self.percent.add(name)
        self.values[name] = value
        self.nodes[name] = tree

    def _number(self, name: str, tree: Node, start: int) -> sp.Rational:
        shown = _SHOWN.get(name, name)
        if has_brackets(tree) or has_points(tree):
            raise MathError(
                ErrorCode.INVALID_INPUT_FOR_INTENT, f"{shown} precisa ser um número.", start
            )
        try:
            value = self.builder.build(tree)
        except MathError as exc:
            position = None if exc.position is None else exc.position + start
            raise MathError(exc.code, exc.message, position) from None
        if value.free_symbols:
            raise MathError(
                ErrorCode.INVALID_INPUT_FOR_INTENT,
                f"{shown} precisa ser um número, sem variáveis.",
                start,
            )
        if not value.is_Rational:
            raise MathError(
                ErrorCode.INVALID_INPUT_FOR_INTENT,
                f"{shown} precisa ser um número racional, como 1/2, 0,3 ou 30%.",
                start,
            )
        return value

    def _show(self, name: str) -> str:
        value = to_text(self.nodes[name]) + ("%" if name in self.percent else "")
        return f"{_SHOWN.get(name, name)} = {value}"


def _split(text: str) -> list[tuple[int, str]]:
    """Items separated by ";" or by ", " (with a space: "0,5" is a decimal), with their start."""
    items: list[tuple[int, str]] = []
    depth, start = 0, 0
    for i, ch in enumerate(text):
        if ch in "([":
            depth += 1
        elif ch in ")]":
            depth -= 1
        elif depth == 0 and (ch == ";" or (ch == "," and text[i + 1 : i + 2].isspace())):
            items.append((start, text[start:i]))
            start = i + 1
    items.append((start, text[start:]))
    if any(not item.strip() for _, item in items):
        raise MathError(
            ErrorCode.INVALID_INPUT_FOR_INTENT, "Há um valor vazio entre os separadores."
        )
    return items


def _fold(text: str) -> str:
    """Lowercase without accents."""
    return "".join(unicodedata.normalize("NFD", ch)[0].lower() for ch in text)


def _natural(values: dict[str, sp.Rational], name: str, minimum: int = 0) -> int:
    value = values[name]
    if not value.is_integer or value < minimum:
        what = (
            "um inteiro não negativo" if minimum == 0 else f"um inteiro maior ou igual a {minimum}"
        )
        raise MathError(ErrorCode.DOMAIN_ERROR, f"{name} precisa ser {what}.")
    return int(value)


def _check_digits(log10: float) -> None:
    if log10 > MAX_RESULT_DIGITS:
        raise MathError(
            ErrorCode.LIMIT_EXCEEDED, f"O resultado teria mais de {MAX_RESULT_DIGITS} dígitos."
        )


def _count_is_zero(name: str, n: int, k: int) -> Notice:
    choose = "escolher" if name == "C" else "ordenar"
    return Notice(
        NoticeCode.COUNT_IS_ZERO,
        f"Em {name}({n}, {k}), k = {k} é maior que n = {n}: não há como {choose} {k} de {n}, "
        f"e o resultado é 0.",
    )


# -- counting -------------------------------------------------------------------------------------


def _counting(
    calculation: ProbabilityCalculation, values: dict[str, sp.Rational]
) -> tuple[sp.Rational, str, str, str]:
    if calculation == "factorial":
        n = _natural(values, "n")
        _check_digits(log10_falling(n, n))
        return sp.factorial(n), f"{n}!", f"{n}!", r"n! = n \cdot (n - 1) \cdots 2 \cdot 1"

    minimum = 1 if calculation.endswith("_repetition") else 0
    n, k = _natural(values, "n", minimum), _natural(values, "k")
    match calculation:
        case "arrangement":
            symbol = f"A({n}, {k})"
            formula = r"A(n, k) = \frac{n!}{(n - k)!}"
            if k > n:
                return sp.Integer(0), symbol, symbol, formula
            _check_digits(log10_falling(n, k))
            return sp.ff(n, k), symbol, symbol, formula
        case "arrangement_repetition":
            symbol = f"AR({n}, {k})"
            _check_digits(k * math.log10(n) if n > 1 else 0)
            return sp.Integer(n) ** k, symbol, symbol, "AR(n, k) = n^k"
        case "combination":
            symbol = f"C({n}, {k})"
            formula = r"C(n, k) = \frac{n!}{k! \, (n - k)!}"
            if k > n:
                return sp.Integer(0), symbol, symbol, formula
            smaller = min(k, n - k)
            _check_digits(log10_falling(n, smaller) - log10_falling(smaller, smaller))
            return sp.binomial(n, k), symbol, symbol, formula
    # Choosing k of n kinds, repeating: the multisets of size k (stars and bars).
    symbol = f"CR({n}, {k})"
    top = n + k - 1
    smaller = min(k, n - 1)
    _check_digits(log10_falling(top, smaller) - log10_falling(smaller, smaller))
    return sp.binomial(top, k), symbol, symbol, r"CR(n, k) = C(n + k - 1, k)"


def _anagrams(text: str) -> ProbabilityOutcome:
    word = text.strip().strip("\"'\u201c\u201d\u2018\u2019")
    if not word or any(not ch.isalpha() for ch in word):
        raise MathError(
            ErrorCode.INVALID_INPUT_FOR_INTENT,
            "Para anagramas, escreva uma palavra só, com letras e sem espaços: BANANA.",
        )
    folded = _fold(word).upper()
    if len(folded) != len(word) or not folded.isascii():
        raise MathError(
            ErrorCode.INVALID_INPUT_FOR_INTENT,
            "Para anagramas, use só letras de A a Z (com ou sem acento).",
        )
    if len(folded) > MAX_WORD_LETTERS:
        raise MathError(
            ErrorCode.LIMIT_EXCEEDED,
            f"A palavra tem mais de {MAX_WORD_LETTERS} letras.",
        )
    notices: list[Notice] = []
    if folded != word.upper():
        notices.append(
            Notice(
                NoticeCode.ACCENTS_IGNORED,
                f"Os acentos foram ignorados: {word} foi lida como {folded}.",
            )
        )
    letters = tuple(Counter(folded).items())  # in the order they first appear
    result = sp.factorial(len(folded))
    repeated = [count for _, count in letters if count > 1]
    for count in repeated:
        result /= sp.factorial(count)
    # Permutation with repetition, as in textbooks: P_6^{3, 2} for BANANA.
    symbol = f"P_{{{len(folded)}}}" + (f"^{{{', '.join(map(str, repeated))}}}" if repeated else "")
    denominator = r" \, ".join(f"{count}!" for count in repeated)
    count = rf"\frac{{{len(folded)}!}}{{{denominator}}}" if repeated else f"{len(folded)}!"
    formula = f"{symbol} = {count}"
    return ProbabilityOutcome(
        parsed=ReadInput(text, folded),
        calculation="anagrams",
        values={"n": sp.Integer(len(folded))},
        value_nodes={},
        percent=frozenset(),
        letters=letters,
        result=result,
        symbol=symbol,
        plain_symbol=f"anagramas de {folded}",
        formula=formula,
        notices=tuple(notices),
    )


# -- events ---------------------------------------------------------------------------------------


def _check_events(values: dict[str, sp.Rational]) -> None:
    """Each probability in [0, 1], and the ones given compatible with each other."""
    for name, value in values.items():
        if not 0 <= value <= 1:
            raise MathError(
                ErrorCode.DOMAIN_ERROR,
                f"{_SHOWN[name]} = {value} não é uma probabilidade: ela vai de 0 a 1 (0% a 100%).",
            )
    a, b = values.get("A"), values.get("B")
    both, either = values.get("A∩B"), values.get("A∪B")
    if both is not None:
        for name, single in (("A", a), ("B", b)):
            if single is not None and both > single:
                raise MathError(
                    ErrorCode.DOMAIN_ERROR,
                    f"P(A ∩ B) não pode ser maior que P({name}): A e B acontecerem juntos não é "
                    f"mais provável que só {name}.",
                )
        if a is not None and b is not None and both < a + b - 1:
            raise MathError(
                ErrorCode.DOMAIN_ERROR,
                f"Com P(A) = {a} e P(B) = {b}, P(A ∩ B) é pelo menos {a + b - 1}: a união não "
                "pode passar de 1.",
            )
    if either is not None:
        for name, single in (("A", a), ("B", b)):
            if single is not None and either < single:
                raise MathError(
                    ErrorCode.DOMAIN_ERROR,
                    f"P(A ∪ B) não pode ser menor que P({name}).",
                )
        if a is not None and b is not None and either > a + b:
            raise MathError(ErrorCode.DOMAIN_ERROR, "P(A ∪ B) não pode ser maior que P(A) + P(B).")
    if None not in (a, b, both, either) and a + b - both != either:
        raise MathError(
            ErrorCode.DOMAIN_ERROR,
            "Os valores não combinam: P(A ∪ B) precisa ser P(A) + P(B) − P(A ∩ B).",
        )


def _events(
    calculation: ProbabilityCalculation, values: dict[str, sp.Rational]
) -> tuple[sp.Rational, str, str, str]:
    a, b = values.get("A"), values.get("B")
    match calculation:
        case "complement" if a is not None:
            return 1 - a, r"P(\bar{A})", "P(não A)", r"P(\bar{A}) = 1 - P(A)"
        case "intersection" if a is not None and b is not None:
            return (
                a + b - values["A∪B"],
                r"P(A \cap B)",
                "P(A ∩ B)",
                r"P(A \cap B) = P(A) + P(B) - P(A \cup B)",
            )
        case "intersection_independent" if a is not None and b is not None:
            _check_independent(values, a * b)
            return a * b, r"P(A \cap B)", "P(A ∩ B)", r"P(A \cap B) = P(A) \cdot P(B)"
        case "union" if a is not None and b is not None:
            return (
                a + b - values["A∩B"],
                r"P(A \cup B)",
                "P(A ∪ B)",
                r"P(A \cup B) = P(A) + P(B) - P(A \cap B)",
            )
        case "union_independent" if a is not None and b is not None:
            _check_independent(values, a * b)
            return (
                a + b - a * b,
                r"P(A \cup B)",
                "P(A ∪ B)",
                r"P(A \cup B) = P(A) + P(B) - P(A) \cdot P(B)",
            )
        case "conditional" if b is not None:
            if b == 0:
                raise MathError(
                    ErrorCode.DOMAIN_ERROR,
                    "Com P(B) = 0, a probabilidade de A dado B não é definida.",
                )
            return (
                values["A∩B"] / b,
                r"P(A \mid B)",
                "P(A | B)",
                r"P(A \mid B) = \frac{P(A \cap B)}{P(B)}",
            )
    raise AssertionError(f"no formula for {calculation}")


def _check_independent(values: dict[str, sp.Rational], product: sp.Rational) -> None:
    both = values.get("A∩B")
    if both is not None and both != product:
        raise MathError(
            ErrorCode.DOMAIN_ERROR,
            f"A e B não são independentes: P(A ∩ B) = {both}, mas P(A) · P(B) = {product}.",
        )
    either = values.get("A∪B")
    if either is not None and either != values["A"] + values["B"] - product:
        raise MathError(
            ErrorCode.DOMAIN_ERROR,
            "A e B não são independentes: P(A ∪ B) não é P(A) + P(B) − P(A) · P(B).",
        )


# -- the binomial distribution --------------------------------------------------------------------


def _binomial(
    calculation: ProbabilityCalculation, values: dict[str, sp.Rational]
) -> tuple[sp.Rational | BinomialSummary, str, str, str]:
    n, p = _natural(values, "n", 1), values["p"]
    if n > MAX_TRIALS:
        raise MathError(
            ErrorCode.LIMIT_EXCEEDED, f"A binomial aceita até {MAX_TRIALS} tentativas (n)."
        )
    if not 0 <= p <= 1:
        raise MathError(
            ErrorCode.DOMAIN_ERROR,
            f"p = {p} não é uma probabilidade: ela vai de 0 a 1 (0% a 100%).",
        )
    _check_digits(n * math.log10(int(p.q)))
    if calculation == "binomial_summary":
        mean, variance = n * p, n * p * (1 - p)
        return (
            BinomialSummary(mean, variance, sp.sqrt(variance)),
            r"\mu",
            "μ",
            r"\mu = np, \ \sigma^2 = np(1 - p), \ \sigma = \sqrt{np(1 - p)}",
        )
    k = _natural(values, "k")
    if k > n:
        raise MathError(
            ErrorCode.DOMAIN_ERROR, f"k vai de 0 a n: com n = {n}, k = {k} não é possível."
        )

    def term(i: int) -> sp.Rational:
        return sp.binomial(n, i) * p**i * (1 - p) ** (n - i)

    term_latex = r"C(n, i) \, p^i \, (1 - p)^{n - i}"
    match calculation:
        case "binomial_exact":
            return (
                term(k),
                f"P(X = {k})",
                f"P(X = {k})",
                r"P(X = k) = C(n, k) \, p^k \, (1 - p)^{n - k}",
            )
        case "binomial_at_most":
            return (
                sp.Add(*(term(i) for i in range(k + 1))),
                rf"P(X \le {k})",
                f"P(X ≤ {k})",
                rf"P(X \le k) = \sum_{{i=0}}^{{k}} {term_latex}",
            )
    return (
        sp.Add(*(term(i) for i in range(k, n + 1))),
        rf"P(X \ge {k})",
        f"P(X ≥ {k})",
        rf"P(X \ge k) = \sum_{{i=k}}^{{n}} {term_latex}",
    )

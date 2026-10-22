"""Descriptive statistics of a list of numbers (Phase 10, ADR 0011).

The data are rational numbers (integers, decimals, fractions), so every
measure is exact: it is computed with Python's ``Fraction``. Only the standard
deviations, square roots of the variances, may be irrational; they are kept
exact (SymPy) and shown with a decimal approximation.

Conventions:

- variance and standard deviation are the population ones (÷ n); the sample
  ones (÷ n − 1) come along, under their own names, and need n ≥ 2;
- the median of an even number of values is the mean of the two central ones;
- the quartiles are the medians of the halves: Q1 of the lower half and Q3 of
  the upper half. With an odd count the central value (the median) is in neither
  half; the IQR is Q3 − Q1, and all three need at least 4 values (ADR 0031);
- the mode is every value with the highest frequency; if no value repeats,
  there is no mode (amodal);
- optional weights are positive integer frequencies, one per value: the data
  are expanded (each value repeated by its weight) and every measure uses the
  expanded list. The frequency table has one row per distinct value, with the
  exact relative frequency and the cumulative count (ADR 0032).
"""

from collections import Counter
from dataclasses import dataclass
from fractions import Fraction

import sympy as sp

from app.core.errors import ErrorCode, MathError
from app.core.limits import MAX_DATA_VALUES
from app.core.notices import Notice, NoticeCode
from app.formatting.expressions import plain
from app.math_engine.values import to_rational
from app.models.intents import Measure, StatisticsParams
from app.parsing import ParseResult, parse
from app.parsing.ast import Equation, ExpressionList, Node, System, variables
from app.parsing.build import ExpressionBuilder

SAMPLE: frozenset[Measure] = frozenset({"sample_variance", "sample_std"})
QUARTILES: frozenset[Measure] = frozenset({"q1", "q3", "iqr"})


@dataclass(frozen=True)
class FrequencyRow:
    value: Fraction
    frequency: int
    relative: Fraction  # frequency / total, exact
    cumulative: int


@dataclass(frozen=True)
class StatisticsOutcome:
    parsed: ParseResult
    items: tuple[Node, ...]  # the values as typed, for the verifier
    values: tuple[Fraction, ...]  # in the order typed
    weight_items: tuple[Node, ...]  # the weights as typed; empty without weights
    weights: tuple[int, ...] | None  # frequencies, one per value; None: raw data
    expanded: tuple[Fraction, ...]  # each value repeated by its weight (or once)
    measure: Measure | None  # None: the whole summary
    total: Fraction
    mean: Fraction
    median: Fraction
    q1: Fraction | None  # median of the lower half; None below 4 values
    q3: Fraction | None  # median of the upper half
    modes: tuple[Fraction, ...]  # ascending; empty when no value repeats
    minimum: Fraction
    maximum: Fraction
    variance: Fraction  # population (÷ n)
    sample_variance: Fraction | None  # ÷ (n − 1); None when n = 1
    frequency: tuple[FrequencyRow, ...]
    notices: tuple[Notice, ...]

    @property
    def count(self) -> int:
        return len(self.expanded)

    @property
    def weighted(self) -> bool:
        return self.weights is not None

    @property
    def spread(self) -> Fraction:
        return self.maximum - self.minimum

    @property
    def iqr(self) -> Fraction | None:
        return None if self.q1 is None or self.q3 is None else self.q3 - self.q1

    @property
    def std(self) -> sp.Expr:
        return sp.sqrt(to_rational(self.variance))

    @property
    def sample_std(self) -> sp.Expr | None:
        if self.sample_variance is None:
            return None
        return sp.sqrt(to_rational(self.sample_variance))


def statistics(params: StatisticsParams) -> StatisticsOutcome:
    parsed = parse(params.data, number_list=True)
    items = _items(parsed)
    builder = ExpressionBuilder()
    values = tuple(_value(item, builder) for item in items)

    weight_items: tuple[Node, ...] = ()
    weights: tuple[int, ...] | None = None
    weight_notices: tuple[Notice, ...] = ()
    if params.weights is not None:
        weight_parsed = parse(params.weights, number_list=True)
        weight_items = _items(weight_parsed, "Os pesos")
        raw_weights = tuple(_value(item, builder, "Os pesos") for item in weight_items)
        if len(raw_weights) != len(values):
            raise MathError(
                ErrorCode.INVALID_INPUT_FOR_INTENT,
                "A quantidade de pesos deve ser igual à quantidade de valores.",
            )
        if any(weight.denominator != 1 or weight <= 0 for weight in raw_weights):
            raise MathError(
                ErrorCode.INVALID_INPUT_FOR_INTENT,
                "Os pesos precisam ser inteiros positivos (frequências).",
            )
        weights = tuple(int(weight) for weight in raw_weights)
        if sum(weights) > MAX_DATA_VALUES:
            raise MathError(
                ErrorCode.LIMIT_EXCEEDED,
                f"A soma dos pesos não pode passar de {MAX_DATA_VALUES}.",
            )
        weight_notices = weight_parsed.notices

    if weights is None:
        expanded = values
    else:
        expanded = tuple(
            value for value, weight in zip(values, weights, strict=True) for _ in range(weight)
        )
    n = len(expanded)

    if params.measure in SAMPLE and n < 2:
        raise MathError(
            ErrorCode.INVALID_INPUT_FOR_INTENT,
            "A variância e o desvio padrão amostrais precisam de pelo menos 2 valores "
            "(dividem por n − 1).",
        )
    if params.measure in QUARTILES and n < 4:
        raise MathError(
            ErrorCode.INVALID_INPUT_FOR_INTENT,
            "Os quartis e o IQR precisam de pelo menos 4 valores.",
        )

    total = sum(expanded, Fraction(0))
    mean = total / n
    ordered = sorted(expanded)
    median = _median(ordered)
    q1, q3 = _quartiles(ordered)
    frequency = _frequency(expanded)
    highest = max(row.frequency for row in frequency)
    modes = tuple(row.value for row in frequency if row.frequency == highest) if highest > 1 else ()
    squares = sum(((v - mean) ** 2 for v in expanded), Fraction(0))

    notices = [*parsed.notices, *weight_notices, *builder.notices]
    if weights is not None:
        notices.append(
            Notice(
                NoticeCode.WEIGHTED_DATA,
                "Os pesos são frequências: cada valor entra no cálculo w vezes; "
                "n = soma dos pesos.",
            )
        )
    # The summary, always shown, has both σ and s: say what tells them apart.
    notices.append(
        Notice(
            NoticeCode.POPULATION_AND_SAMPLE,
            "σ e σ² são populacionais (dividem por n), para quando os dados são o grupo "
            "inteiro; s e s² são amostrais (dividem por n − 1), para quando os dados são "
            "uma amostra de um grupo maior.",
        )
    )
    if n == 1:
        notices.append(
            Notice(
                NoticeCode.SINGLE_VALUE,
                "Com um só valor, a variância e o desvio padrão amostrais não são definidos "
                "(dividem por n − 1 = 0).",
            )
        )
    if n < 4:
        notices.append(
            Notice(
                NoticeCode.QUARTILES_NOT_DEFINED,
                "Com menos de 4 valores, os quartis e o IQR não são definidos.",
            )
        )
    return StatisticsOutcome(
        parsed=parsed,
        items=items,
        values=values,
        weight_items=weight_items,
        weights=weights,
        expanded=expanded,
        measure=params.measure,
        total=total,
        mean=mean,
        median=median,
        q1=q1,
        q3=q3,
        modes=modes,
        minimum=ordered[0],
        maximum=ordered[-1],
        variance=squares / n,
        sample_variance=squares / (n - 1) if n > 1 else None,
        frequency=frequency,
        notices=tuple(notices),
    )


def _median(ordered: list[Fraction]) -> Fraction:
    middle = len(ordered) // 2
    return ordered[middle] if len(ordered) % 2 else (ordered[middle - 1] + ordered[middle]) / 2


def _quartiles(ordered: list[Fraction]) -> tuple[Fraction | None, Fraction | None]:
    """Q1 and Q3 as the medians of the halves (ADR 0031).

    With an odd count the central value (the median) belongs to neither half.
    Below four values there are no quartiles: Q1 and Q3 would be the extremes,
    which says nothing about the spread.
    """
    n = len(ordered)
    if n < 4:
        return None, None
    middle = n // 2
    lower = ordered[:middle]
    upper = ordered[middle:] if n % 2 == 0 else ordered[middle + 1 :]
    return _median(lower), _median(upper)


def _frequency(expanded: tuple[Fraction, ...]) -> tuple[FrequencyRow, ...]:
    """The frequency table of the expanded data, one row per distinct value."""
    counts = Counter(expanded)
    total = len(expanded)
    cumulative = 0
    rows: list[FrequencyRow] = []
    for value in sorted(counts):
        count = counts[value]
        cumulative += count
        rows.append(FrequencyRow(value, count, Fraction(count, total), cumulative))
    return tuple(rows)


def _items(parsed: ParseResult, label: str = "Os dados") -> tuple[Node, ...]:
    tree = parsed.tree
    if isinstance(tree, Equation | System):
        raise MathError(
            ErrorCode.INVALID_INPUT_FOR_INTENT,
            f"{label} são números separados por '; ' ou ', ', como 10, 20, 30, sem '='.",
            tree.position,
        )
    return tree.expressions if isinstance(tree, ExpressionList) else (tree,)


def _value(item: Node, builder: ExpressionBuilder, label: str = "Os dados") -> Fraction:
    if variables(item):
        raise MathError(
            ErrorCode.INVALID_INPUT_FOR_INTENT,
            f"{label} precisam ser números, sem variáveis.",
            item.position,
        )
    value = builder.build(item)
    if not value.is_Rational:
        raise MathError(
            ErrorCode.INVALID_INPUT_FOR_INTENT,
            f"{label} precisam ser números racionais (inteiros, decimais ou frações); "
            f"{plain(value)} não é.",
            item.position,
        )
    return Fraction(int(value.p), int(value.q))

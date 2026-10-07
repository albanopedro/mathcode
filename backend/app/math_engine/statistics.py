"""Descriptive statistics of a list of numbers (Phase 10, ADR 0011).

The data are rational numbers (integers, decimals, fractions), so every
measure is exact: it is computed with Python's ``Fraction``. Only the standard
deviations, square roots of the variances, may be irrational; they are kept
exact (SymPy) and shown with a decimal approximation.

Conventions:

- variance and standard deviation are the population ones (÷ n); the sample
  ones (÷ n − 1) come along, under their own names, and need n ≥ 2;
- the median of an even number of values is the mean of the two central ones;
- the mode is every value with the highest frequency; if no value repeats,
  there is no mode (amodal).
"""

from collections import Counter
from dataclasses import dataclass
from fractions import Fraction

import sympy as sp

from app.core.errors import ErrorCode, MathError
from app.core.notices import Notice, NoticeCode
from app.formatting.expressions import plain
from app.models.intents import Measure, StatisticsParams
from app.parsing import ParseResult, parse
from app.parsing.ast import Equation, ExpressionList, Node, System, variables
from app.parsing.build import ExpressionBuilder

SAMPLE: frozenset[Measure] = frozenset({"sample_variance", "sample_std"})


@dataclass(frozen=True)
class StatisticsOutcome:
    parsed: ParseResult
    items: tuple[Node, ...]  # the values as typed, for the verifier
    values: tuple[Fraction, ...]  # in the order typed
    measure: Measure | None  # None: the whole summary
    total: Fraction
    mean: Fraction
    median: Fraction
    modes: tuple[Fraction, ...]  # ascending; empty when no value repeats
    minimum: Fraction
    maximum: Fraction
    variance: Fraction  # population (÷ n)
    sample_variance: Fraction | None  # ÷ (n − 1); None when n = 1
    notices: tuple[Notice, ...]

    @property
    def count(self) -> int:
        return len(self.values)

    @property
    def spread(self) -> Fraction:
        return self.maximum - self.minimum

    @property
    def std(self) -> sp.Expr:
        return sp.sqrt(rational(self.variance))

    @property
    def sample_std(self) -> sp.Expr | None:
        if self.sample_variance is None:
            return None
        return sp.sqrt(rational(self.sample_variance))


def rational(value: Fraction) -> sp.Rational:
    return sp.Rational(value.numerator, value.denominator)


def statistics(params: StatisticsParams) -> StatisticsOutcome:
    parsed = parse(params.data, number_list=True)
    items = _items(parsed)
    builder = ExpressionBuilder()
    values = tuple(_value(item, builder) for item in items)
    n = len(values)

    if params.measure in SAMPLE and n < 2:
        raise MathError(
            ErrorCode.INVALID_INPUT_FOR_INTENT,
            "A variância e o desvio padrão amostrais precisam de pelo menos 2 valores "
            "(dividem por n − 1).",
        )

    total = sum(values, Fraction(0))
    mean = total / n
    ordered = sorted(values)
    middle = n // 2
    median = ordered[middle] if n % 2 else (ordered[middle - 1] + ordered[middle]) / 2
    counts = Counter(values)
    highest = max(counts.values())
    modes = tuple(sorted(v for v, c in counts.items() if c == highest)) if highest > 1 else ()
    squares = sum(((v - mean) ** 2 for v in values), Fraction(0))

    notices = [*parsed.notices, *builder.notices]
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
    return StatisticsOutcome(
        parsed=parsed,
        items=items,
        values=values,
        measure=params.measure,
        total=total,
        mean=mean,
        median=median,
        modes=modes,
        minimum=ordered[0],
        maximum=ordered[-1],
        variance=squares / n,
        sample_variance=squares / (n - 1) if n > 1 else None,
        notices=tuple(notices),
    )


def _items(parsed: ParseResult) -> tuple[Node, ...]:
    tree = parsed.tree
    if isinstance(tree, Equation | System):
        raise MathError(
            ErrorCode.INVALID_INPUT_FOR_INTENT,
            "Os dados são números separados por '; ' ou ', ', como 10, 20, 30, sem '='.",
            tree.position,
        )
    return tree.expressions if isinstance(tree, ExpressionList) else (tree,)


def _value(item: Node, builder: ExpressionBuilder) -> Fraction:
    if variables(item):
        raise MathError(
            ErrorCode.INVALID_INPUT_FOR_INTENT,
            "Os dados precisam ser números, sem variáveis.",
            item.position,
        )
    value = builder.build(item)
    if not value.is_Rational:
        raise MathError(
            ErrorCode.INVALID_INPUT_FOR_INTENT,
            f"Os dados precisam ser números racionais (inteiros, decimais ou frações); "
            f"{plain(value)} não é.",
            item.position,
        )
    return Fraction(int(value.p), int(value.q))

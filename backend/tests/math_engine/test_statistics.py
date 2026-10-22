"""Descriptive statistics: engine, verification and presentation (ADR 0011)."""

from dataclasses import replace
from fractions import Fraction as F

import pytest
import sympy as sp

from app.core.errors import ErrorCode, MathError
from app.formatting.results import present_statistics
from app.math_engine.statistics import FrequencyRow, StatisticsOutcome, statistics
from app.models.intents import StatisticsParams
from app.models.result import VerificationStatus as S
from app.verification.statistics import verify_statistics


def stats(data: str, measure: str | None = None) -> StatisticsOutcome:
    return statistics(StatisticsParams(data=data, measure=measure))  # type: ignore[arg-type]


def weighted(data: str, weights: str, measure: str | None = None) -> StatisticsOutcome:
    return statistics(
        StatisticsParams(data=data, weights=weights, measure=measure)  # type: ignore[arg-type]
    )


# -- the measures -------------------------------------------------------------------------------


def test_classic_example() -> None:
    """2, 4, 4, 4, 5, 5, 7, 9: mean 5, population σ = 2 (the textbook example)."""
    o = stats("2, 4, 4, 4, 5, 5, 7, 9")
    assert o.count == 8
    assert o.total == 40
    assert o.mean == 5
    assert o.median == F(9, 2)  # even count: mean of the two central values
    assert (o.q1, o.q3, o.iqr) == (4, 6, 2)  # medians of [2, 4, 4, 4] and [5, 5, 7, 9]
    assert o.modes == (F(4),)
    assert (o.minimum, o.maximum, o.spread) == (2, 9, 7)
    assert o.variance == 4
    assert o.std == 2
    assert o.sample_variance == F(32, 7)
    assert o.sample_std == 4 * sp.sqrt(14) / 7


def test_exact_with_decimals_and_fractions() -> None:
    o = stats("0.1, 0.2, 1/3")
    assert o.mean == F(19, 90)  # no rounding: 0.1 + 0.2 + 1/3 = 19/30


def test_quartiles_even_count() -> None:
    o = stats("1, 2, 3, 4")
    assert (o.q1, o.median, o.q3, o.iqr) == (F(3, 2), F(5, 2), F(7, 2), 2)


def test_quartiles_odd_count_leave_the_median_out_of_both_halves() -> None:
    o = stats("1, 2, 3, 4, 5, 6, 7, 8, 9")
    assert (o.q1, o.median, o.q3, o.iqr) == (F(5, 2), 5, F(15, 2), 5)


@pytest.mark.parametrize("data", ["5", "1, 2", "1, 2, 3"])
def test_quartiles_need_four_values(data: str) -> None:
    o = stats(data)
    assert (o.q1, o.q3, o.iqr) == (None, None, None)
    assert "QUARTILES_NOT_DEFINED" in [n.code for n in o.notices]
    with pytest.raises(MathError) as exc:
        stats(data, "q1")
    assert "pelo menos 4 valores" in exc.value.message


@pytest.mark.parametrize(
    ("data", "modes"),
    [
        ("1, 2, 3", ()),  # no value repeats: no mode
        ("1, 1, 2, 2, 3", (F(1), F(2))),  # two modes
        ("1, 1, 2, 2", (F(1), F(2))),  # every value repeats equally: both are modes
        ("7, 7, 7", (F(7),)),
    ],
)
def test_modes(data: str, modes: tuple[F, ...]) -> None:
    assert stats(data).modes == modes


def test_weighted_mean_is_the_mean_of_the_expanded_data() -> None:
    o = weighted("7, 8, 9", "2, 3, 5", "mean")
    assert o.weighted
    assert o.count == 10
    assert o.values == (7, 8, 9)
    assert o.expanded == (7, 7, 8, 8, 8, 9, 9, 9, 9, 9)
    assert o.total == 83
    assert o.mean == F(83, 10)
    assert o.median == F(17, 2)
    assert o.modes == (F(9),)
    assert o.frequency == (
        FrequencyRow(F(7), 2, F(1, 5), 2),
        FrequencyRow(F(8), 3, F(3, 10), 5),
        FrequencyRow(F(9), 5, F(1, 2), 10),
    )
    assert "WEIGHTED_DATA" in [n.code for n in o.notices]


def test_frequency_table_of_raw_data() -> None:
    o = stats("1, 2, 2, 3")
    assert o.frequency == (
        FrequencyRow(F(1), 1, F(1, 4), 1),
        FrequencyRow(F(2), 2, F(1, 2), 3),
        FrequencyRow(F(3), 1, F(1, 4), 4),
    )


def test_order_does_not_matter_but_is_kept() -> None:
    o = stats("9; 2; 5")
    assert o.values == (9, 2, 5)
    assert o.median == 5


def test_a_single_value() -> None:
    o = stats("5")
    assert (o.mean, o.median, o.variance, o.std) == (5, 5, 0, 0)
    assert o.sample_variance is None and o.sample_std is None
    assert o.q1 is None and o.q3 is None and o.iqr is None
    assert "SINGLE_VALUE" in [n.code for n in o.notices]
    assert "QUARTILES_NOT_DEFINED" in [n.code for n in o.notices]


def test_population_and_sample_notice_always_comes_with_the_summary() -> None:
    for measure in (None, "std", "mean", "mode"):
        assert "POPULATION_AND_SAMPLE" in [n.code for n in stats("1, 2", measure).notices]


@pytest.mark.parametrize(
    ("data", "shown"),
    [
        ("9,5; 7; 1/4", ["9.5", "7", "0.25"]),
        ("1/3, -0.05, -2.5, 100", ["1/3", "-0.05", "-2.5", "100"]),
        ("-1/8", ["-0.125"]),
    ],
)
def test_data_are_shown_as_typed_decimals(data: str, shown: list[str]) -> None:
    assert present_statistics(stats(data)).details["data"] == shown


@pytest.mark.parametrize(
    ("data", "measure", "message"),
    [
        ("5", "sample_std", "pelo menos 2 valores"),
        ("5", "iqr", "pelo menos 4 valores"),
        ("1, 2, 3", "q3", "pelo menos 4 valores"),
        ("x, 2", None, "sem variáveis"),
        ("sqrt(2), 1", None, "racionais"),
        ("pi, 1", None, "racionais"),
        ("1, 2 = 3", None, "sem '='"),
        ("10,20,30", None, "ambíguo"),
    ],
)
def test_invalid_data(data: str, measure: str | None, message: str) -> None:
    with pytest.raises(MathError) as exc:
        stats(data, measure)
    assert message in exc.value.message


def test_error_position_points_at_the_bad_value() -> None:
    with pytest.raises(MathError) as exc:
        stats("1, 2, x")
    assert exc.value.position == 6


def test_too_many_values() -> None:
    with pytest.raises(MathError) as exc:
        stats(";".join(["1"] * 201))
    assert exc.value.code is ErrorCode.LIMIT_EXCEEDED


@pytest.mark.parametrize(
    ("weights", "message"),
    [
        ("2, 3", "quantidade de pesos"),
        ("2, 3, 0", "inteiros positivos"),
        ("2, 3, -1", "inteiros positivos"),
        ("2, 3, 2.5", "inteiros positivos"),
        ("2, 3, x", "sem variáveis"),
        ("2, 3, sqrt(2)", "racionais"),
    ],
)
def test_invalid_weights(weights: str, message: str) -> None:
    with pytest.raises(MathError) as exc:
        weighted("7, 8, 9", weights)
    assert message in exc.value.message


def test_too_many_weighted_observations() -> None:
    with pytest.raises(MathError) as exc:
        weighted("1, 2", "200, 1")
    assert exc.value.code is ErrorCode.LIMIT_EXCEEDED


# -- verification ---------------------------------------------------------------------------------


@pytest.mark.parametrize(
    "data", ["2, 4, 4, 4, 5, 5, 7, 9", "0.1, 0.2, 1/3", "5", "-3, 1,5, 1/2, 0", "1, 1, 2, 2"]
)
def test_verified_exactly_by_two_methods(data: str) -> None:
    report = verify_statistics(stats(data))
    assert report.status is S.VERIFIED_SYMBOLIC
    assert report.methods == ["comparison", "symbolic"]
    assert "módulo statistics" in report.checks[1].message


@pytest.mark.parametrize(
    "tamper",
    [
        lambda o: replace(o, mean=o.mean + F(1, 10**9)),
        lambda o: replace(o, median=o.maximum),
        lambda o: replace(o, modes=()),
        lambda o: replace(o, variance=o.variance * 2),
        lambda o: replace(o, sample_variance=o.variance),  # ÷ n instead of ÷ (n − 1)
        lambda o: replace(o, q1=o.q1 + F(1, 10**9)),
        lambda o: replace(o, q3=o.q3 + F(1, 10**9)),
        lambda o: replace(o, total=o.total + 1),
        lambda o: replace(o, minimum=o.minimum - 1),
        lambda o: replace(o, values=(*o.values[:-1], o.values[-1] + 1)),  # a value misread
    ],
)
def test_catches_any_wrong_measure(tamper: object) -> None:
    outcome = stats("2, 4, 4, 4, 5, 5, 7, 9")
    report = verify_statistics(tamper(outcome))  # type: ignore[operator]
    assert report.status is S.FAILED


def test_values_that_are_not_plain_fractions_are_read_by_the_engine_only() -> None:
    report = verify_statistics(stats("sqrt(4), 3"))
    assert report.status is S.VERIFIED_SYMBOLIC
    assert report.checks[0].outcome == "inconclusive"


def test_weighted_data_is_verified() -> None:
    report = verify_statistics(weighted("7, 8, 9", "2, 3, 5"))
    assert report.status is S.VERIFIED_SYMBOLIC
    assert any("tabela de frequências" in check.message for check in report.checks)


@pytest.mark.parametrize(
    "tamper",
    [
        lambda o: replace(o, weights=(2, 3, 6)),
        lambda o: replace(o, expanded=o.expanded[:-1]),
        lambda o: replace(o, frequency=o.frequency[:-1]),
        lambda o: replace(o, mean=o.mean + F(1, 10**9)),
    ],
)
def test_catches_a_wrong_weighted_result(tamper: object) -> None:
    outcome = weighted("7, 8, 9", "2, 3, 5")
    report = verify_statistics(tamper(outcome))  # type: ignore[operator]
    assert report.status is S.FAILED


# -- presentation ---------------------------------------------------------------------------------


def test_summary_shows_the_mean_and_every_measure() -> None:
    p = present_statistics(stats("10, 20, 30"))
    assert p.result.plain == "média = 20"
    assert p.result.latex == r"\bar{x} = 20"
    names = [m["name"] for m in p.details["measures"]]
    assert names == [
        "count",
        "sum",
        "mean",
        "median",
        "q1",
        "q3",
        "iqr",
        "mode",
        "min",
        "max",
        "range",
        "variance",
        "std",
        "sample_variance",
        "sample_std",
    ]
    std = next(m for m in p.details["measures"] if m["name"] == "std")
    assert std == {
        "name": "std",
        "label": "Desvio padrão populacional",
        "symbol": r"\sigma",
        "plain": "10*sqrt(6)/3",
        "latex": r"\frac{10 \sqrt{6}}{3}",
        "approx": "8.16496580927726",
    }
    assert p.details["data"] == ["10", "20", "30"]
    assert p.details["measure"] is None
    assert p.details["weighted"] is False
    assert p.details["frequency"] == [
        {"value": "10", "frequency": 1, "relative": "1/3", "cumulative": 1},
        {"value": "20", "frequency": 1, "relative": "1/3", "cumulative": 2},
        {"value": "30", "frequency": 1, "relative": "1/3", "cumulative": 3},
    ]


def test_requested_measure_is_the_result() -> None:
    p = present_statistics(stats("2, 4, 4, 4, 5, 5, 7, 9", "std"))
    assert (p.result.plain, p.result.latex) == ("σ = 2", r"\sigma = 2")
    assert p.details["measure"] == "std"


def test_weighted_summary_says_it_is_weighted() -> None:
    p = present_statistics(weighted("7, 8, 9", "2, 3, 5"))
    assert p.result.plain == "média ponderada = 83/10"
    assert p.result.latex == r"\bar{x}_w = \frac{83}{10}"
    assert p.result.approx == "8.3"
    assert p.details["weighted"] is True
    assert p.details["sorted"] == ["7", "7", "8", "8", "8", "9", "9", "9", "9", "9"]
    mean = next(m for m in p.details["measures"] if m["name"] == "mean")
    assert mean["label"] == "Média ponderada"
    assert mean["symbol"] == r"\bar{x}_w"
    assert p.details["frequency"] == [
        {"value": "7", "frequency": 2, "relative": "1/5", "cumulative": 2},
        {"value": "8", "frequency": 3, "relative": "3/10", "cumulative": 5},
        {"value": "9", "frequency": 5, "relative": "1/2", "cumulative": 10},
    ]


def test_frequency_measure_shows_the_table_not_a_number() -> None:
    p = present_statistics(stats("1, 2, 2, 3", "frequency"))
    assert p.result.plain == "tabela de frequências (n = 4)"
    assert p.result.latex == r"\text{Tabela de frequências}"
    assert p.result.approx is None
    assert p.details["measure"] == "frequency"
    assert p.details["frequency"] == [
        {"value": "1", "frequency": 1, "relative": "1/4", "cumulative": 1},
        {"value": "2", "frequency": 2, "relative": "1/2", "cumulative": 3},
        {"value": "3", "frequency": 1, "relative": "1/4", "cumulative": 4},
    ]


@pytest.mark.parametrize(
    ("measure", "plain", "latex"),
    [
        ("q1", "Q₁ = 4", r"Q_{1} = 4"),
        ("q3", "Q₃ = 6", r"Q_{3} = 6"),
        ("iqr", "IQR = 2", r"\mathrm{IQR} = 2"),
    ],
)
def test_requested_quartile_is_the_result(measure: str, plain: str, latex: str) -> None:
    p = present_statistics(stats("2, 4, 4, 4, 5, 5, 7, 9", measure))
    assert (p.result.plain, p.result.latex) == (plain, latex)
    assert p.details["measure"] == measure


def test_quartiles_are_empty_below_four_values() -> None:
    p = present_statistics(stats("1, 2, 3"))
    for name in ("q1", "q3", "iqr"):
        entry = next(m for m in p.details["measures"] if m["name"] == name)
        assert entry["plain"] is None and entry["latex"] is None and entry["approx"] is None


def test_no_mode_is_said_in_words() -> None:
    p = present_statistics(stats("1, 2, 3", "mode"))
    assert p.result.plain == "moda: nenhuma (nenhum valor se repete)"
    mode = next(m for m in p.details["measures"] if m["name"] == "mode")
    assert mode["plain"] == "nenhuma"


def test_undefined_sample_measures_are_empty() -> None:
    p = present_statistics(stats("5"))
    sample = next(m for m in p.details["measures"] if m["name"] == "sample_std")
    assert sample["plain"] is None and sample["latex"] is None

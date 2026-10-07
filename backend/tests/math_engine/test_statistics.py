"""Descriptive statistics: engine, verification and presentation (ADR 0011)."""

from dataclasses import replace
from fractions import Fraction as F

import pytest
import sympy as sp

from app.core.errors import ErrorCode, MathError
from app.formatting.results import present_statistics
from app.math_engine.statistics import StatisticsOutcome, statistics
from app.models.intents import StatisticsParams
from app.models.result import VerificationStatus as S
from app.verification.statistics import verify_statistics


def stats(data: str, measure: str | None = None) -> StatisticsOutcome:
    return statistics(StatisticsParams(data=data, measure=measure))  # type: ignore[arg-type]


# -- the measures -------------------------------------------------------------------------------


def test_classic_example() -> None:
    """2, 4, 4, 4, 5, 5, 7, 9: mean 5, population σ = 2 (the textbook example)."""
    o = stats("2, 4, 4, 4, 5, 5, 7, 9")
    assert o.count == 8
    assert o.total == 40
    assert o.mean == 5
    assert o.median == F(9, 2)  # even count: mean of the two central values
    assert o.modes == (F(4),)
    assert (o.minimum, o.maximum, o.spread) == (2, 9, 7)
    assert o.variance == 4
    assert o.std == 2
    assert o.sample_variance == F(32, 7)
    assert o.sample_std == 4 * sp.sqrt(14) / 7


def test_exact_with_decimals_and_fractions() -> None:
    o = stats("0.1, 0.2, 1/3")
    assert o.mean == F(19, 90)  # no rounding: 0.1 + 0.2 + 1/3 = 19/30


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


def test_order_does_not_matter_but_is_kept() -> None:
    o = stats("9; 2; 5")
    assert o.values == (9, 2, 5)
    assert o.median == 5


def test_a_single_value() -> None:
    o = stats("5")
    assert (o.mean, o.median, o.variance, o.std) == (5, 5, 0, 0)
    assert o.sample_variance is None and o.sample_std is None
    assert "SINGLE_VALUE" in [n.code for n in o.notices]


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


def test_requested_measure_is_the_result() -> None:
    p = present_statistics(stats("2, 4, 4, 4, 5, 5, 7, 9", "std"))
    assert (p.result.plain, p.result.latex) == ("σ = 2", r"\sigma = 2")
    assert p.details["measure"] == "std"


def test_no_mode_is_said_in_words() -> None:
    p = present_statistics(stats("1, 2, 3", "mode"))
    assert p.result.plain == "moda: nenhuma (nenhum valor se repete)"
    mode = next(m for m in p.details["measures"] if m["name"] == "mode")
    assert mode["plain"] == "nenhuma"


def test_undefined_sample_measures_are_empty() -> None:
    p = present_statistics(stats("5"))
    sample = next(m for m in p.details["measures"] if m["name"] == "sample_std")
    assert sample["plain"] is None and sample["latex"] is None

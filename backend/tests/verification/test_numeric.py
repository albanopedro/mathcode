from itertools import islice

import pytest
import sympy as sp
from mpmath import mp, mpf

from app.parsing import parse
from app.parsing.ast import Equation, Node
from app.parsing.build import symbol
from app.verification.numeric import (
    BASE_PRECISION,
    MAX_PRECISION,
    OutsideDomain,
    TooLarge,
    agrees,
    evaluate,
    sample_points,
    to_mpf,
)


def tree(source: str) -> Node:
    node = parse(source).tree
    assert not isinstance(node, Equation)
    return node


def exact(text: str) -> mpf:
    """The expected value at the evaluator's precision (mpmath defaults to 15 digits)."""
    with mp.workdps(BASE_PRECISION):
        return mpf(text)


def matches(source: str, expected: str) -> bool:
    return agrees(evaluate(tree(source)), exact(expected))


@pytest.mark.parametrize(
    ("source", "expected"),
    [
        ("2 + 3*4", "14"),
        ("2^3^2", "512"),
        ("-2^2", "-4"),
        ("(-8)^(1/3)", "-2"),
        ("(-8)^(2/3)", "4"),
        ("(-32)^0.2", "-2"),
        ("log(1000)", "3"),
        ("log(8; 2)", "3"),
        ("sin(30°)", "0.5"),
        ("abs(-7)", "7"),
        ("√16", "4"),
        ("0.1 + 0.2", "0.3"),
    ],
)
def test_evaluates_with_the_same_conventions(source: str, expected: str) -> None:
    assert matches(source, expected)


def test_evaluates_variables_at_exact_decimal_points() -> None:
    assert agrees(evaluate(tree("x^2 + y"), {"x": "1.5", "y": "1"}), exact("3.25"))


@pytest.mark.parametrize(
    ("source", "expected"),
    [
        ("10^3999 + 1 - 10^3999", "1"),
        ("1/(10^100 + 1 - 10^100)", "1"),
        ("(10^50 + 7) - 10^50", "7"),
    ],
)
def test_precision_grows_with_the_numbers(source: str, expected: str) -> None:
    """A fixed 50-digit evaluator would get 0 here (or divide by zero)."""
    assert matches(source, expected)


def test_strict_enough_to_catch_an_error_in_the_eleventh_digit() -> None:
    assert not matches("sqrt(2)", "1.4142135623")


def test_cancellation_to_zero_is_within_the_error_bound() -> None:
    assert matches("sqrt(2)^2 - 2", "0")
    assert matches("sin(pi)", "0")


@pytest.mark.parametrize(
    "source",
    ["1/0", "0^0", "0^(-1)", "sqrt(-1)", "(-4)^(1/2)", "ln(0)", "log(-1)", "asin(2)", "log(8; 1)"],
)
def test_outside_domain(source: str) -> None:
    with pytest.raises(OutsideDomain):
        evaluate(tree(source))


def test_refuses_intermediate_values_too_large_to_bound() -> None:
    with pytest.raises(TooLarge):
        evaluate(tree("exp(exp(10)) - exp(exp(10))"))  # e^22026 has ~9566 digits
    assert MAX_PRECISION < 9566


def test_to_mpf() -> None:
    x = symbol("x")
    value = to_mpf(sp.sqrt(2))
    with mp.workdps(BASE_PRECISION):
        assert value is not None and abs(value - mp.sqrt(2)) < mpf("1e-45")
    assert to_mpf(x**2, {x: "1.5"}) == mpf("2.25")
    assert to_mpf(sp.I) is None
    assert to_mpf(sp.zoo) is None


def test_sample_points_are_reproducible() -> None:
    first = list(islice(sample_points("x + 1", ["x"]), 5))
    second = list(islice(sample_points("x + 1", ["x"]), 5))
    other = list(islice(sample_points("x + 2", ["x"]), 5))
    assert first == second
    assert first != other
    assert all(-10 <= float(p["x"]) <= 10 for p in first)

"""Calculus verifiers: confirm correct results and catch tampered ones."""

from dataclasses import replace

import pytest
import sympy as sp

from app.math_engine.calculus import (
    DerivativeOutcome,
    IntegralOutcome,
    LimitKind,
    LimitOutcome,
    derivative,
    integral,
    limit,
)
from app.models.intents import DerivativeParams, IntegralParams, LimitParams
from app.models.result import VerificationStatus as S
from app.parsing.build import symbol
from app.verification.calculus import verify_derivative, verify_integral, verify_limit

x = symbol("x")


def d(expression: str, order: int = 1) -> DerivativeOutcome:
    return derivative(DerivativeParams(expression=expression, order=order))


def i(expression: str, lower: str | None = None, upper: str | None = None) -> IntegralOutcome:
    return integral(IntegralParams(expression=expression, lower=lower, upper=upper))


def lim(expression: str, point: str, side: str = "both") -> LimitOutcome:
    return limit(LimitParams(expression=expression, point=point, side=side))  # type: ignore[arg-type]


# -- derivative ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("expression", "order"),
    [("x^2 + 3x", 1), ("x^2 sin(x)", 3), ("e^(2x)", 10), ("ln(x)", 1), ("abs(x)", 1)],
)
def test_derivatives_are_verified_numerically(expression: str, order: int) -> None:
    report = verify_derivative(d(expression, order))
    assert report.status is S.VERIFIED_NUMERIC
    assert "diferenças finitas" in report.checks[0]


def test_derivative_with_another_variable() -> None:
    outcome = derivative(DerivativeParams(expression="x y^2", variable="y"))
    assert verify_derivative(outcome).status is S.VERIFIED_NUMERIC


def test_derivative_catches_a_wrong_result() -> None:
    outcome = d("x^2 sin(x)")
    wrong = replace(outcome, result=2 * x * sp.sin(x))  # forgot the product rule
    assert verify_derivative(wrong).status is S.FAILED


def test_derivative_catches_a_small_error() -> None:
    outcome = d("x^3")
    wrong = replace(outcome, result=3 * x**2 * sp.Rational(1000001, 1000000))
    assert verify_derivative(wrong).status is S.FAILED


# -- indefinite integral --------------------------------------------------------------------


@pytest.mark.parametrize("expression", ["x^2", "sen(x)", "1/x", "tan(x)", "exp(-x^2)"])
def test_antiderivatives_are_verified_symbolically(expression: str) -> None:
    assert verify_integral(i(expression)).status is S.VERIFIED_SYMBOLIC


def test_absolute_value_in_log_is_explained() -> None:
    report = verify_integral(i("1/x"))
    assert any("ln|u|" in check for check in report.checks)


def test_antiderivative_catches_a_wrong_result() -> None:
    outcome = i("x^2")
    assert verify_integral(replace(outcome, antiderivative=x**3)).status is S.FAILED


def test_antiderivative_valid_only_for_positive_x_fails() -> None:
    """SymPy's log(x) for ∫1/x is not real for x < 0, where 1/x is defined."""
    outcome = i("1/x")
    raw = replace(outcome, antiderivative=sp.log(x), raw_antiderivative=sp.log(x))
    assert verify_integral(raw).status is S.FAILED


# -- definite integral ----------------------------------------------------------------------


@pytest.mark.parametrize(
    ("expression", "lower", "upper"),
    [
        ("x^2", "0", "1"),
        ("sen(x)", "0", "pi"),
        ("1/x^2", "1", "inf"),
        ("e^(-x^2)", "-inf", "inf"),
        ("1/sqrt(x)", "0", "1"),
    ],
)
def test_definite_integrals_are_verified_by_quadrature(
    expression: str, lower: str, upper: str
) -> None:
    report = verify_integral(i(expression, lower, upper))
    assert report.status is S.VERIFIED_NUMERIC
    assert "tanh-sinh" in report.checks[0]


def test_definite_integral_catches_a_wrong_value() -> None:
    outcome = i("x^2", "0", "1")
    assert verify_integral(replace(outcome, value=sp.Rational(1, 2))).status is S.FAILED


def test_divergence_is_not_claimed_as_verified() -> None:
    assert verify_integral(i("1/x", "1", "inf")).status is S.UNVERIFIED


# -- limit -----------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("expression", "point", "side"),
    [
        ("sin(x)/x", "0", "both"),
        ("(1 + 1/x)^x", "inf", "both"),
        ("1/x^2", "0", "both"),
        ("1/x", "0", "both"),  # no limit: -∞ on the left, +∞ on the right
        ("sqrt(x)", "0", "both"),  # only the right side exists
        ("abs(x)/x", "0", "left"),
        ("tan(x)", "pi/2", "both"),
    ],
)
def test_limits_are_at_most_partial(expression: str, point: str, side: str) -> None:
    report = verify_limit(lim(expression, point, side))
    assert report.status is S.PARTIAL
    assert "não prova" in report.checks[-1]


def test_slow_convergence_is_inconclusive_not_verified() -> None:
    assert verify_limit(lim("1/log(x)", "inf")).status is S.UNVERIFIED


def test_oscillation_is_not_verified() -> None:
    assert verify_limit(lim("sin(1/x)", "0")).status is S.UNVERIFIED


def test_limit_catches_a_wrong_value() -> None:
    outcome = lim("sin(x)/x", "0")
    assert verify_limit(replace(outcome, value=sp.Integer(2))).status is S.FAILED


def test_limit_catches_a_wrong_infinity() -> None:
    outcome = lim("sin(x)/x", "0")
    wrong = replace(outcome, kind=LimitKind.INFINITE, value=sp.oo)
    assert verify_limit(wrong).status is S.FAILED


def test_limit_catches_wrong_sides() -> None:
    outcome = lim("abs(x)/x", "0")
    swapped = replace(outcome, left=sp.Integer(1), right=sp.Integer(-1))
    assert verify_limit(swapped).status is S.FAILED

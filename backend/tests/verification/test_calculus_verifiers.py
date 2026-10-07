"""Calculus verifiers: confirm correct results and catch tampered ones."""

import time
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
from app.verification import calculus as calculus_module
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
    [
        ("x^2 + 3x", 1),
        ("x^2 sin(x)", 3),
        ("e^(2x)", 10),
        ("ln(x)", 1),
        ("abs(x)", 1),
        ("x^x", 2),
        ("asin(x/2) + atan(x^2)", 1),
        ("log(x; 2)", 1),
    ],
)
def test_derivatives_are_verified_by_two_methods(expression: str, order: int) -> None:
    """Finite differences (numeric) and a second differentiator (textbook rules)."""
    report = verify_derivative(d(expression, order))
    assert report.status is S.VERIFIED_SYMBOLIC
    assert report.methods == ["numeric", "comparison"]
    assert "diferenças finitas" in report.checks[0].message
    assert "segundo derivador" in report.checks[1].message


@pytest.mark.parametrize(
    ("expression", "order"),
    [("sin(x)^10 cos(x)^10", 10), ("1/(1 + x^2)", 10), ("sin(5x)", 10), ("e^(x^2)", 8)],
)
def test_high_order_finite_differences_alone_pass(
    expression: str, order: int, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A fixed step of 10^-5 gave a relative error of 3.5e-7 at order 10 (Phase 9 fix)."""
    monkeypatch.setattr(calculus_module, "differentiate", lambda *args: None)
    report = verify_derivative(d(expression, order))
    assert report.status is S.VERIFIED_NUMERIC
    assert report.checks[0].outcome == "passed"


def test_derivative_outside_the_second_differentiator_is_numeric() -> None:
    """The 2nd derivative of abs(x^2 - 1) involves sign(u), outside the rule table."""
    report = verify_derivative(d("abs(x^2 - 1)", 2))
    assert report.status is S.VERIFIED_NUMERIC
    assert report.checks[1].outcome == "inconclusive"
    assert "sign" in report.checks[1].message


def test_derivative_with_another_variable() -> None:
    outcome = derivative(DerivativeParams(expression="x y^2", variable="y"))
    assert verify_derivative(outcome).status is S.VERIFIED_SYMBOLIC


def test_a_slow_comparison_is_inconclusive_not_fatal(monkeypatch: pytest.MonkeyPatch) -> None:
    def slow(*args: object) -> None:
        time.sleep(5)

    monkeypatch.setattr(calculus_module, "differentiate", slow)
    monkeypatch.setattr(calculus_module, "COMPARISON_SECONDS", 0.05)

    report = verify_derivative(d("x^2 sin(x)"))

    assert report.status is S.VERIFIED_NUMERIC
    assert report.checks[1].outcome == "inconclusive"
    assert "não terminou a tempo" in report.checks[1].message


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
    assert any("ln|u|" in check.message for check in report.checks)


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
        ("sen(x)", "0", "pi"),
        ("1/x^2", "1", "inf"),  # infinite bound: outside Newton–Leibniz here
        ("e^(-x^2)", "-inf", "inf"),
        ("1/sqrt(x)", "0", "1"),
    ],
)
def test_definite_integrals_are_verified_by_quadrature(
    expression: str, lower: str, upper: str
) -> None:
    report = verify_integral(i(expression, lower, upper))
    assert report.status is S.VERIFIED_NUMERIC
    assert report.methods == ["numeric"]
    assert "tanh-sinh" in report.checks[0].message


@pytest.mark.parametrize(
    ("expression", "lower", "upper", "value"),
    [
        ("x^2", "0", "1", sp.Rational(1, 3)),
        ("x^3 - 2x", "-1", "3", sp.Integer(12)),
        ("1/(x^2 + 1)", "0", "1", sp.pi / 4),
        ("1/x", "1", "2", sp.log(2)),
        ("1/x", "-2", "-1", -sp.log(2)),  # ln|x|: a real antiderivative on [-2, -1]
        ("(x^2 + 1)/(x - 3)", "0", "2", 8 - 10 * sp.log(3)),
        ("1/(x^2 + x + 1)", "0", "1", sp.sqrt(3) * sp.pi / 9),
    ],
)
def test_newton_leibniz_proves_definite_integrals(
    expression: str, lower: str, upper: str, value: sp.Expr
) -> None:
    outcome = i(expression, lower, upper)
    assert sp.simplify(outcome.value - value) == 0
    report = verify_integral(outcome)
    assert report.status is S.VERIFIED_SYMBOLIC
    assert report.methods == ["numeric", "comparison"]
    assert "Newton–Leibniz" in report.checks[1].message


def test_definite_integral_catches_a_wrong_value() -> None:
    outcome = i("x^2", "0", "1")
    report = verify_integral(replace(outcome, value=sp.Rational(1, 2)))
    assert report.status is S.FAILED


def test_newton_leibniz_alone_catches_a_tiny_error() -> None:
    """1/3 + 10^-12 passes quadrature's 10^-10 tolerance, not the exact comparison."""
    outcome = i("x^2", "0", "1")
    report = verify_integral(replace(outcome, value=sp.Rational(1, 3) + sp.Rational(1, 10**12)))
    assert report.status is S.FAILED
    assert report.checks[0].outcome == "passed"  # quadrature could not tell
    assert report.checks[1].outcome == "failed"


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
def test_limits_without_continuity_are_at_most_partial(
    expression: str, point: str, side: str
) -> None:
    report = verify_limit(lim(expression, point, side))
    assert report.status is S.PARTIAL
    assert report.reason == "numeric_evidence_only"
    assert "não prova" in report.checks[-1].message


@pytest.mark.parametrize(
    ("expression", "point", "side"),
    [
        ("x^2 + 1", "2", "both"),
        ("sin(x)", "pi/6", "both"),
        ("ln(x)", "e", "both"),
        ("sqrt(x)", "4", "left"),
        ("(x^2 - 1)/(x + 1)", "3", "both"),
        ("tan(x)", "pi/4", "right"),
    ],
)
def test_limits_at_continuity_points_are_proved(expression: str, point: str, side: str) -> None:
    report = verify_limit(lim(expression, point, side))
    assert report.status is S.VERIFIED_SYMBOLIC
    assert report.checks[0].kind == "comparison"
    assert "contínua" in report.checks[0].message


def test_continuity_catches_a_wrong_limit() -> None:
    outcome = lim("x^2 + 1", "2")
    report = verify_limit(replace(outcome, value=sp.Integer(6)))
    assert report.status is S.FAILED
    assert report.checks[0].kind == "comparison"


def test_continuity_catches_a_false_nonexistent_limit() -> None:
    outcome = lim("x^2 + 1", "2")
    nonexistent = replace(
        outcome, kind=LimitKind.NONEXISTENT, value=None, left=sp.Integer(5), right=sp.Integer(4)
    )
    assert verify_limit(nonexistent).status is S.FAILED


def test_continuity_explains_why_it_does_not_apply() -> None:
    report = verify_limit(lim("sin(x)/x", "0"))
    assert any(
        check.kind == "comparison" and "denominador se anula" in check.message
        for check in report.checks
    )


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

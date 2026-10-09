"""The verification of extrema rejects wrong points, values and classifications (ADR 0021)."""

from dataclasses import replace

import sympy as sp

from app.math_engine.extrema import ExtremaOutcome, extrema
from app.models.intents import ExtremaParams
from app.models.result import CheckKind, ReasonCode, VerificationStatus
from app.verification.extrema import verify_extrema


def run(text: str) -> ExtremaOutcome:
    return extrema(ExtremaParams(expression=text))


def test_polynomials_are_verified_symbolically() -> None:
    report = verify_extrema(run("x^3 - 3x"))
    assert report.status is VerificationStatus.VERIFIED_SYMBOLIC
    assert {CheckKind.COMPARISON, CheckKind.SUBSTITUTION, CheckKind.COMPLETENESS} <= set(
        report.methods
    )


def test_the_vertex_is_checked_by_its_formula() -> None:
    report = verify_extrema(run("x^2 - 4x + 3"))
    assert report.status is VerificationStatus.VERIFIED_SYMBOLIC
    assert any("−b/(2a)" in check.message for check in report.checks)


def test_no_critical_points_is_proved() -> None:
    report = verify_extrema(run("x^3 + x"))
    assert report.status is VerificationStatus.VERIFIED_SYMBOLIC


def test_a_line_has_no_critical_point() -> None:
    outcome = run("2x + 1")
    assert outcome.equation is None and outcome.points == ()
    report = verify_extrema(outcome)
    assert report.status is VerificationStatus.VERIFIED_SYMBOLIC
    assert "constante e diferente de zero" in report.checks[-1].message


def test_other_functions_are_partial() -> None:
    report = verify_extrema(run("e^x - 2x"))
    assert report.status is VerificationStatus.PARTIAL
    assert report.reason is ReasonCode.COMPLETENESS_NOT_PROVED


def test_a_wrong_value_fails() -> None:
    outcome = run("x^3 - 3x")
    wrong = replace(outcome.points[0], y=outcome.points[0].y + sp.Rational(1, 10**6))
    report = verify_extrema(replace(outcome, points=(wrong, *outcome.points[1:])))
    assert report.status is VerificationStatus.FAILED


def test_a_wrong_classification_fails() -> None:
    outcome = run("x^3 - 3x")
    wrong = replace(outcome.points[0], kind="min")
    report = verify_extrema(replace(outcome, points=(wrong, *outcome.points[1:])))
    assert report.status is VerificationStatus.FAILED
    assert report.checks[-1].kind is CheckKind.NUMERIC


def test_a_missing_critical_point_fails() -> None:
    outcome = run("x^3 - 3x")
    equation = replace(outcome.equation, solutions=outcome.equation.solutions[:1])
    report = verify_extrema(replace(outcome, equation=equation, points=outcome.points[:1]))
    assert report.status is VerificationStatus.FAILED
    assert report.checks[-1].kind is CheckKind.COMPLETENESS


def test_a_wrong_vertex_fails() -> None:
    outcome = run("x^2 - 4x + 3")
    wrong = replace(outcome.points[0], kind="max")
    report = verify_extrema(replace(outcome, points=(wrong,)))
    assert report.status is VerificationStatus.FAILED


def test_a_wrong_derivative_fails() -> None:
    outcome = run("x^3 - 3x")
    x = outcome.variable
    equation = replace(outcome.equation, left=outcome.equation.left + x)
    assert verify_extrema(replace(outcome, equation=equation)).status is VerificationStatus.FAILED

"""The verifiers must confirm correct results and, above all, catch wrong ones."""

from dataclasses import replace

import pytest
import sympy as sp

from app.math_engine.algebra import SolutionKind, simplify, solve_linear
from app.math_engine.arithmetic import evaluate
from app.models.intents import ArithmeticParams, SimplifyParams, SolveEquationParams
from app.models.result import VerificationStatus
from app.parsing.build import symbol
from app.verification.algebra import verify_equation, verify_simplify
from app.verification.arithmetic import verify_arithmetic

x = symbol("x")

# -- arithmetic -----------------------------------------------------------------------


@pytest.mark.parametrize(
    "expression", ["2 + 2", "0.1 + 0.2", "sqrt(8)", "sin(30)", "(-8)^(1/3)", "2^3000", "log(5)"]
)
def test_arithmetic_is_verified_numerically(expression: str) -> None:
    report = verify_arithmetic(evaluate(ArithmeticParams(expression=expression)))
    assert report.status is VerificationStatus.VERIFIED_NUMERIC
    assert report.checks


def test_arithmetic_catches_a_wrong_value() -> None:
    outcome = evaluate(ArithmeticParams(expression="2 + 2"))
    report = verify_arithmetic(replace(outcome, value=sp.Integer(5)))
    assert report.status is VerificationStatus.FAILED


def test_arithmetic_catches_a_tiny_error() -> None:
    outcome = evaluate(ArithmeticParams(expression="sqrt(2)"))
    report = verify_arithmetic(replace(outcome, value=sp.Rational(14142135623, 10**10)))
    assert report.status is VerificationStatus.FAILED


# -- simplify ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "expression", ["x² + 2x + x²", "sin(x)^2 + cos(x)^2", "(x^2 - 1)/(x - 1)", "sqrt(x^2)"]
)
def test_simplify_is_verified_symbolically(expression: str) -> None:
    report = verify_simplify(simplify(SimplifyParams(expression=expression)))
    assert report.status is VerificationStatus.VERIFIED_SYMBOLIC


def test_simplify_catches_a_wrong_result() -> None:
    outcome = simplify(SimplifyParams(expression="x^2 + 2x + 1"))
    report = verify_simplify(replace(outcome, result=(x + 2) ** 2))
    assert report.status is VerificationStatus.FAILED
    assert "x =" in report.checks[0]


def test_simplify_catches_a_result_undefined_where_the_original_is_defined() -> None:
    outcome = simplify(SimplifyParams(expression="x"))
    # Equal to x for x > 0, but not real for x < 0.
    report = verify_simplify(replace(outcome, result=x * sp.sqrt(x) / sp.sqrt(sp.Abs(x))))
    assert report.status is VerificationStatus.FAILED


def test_simplify_without_domain_points_is_unverified() -> None:
    outcome = simplify(SimplifyParams(expression="sqrt(x - 1000)"))
    report = verify_simplify(outcome)
    assert report.status is VerificationStatus.UNVERIFIED


# -- equations ----------------------------------------------------------------------------


@pytest.mark.parametrize(
    "equation", ["2x + 5 = 17", "(x + 1)^2 = x^2", "x + 1 = x + 2", "2(x + 1) = 2x + 2"]
)
def test_equations_are_verified_symbolically(equation: str) -> None:
    report = verify_equation(solve_linear(SolveEquationParams(equation=equation)))
    assert report.status is VerificationStatus.VERIFIED_SYMBOLIC


def test_unique_solution_report_mentions_completeness() -> None:
    report = verify_equation(solve_linear(SolveEquationParams(equation="2x + 5 = 17")))
    assert any("não existem outras soluções" in check for check in report.checks)


def test_equation_catches_a_wrong_solution() -> None:
    outcome = solve_linear(SolveEquationParams(equation="2x + 5 = 17"))
    report = verify_equation(replace(outcome, solution=sp.Integer(7)))
    assert report.status is VerificationStatus.FAILED


def test_equation_catches_a_false_no_solution_claim() -> None:
    outcome = solve_linear(SolveEquationParams(equation="2x + 5 = 17"))
    report = verify_equation(replace(outcome, kind=SolutionKind.NONE, solution=None))
    assert report.status is VerificationStatus.FAILED


def test_equation_catches_a_false_identity_claim() -> None:
    outcome = solve_linear(SolveEquationParams(equation="x + 1 = x + 2"))
    report = verify_equation(replace(outcome, kind=SolutionKind.ALL_REALS))
    assert report.status is VerificationStatus.FAILED

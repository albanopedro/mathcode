"""The verifiers must confirm correct results and, above all, catch wrong ones."""

from dataclasses import replace

import pytest
import sympy as sp

from app.math_engine.algebra import divide, expand, factor, simplify
from app.math_engine.arithmetic import evaluate
from app.math_engine.equations import EquationOutcome, SolutionKind, solve_equation
from app.math_engine.systems import SystemKind, SystemOutcome, solve_system
from app.models.intents import (
    ArithmeticParams,
    ExpandParams,
    FactorParams,
    PolynomialDivisionParams,
    SimplifyParams,
    SolveEquationParams,
    SolveSystemParams,
)
from app.models.result import VerificationStatus as S
from app.parsing.build import symbol
from app.verification.algebra import verify_division, verify_factor, verify_rewrite
from app.verification.arithmetic import verify_arithmetic
from app.verification.equations import verify_equation, verify_system

x, y = symbol("x"), symbol("y")


def equation(text: str) -> EquationOutcome:
    return solve_equation(SolveEquationParams(equation=text))


def system(text: str) -> SystemOutcome:
    return solve_system(SolveSystemParams(system=text))


# -- arithmetic -----------------------------------------------------------------------


@pytest.mark.parametrize(
    "expression", ["2 + 2", "0.1 + 0.2", "sqrt(8)", "sin(30)", "(-8)^(1/3)", "2^3000", "log(5)"]
)
def test_arithmetic_is_verified_numerically(expression: str) -> None:
    report = verify_arithmetic(evaluate(ArithmeticParams(expression=expression)))
    assert report.status is S.VERIFIED_NUMERIC
    assert report.checks


def test_arithmetic_catches_a_wrong_value() -> None:
    outcome = evaluate(ArithmeticParams(expression="2 + 2"))
    assert verify_arithmetic(replace(outcome, value=sp.Integer(5))).status is S.FAILED


def test_arithmetic_catches_a_tiny_error() -> None:
    outcome = evaluate(ArithmeticParams(expression="sqrt(2)"))
    wrong = replace(outcome, value=sp.Rational(14142135623, 10**10))
    assert verify_arithmetic(wrong).status is S.FAILED


# -- rewrites -------------------------------------------------------------------------


@pytest.mark.parametrize(
    "expression", ["x² + 2x + x²", "sin(x)^2 + cos(x)^2", "(x^2 - 1)/(x - 1)", "sqrt(x^2)"]
)
def test_simplify_is_verified_symbolically(expression: str) -> None:
    report = verify_rewrite(simplify(SimplifyParams(expression=expression)))
    assert report.status is S.VERIFIED_SYMBOLIC


def test_simplify_catches_a_wrong_result() -> None:
    outcome = simplify(SimplifyParams(expression="x^2 + 2x + 1"))
    report = verify_rewrite(replace(outcome, result=(x + 2) ** 2))
    assert report.status is S.FAILED
    assert "x =" in report.checks[0]


def test_simplify_catches_a_result_undefined_where_the_original_is_defined() -> None:
    outcome = simplify(SimplifyParams(expression="x"))
    # Equal to x for x > 0, but not real for x < 0.
    report = verify_rewrite(replace(outcome, result=x * sp.sqrt(x) / sp.sqrt(sp.Abs(x))))
    assert report.status is S.FAILED


def test_simplify_without_domain_points_is_unverified() -> None:
    report = verify_rewrite(simplify(SimplifyParams(expression="sqrt(x - 1000)")))
    assert report.status is S.UNVERIFIED


@pytest.mark.parametrize("expression", ["x^2 - 4", "x^4 - 1", "x^2 - 2", "360", "-84"])
def test_factor_is_verified_symbolically(expression: str) -> None:
    report = verify_factor(factor(FactorParams(expression=expression)))
    assert report.status is S.VERIFIED_SYMBOLIC


def test_factor_catches_a_wrong_factorization() -> None:
    outcome = factor(FactorParams(expression="x^2 - 4"))
    assert verify_factor(replace(outcome, result=(x - 2) ** 2)).status is S.FAILED


def test_prime_factorization_catches_a_wrong_product_or_a_composite() -> None:
    outcome = factor(FactorParams(expression="360"))
    assert verify_factor(replace(outcome, factors=((2, 3), (3, 2), (7, 1)))).status is S.FAILED
    assert verify_factor(replace(outcome, factors=((8, 1), (9, 1), (5, 1)))).status is S.FAILED


def test_prime_factorization_names_the_primality_test() -> None:
    small = verify_factor(factor(FactorParams(expression="360")))
    assert "determinístico" in small.checks[1]
    big = verify_factor(factor(FactorParams(expression="2^89 - 1")))  # a Mersenne prime
    assert "BPSW" in big.checks[1]


def test_expand_is_verified_and_catches_errors() -> None:
    outcome = expand(ExpandParams(expression="(x + 1)^3"))
    assert verify_rewrite(outcome).status is S.VERIFIED_SYMBOLIC
    wrong = replace(outcome, result=x**3 + 3 * x**2 + 3 * x + 2)
    assert verify_rewrite(wrong).status is S.FAILED


# -- polynomial division ---------------------------------------------------------------------


@pytest.mark.parametrize(
    "division", ["(x^3 - 1)/(x - 1)", "(x^3 + 2x + 5)/(x^2 + 1)", "(x^2)/(2x - 4)"]
)
def test_division_is_verified(division: str) -> None:
    report = verify_division(divide(PolynomialDivisionParams(division=division)))
    assert report.status is S.VERIFIED_SYMBOLIC


def test_division_catches_a_wrong_quotient_and_a_remainder_too_big() -> None:
    outcome = divide(PolynomialDivisionParams(division="(x^3 + 2x + 5)/(x^2 + 1)"))
    assert verify_division(replace(outcome, quotient=x + 1)).status is S.FAILED
    # A = B·0 + A holds, but the remainder's degree is not below the divisor's.
    lazy = replace(outcome, quotient=sp.Integer(0), remainder=outcome.dividend)
    assert verify_division(lazy).status is S.FAILED


# -- equations --------------------------------------------------------------------------------


@pytest.mark.parametrize(
    "text",
    [
        "2x + 5 = 17",
        "x^2 - 5x + 6 = 0",
        "x^3 = 3x - 1",
        "(x - 1)^2 (x + 2) = 0",
        "x^2 + 1 = 0",
        "1/x = 2",
        "(x^2 - 1)/(x - 1) = 0",
        "x/x = 1",
        "1/x = 0",
        "x + 1 = x + 2",
        "2(x + 1) = 2x + 2",
        "sqrt(2)x = 2",
    ],
)
def test_complete_solution_sets_are_verified_symbolically(text: str) -> None:
    assert verify_equation(equation(text)).status is S.VERIFIED_SYMBOLIC


def test_sturm_is_named_in_the_report() -> None:
    report = verify_equation(equation("x^2 - 5x + 6 = 0"))
    assert any("Sturm" in check for check in report.checks)


@pytest.mark.parametrize(
    "text", ["sqrt(x + 2) = x", "abs(x) = 3", "2^x = 8", "sqrt(x) = -1", "sqrt(2) x^2 = 1"]
)
def test_completeness_not_proved_is_partial(text: str) -> None:
    report = verify_equation(equation(text))
    assert report.status is S.PARTIAL
    assert report.message.startswith("Verificação parcial")


def test_equation_catches_a_wrong_solution() -> None:
    outcome = equation("2x + 5 = 17")
    assert verify_equation(replace(outcome, solutions=(sp.Integer(7),))).status is S.FAILED


def test_equation_catches_a_missing_root() -> None:
    outcome = equation("x^2 - 5x + 6 = 0")
    report = verify_equation(replace(outcome, solutions=(sp.Integer(2),), multiplicities=(1,)))
    assert report.status is S.FAILED
    assert "Sturm" in report.checks[0]


def test_equation_catches_an_extraneous_root() -> None:
    """x = -1 satisfies the squared equation x + 2 = x^2, but not sqrt(x + 2) = x."""
    outcome = equation("sqrt(x + 2) = x")
    wrong = replace(outcome, solutions=(sp.Integer(-1), sp.Integer(2)))
    assert verify_equation(wrong).status is S.FAILED


def test_equation_catches_a_root_outside_the_domain() -> None:
    outcome = equation("(x^2 - 1)/(x - 1) = 0")
    wrong = replace(outcome, solutions=(sp.Integer(-1), sp.Integer(1)), rejected=())
    assert verify_equation(wrong).status is S.FAILED


def test_equation_catches_false_claims() -> None:
    outcome = equation("2x + 5 = 17")
    no_solution = replace(outcome, kind=SolutionKind.NONE, solutions=())
    assert verify_equation(no_solution).status is not S.VERIFIED_SYMBOLIC
    assert verify_equation(replace(outcome, kind=SolutionKind.ALL_REALS)).status is S.FAILED


# -- systems ------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    "text",
    [
        "x + y = 3; x - y = 1",
        "x/3 + y = 1; x - y = 2",
        "x + y = 3; 2x + 2y = 6",
        "x + y = 3; x + y = 4",
        "x + y + z = 6; x - y = 0; 2z = 4",
    ],
)
def test_systems_are_verified_symbolically(text: str) -> None:
    assert verify_system(system(text)).status is S.VERIFIED_SYMBOLIC


def test_system_catches_a_wrong_solution() -> None:
    outcome = system("x + y = 3; x - y = 1")
    assert (
        verify_system(replace(outcome, solution=(sp.Integer(1), sp.Integer(2)))).status is S.FAILED
    )


def test_system_catches_a_false_infinite_claim() -> None:
    outcome = system("x + y = 3; x - y = 1")
    wrong = replace(outcome, kind=SystemKind.INFINITE, solution=(3 - y, y), free=(y,))
    assert verify_system(wrong).status is S.FAILED


def test_system_catches_a_false_inconsistency() -> None:
    outcome = system("x + y = 3; x - y = 1")
    wrong = replace(outcome, kind=SystemKind.NONE, solution=None)
    assert verify_system(wrong).status is S.FAILED

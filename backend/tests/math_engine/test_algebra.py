import pytest
import sympy as sp

from app.core.errors import ErrorCode, MathError
from app.core.notices import NoticeCode
from app.math_engine.algebra import (
    PrimeFactorization,
    RewriteOutcome,
    divide,
    expand,
    factor,
    simplify,
)
from app.models.intents import ExpandParams, FactorParams, PolynomialDivisionParams, SimplifyParams
from app.parsing.build import symbol

x = symbol("x")
y = symbol("y")

# -- simplify ---------------------------------------------------------------------


@pytest.mark.parametrize(
    ("expression", "expected"),
    [
        ("x² + 2x + x²", 2 * x**2 + 2 * x),
        ("x + x + x", 3 * x),
        ("(x + 1)^2 - x^2 - 2x", sp.Integer(1)),
        ("sin(x)^2 + cos(x)^2", sp.Integer(1)),
        ("sqrt(x^2)", sp.Abs(x)),
        ("2x + 3y - x", x + 3 * y),
        ("2 + 2", sp.Integer(4)),
    ],
)
def test_simplify_is_equivalent(expression: str, expected: sp.Expr) -> None:
    outcome = simplify(SimplifyParams(expression=expression))
    assert sp.simplify(outcome.result - expected) == 0


def test_simplify_warns_when_the_domain_grows() -> None:
    outcome = simplify(SimplifyParams(expression="(x^2 - 1)/(x - 1)"))
    assert sp.simplify(outcome.result - (x + 1)) == 0
    notices = [n for n in outcome.notices if n.code is NoticeCode.DOMAIN_CHANGED]
    assert len(notices) == 1
    assert "x = 1" in notices[0].message


def test_simplify_does_not_warn_when_the_singularity_remains() -> None:
    outcome = simplify(SimplifyParams(expression="1/x + 1/x"))
    assert all(n.code is not NoticeCode.DOMAIN_CHANGED for n in outcome.notices)


@pytest.mark.parametrize("expression", ["x = 1", "x + y = 1; x - y = 0"])
def test_simplify_rejects_equations_and_systems(expression: str) -> None:
    with pytest.raises(MathError) as exc:
        simplify(SimplifyParams(expression=expression))
    assert exc.value.code is ErrorCode.INVALID_INPUT_FOR_INTENT


# -- factor ---------------------------------------------------------------------------


def run_factor(expression: str) -> RewriteOutcome:
    outcome = factor(FactorParams(expression=expression))
    assert isinstance(outcome, RewriteOutcome)
    return outcome


@pytest.mark.parametrize(
    ("expression", "expected"),
    [
        ("x^2 - 4", (x - 2) * (x + 2)),
        ("x² - 5x + 6", (x - 2) * (x - 3)),
        ("x^4 - 1", (x - 1) * (x + 1) * (x**2 + 1)),
        ("2x^2 + 4x", 2 * x * (x + 2)),
        ("x^2 + 2xy + y^2".replace("xy", "x*y"), (x + y) ** 2),
        ("sin(x)^2 - 1", (sp.sin(x) - 1) * (sp.sin(x) + 1)),
    ],
)
def test_factor(expression: str, expected: sp.Expr) -> None:
    outcome = run_factor(expression)
    assert outcome.result == expected
    assert outcome.changed


def test_irreducible_over_the_rationals_is_unchanged() -> None:
    outcome = run_factor("x^2 - 2")
    assert outcome.result == x**2 - 2
    assert not outcome.changed


def test_factoring_a_fraction_warns_about_the_domain() -> None:
    outcome = run_factor("(x^2 - 1)/(x - 1)")
    assert outcome.result == x + 1
    assert NoticeCode.DOMAIN_CHANGED in {n.code for n in outcome.notices}


@pytest.mark.parametrize(
    ("number", "factors"),
    [
        ("360", ((2, 3), (3, 2), (5, 1))),
        ("-84", ((2, 2), (3, 1), (7, 1))),
        ("97", ((97, 1),)),
        ("2^10 * 3", ((2, 10), (3, 1))),
    ],
)
def test_integers_are_factored_into_primes(number: str, factors: tuple) -> None:
    outcome = factor(FactorParams(expression=number))
    assert isinstance(outcome, PrimeFactorization)
    assert outcome.factors == factors


@pytest.mark.parametrize("number", ["0", "1", "-1", "1/2", "sqrt(2)"])
def test_numbers_without_prime_factorization(number: str) -> None:
    with pytest.raises(MathError) as exc:
        factor(FactorParams(expression=number))
    assert exc.value.code is ErrorCode.INVALID_INPUT_FOR_INTENT


# -- expand ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("expression", "expected"),
    [
        ("(x + 1)^3", x**3 + 3 * x**2 + 3 * x + 1),
        ("(x - y)(x + y)", x**2 - y**2),
        ("x(x + 3)", x**2 + 3 * x),
    ],
)
def test_expand(expression: str, expected: sp.Expr) -> None:
    outcome = expand(ExpandParams(expression=expression))
    assert outcome.result == expected
    assert outcome.changed


def test_already_expanded_is_unchanged() -> None:
    assert not expand(ExpandParams(expression="x^2 + 1")).changed


# -- polynomial division ----------------------------------------------------------------


@pytest.mark.parametrize(
    ("division", "quotient", "remainder"),
    [
        ("(x^3 - 1)/(x - 1)", x**2 + x + 1, sp.Integer(0)),
        ("(x^3 + 2x + 5)/(x^2 + 1)", x, x + 5),
        ("(x^2)/(2x - 4)", x / 2 + 1, sp.Integer(4)),
        ("x^2/3", x**2 / 3, sp.Integer(0)),
        ("(x + 1)/(x^2 + 1)", sp.Integer(0), x + 1),
    ],
)
def test_division(division: str, quotient: sp.Expr, remainder: sp.Expr) -> None:
    outcome = divide(PolynomialDivisionParams(division=division))
    assert outcome.quotient == quotient
    assert outcome.remainder == remainder


def test_division_does_not_let_sympy_cancel_first() -> None:
    """Built as one expression, (x^2 - 1)/(x - 1) could lose its structure."""
    outcome = divide(PolynomialDivisionParams(division="(x^2 - 1)/(x - 1)"))
    assert outcome.dividend == x**2 - 1
    assert outcome.divisor == x - 1


@pytest.mark.parametrize(
    ("division", "code"),
    [
        ("x^2 + 1", ErrorCode.INVALID_INPUT_FOR_INTENT),
        ("6/3", ErrorCode.INVALID_INPUT_FOR_INTENT),
        ("(x + y)/(x - y)", ErrorCode.UNSUPPORTED_FEATURE),
        ("sin(x)/x", ErrorCode.UNSUPPORTED_FEATURE),
        ("x/(1/x)", ErrorCode.UNSUPPORTED_FEATURE),
        ("x/(x - x)", ErrorCode.DIVISION_BY_ZERO),
    ],
)
def test_division_errors(division: str, code: ErrorCode) -> None:
    with pytest.raises(MathError) as exc:
        divide(PolynomialDivisionParams(division=division))
    assert exc.value.code is code

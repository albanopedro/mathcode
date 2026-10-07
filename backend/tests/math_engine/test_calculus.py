import pytest
import sympy as sp

from app.core.errors import ErrorCode, MathError
from app.core.notices import NoticeCode
from app.math_engine.calculus import (
    LimitKind,
    LimitOutcome,
    derivative,
    integral,
    limit,
    parse_value,
)
from app.models.intents import DerivativeParams, IntegralParams, LimitParams
from app.parsing.build import symbol

x, y = symbol("x"), symbol("y")

# -- bounds and points --------------------------------------------------------------------


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("0", sp.Integer(0)),
        ("pi/2", sp.pi / 2),
        ("1,5", sp.Rational(3, 2)),
        ("inf", sp.oo),
        ("+∞", sp.oo),
        ("oo", sp.oo),
        ("infinito", sp.oo),
        ("-inf", -sp.oo),
        ("-∞", -sp.oo),
        (" - inf ", -sp.oo),
    ],
)
def test_parse_value(text: str, expected: sp.Expr) -> None:
    assert parse_value(text, "ponto")[0] == expected


@pytest.mark.parametrize(
    ("text", "code", "fragment"),
    [
        ("y", ErrorCode.INVALID_INPUT_FOR_INTENT, "não pode ter variáveis"),
        ("1/0", ErrorCode.DIVISION_BY_ZERO, "Divisão por zero"),
        ("sqrt(-1)", ErrorCode.DOMAIN_ERROR, "real"),
        ("2 +", ErrorCode.PARSE_ERROR, "incompleta"),
    ],
)
def test_parse_value_errors_name_the_field(text: str, code: ErrorCode, fragment: str) -> None:
    with pytest.raises(MathError) as exc:
        parse_value(text, "limite inferior")
    assert exc.value.code is code
    assert exc.value.message.startswith("No limite inferior:")
    assert fragment in exc.value.message
    assert exc.value.position is None  # it would point into another field


# -- derivative ------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("expression", "options", "expected"),
    [
        ("x^2 + 3x + 5", {}, 2 * x + 3),
        ("sen(x)", {}, sp.cos(x)),
        ("x^2 sin(x)", {"order": 2}, -(x**2) * sp.sin(x) + 4 * x * sp.cos(x) + 2 * sp.sin(x)),
        ("e^(2x)", {"order": 3}, 8 * sp.exp(2 * x)),
        ("ln(x)", {}, 1 / x),
        ("x y^2", {"variable": "y"}, 2 * x * y),
        ("x y^2", {"variable": "x"}, y**2),
        ("5", {}, sp.Integer(0)),
        ("x^3", {"order": 4}, sp.Integer(0)),
    ],
)
def test_derivative(expression: str, options: dict, expected: sp.Expr) -> None:
    outcome = derivative(DerivativeParams(expression=expression, **options))
    assert sp.simplify(outcome.result - expected) == 0


def test_derivative_of_absolute_value_warns() -> None:
    outcome = derivative(DerivativeParams(expression="abs(x)"))
    assert outcome.result == sp.sign(x)
    assert [n.code for n in outcome.notices] == [NoticeCode.NOT_DIFFERENTIABLE_POINTS]


def test_derivative_needs_the_variable_when_there_are_several() -> None:
    with pytest.raises(MathError) as exc:
        derivative(DerivativeParams(expression="x y"))
    assert exc.value.code is ErrorCode.AMBIGUOUS_INPUT
    assert "x, y" in exc.value.message


# -- indefinite integral ---------------------------------------------------------------------


@pytest.mark.parametrize(
    ("expression", "expected"),
    [
        ("x^2", x**3 / 3),
        ("sen(x)", -sp.cos(x)),
        ("e^x", sp.exp(x)),
        ("2x/(x^2 + 1)", sp.log(x**2 + 1)),  # always positive: no |...| needed
    ],
)
def test_indefinite_integral(expression: str, expected: sp.Expr) -> None:
    outcome = integral(IntegralParams(expression=expression))
    assert outcome.antiderivative is not None
    assert sp.simplify(outcome.antiderivative - expected) == 0
    assert not outcome.definite


@pytest.mark.parametrize(
    ("expression", "expected"),
    [
        ("1/x", sp.log(sp.Abs(x))),
        ("tan(x)", -sp.log(sp.Abs(sp.cos(x)))),
        ("1/(x - 1)", sp.log(sp.Abs(x - 1))),
    ],
)
def test_logarithms_get_absolute_values_in_the_real_domain(
    expression: str, expected: sp.Expr
) -> None:
    """SymPy gives ∫1/x dx = log(x), valid only for x > 0."""
    outcome = integral(IntegralParams(expression=expression))
    assert outcome.antiderivative == expected
    assert outcome.raw_antiderivative != expected
    assert NoticeCode.ABSOLUTE_VALUE_IN_LOG in {n.code for n in outcome.notices}


def test_other_variables_are_constants_in_an_indefinite_integral() -> None:
    outcome = integral(IntegralParams(expression="x y", variable="x"))
    assert outcome.antiderivative == x**2 * y / 2


def test_antiderivative_without_closed_form() -> None:
    with pytest.raises(MathError) as exc:
        integral(IntegralParams(expression="x^x"))
    assert exc.value.code is ErrorCode.UNSUPPORTED_FEATURE


# -- definite integral -------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("expression", "lower", "upper", "expected"),
    [
        ("x^2", "0", "1", sp.Rational(1, 3)),
        ("sen(x)", "0", "pi", sp.Integer(2)),
        ("1/x^2", "1", "inf", sp.Integer(1)),
        ("e^(-x)", "0", "+∞", sp.Integer(1)),
        ("e^(-x^2)", "-inf", "inf", sp.sqrt(sp.pi)),
        ("1/sqrt(x)", "0", "1", sp.Integer(2)),  # integrable endpoint singularity
        ("x", "1", "0", sp.Rational(-1, 2)),  # reversed bounds
    ],
)
def test_definite_integral(expression: str, lower: str, upper: str, expected: sp.Expr) -> None:
    outcome = integral(IntegralParams(expression=expression, lower=lower, upper=upper))
    assert outcome.definite and outcome.converges
    assert outcome.value is not None
    assert sp.simplify(outcome.value - expected) == 0


def test_divergent_integral_is_an_answer() -> None:
    outcome = integral(IntegralParams(expression="1/x", lower="1", upper="inf"))
    assert outcome.value == sp.oo
    assert not outcome.converges


@pytest.mark.parametrize(
    ("expression", "lower", "upper", "code"),
    [
        ("1/x", "-1", "1", ErrorCode.DOMAIN_ERROR),  # not integrable at 0
        ("sen(x)", "0", "inf", ErrorCode.DOMAIN_ERROR),  # oscillates
        ("sqrt(x)", "-1", "1", ErrorCode.DOMAIN_ERROR),  # not real on part of it
        ("x y", "0", "1", ErrorCode.UNSUPPORTED_FEATURE),  # other variables
    ],
)
def test_definite_integral_errors(expression: str, lower: str, upper: str, code: ErrorCode) -> None:
    with pytest.raises(MathError) as exc:
        integral(IntegralParams(expression=expression, variable="x", lower=lower, upper=upper))
    assert exc.value.code is code


# -- limit ------------------------------------------------------------------------------------


def run_limit(expression: str, point: str, side: str = "both") -> LimitOutcome:
    return limit(LimitParams(expression=expression, point=point, side=side))  # type: ignore[arg-type]


@pytest.mark.parametrize(
    ("expression", "point", "expected"),
    [
        ("sin(x)/x", "0", sp.Integer(1)),
        ("(1 - cos(x))/x^2", "0", sp.Rational(1, 2)),
        ("(x^2 - 1)/(x - 1)", "1", sp.Integer(2)),
        ("x sin(1/x)", "0", sp.Integer(0)),
        ("(1 + 1/x)^x", "inf", sp.E),  # used to hang: see _side_in_domain
        ("(1 + 2/x)^x", "-inf", sp.exp(2)),
        ("ln(x)/x", "inf", sp.Integer(0)),
    ],
)
def test_finite_limits(expression: str, point: str, expected: sp.Expr) -> None:
    outcome = run_limit(expression, point)
    assert outcome.kind is LimitKind.FINITE
    assert outcome.value == expected


@pytest.mark.parametrize(
    ("expression", "point", "side", "expected"),
    [
        ("1/x^2", "0", "both", sp.oo),
        ("1/x", "0", "right", sp.oo),
        ("1/x", "0", "left", -sp.oo),
        ("x", "-inf", "both", -sp.oo),
    ],
)
def test_infinite_limits(expression: str, point: str, side: str, expected: sp.Expr) -> None:
    outcome = run_limit(expression, point, side)
    assert outcome.kind is LimitKind.INFINITE
    assert outcome.value == expected


@pytest.mark.parametrize(
    ("expression", "point", "left", "right"),
    [
        ("1/x", "0", -sp.oo, sp.oo),
        ("abs(x)/x", "0", sp.Integer(-1), sp.Integer(1)),
        ("tan(x)", "pi/2", sp.oo, -sp.oo),
    ],
)
def test_different_sides_mean_no_limit(
    expression: str, point: str, left: sp.Expr, right: sp.Expr
) -> None:
    outcome = run_limit(expression, point)
    assert outcome.kind is LimitKind.NONEXISTENT
    assert (outcome.left, outcome.right) == (left, right)


def test_oscillation_means_no_limit() -> None:
    outcome = run_limit("sin(1/x)", "0")
    assert outcome.kind is LimitKind.NONEXISTENT
    assert outcome.oscillates


@pytest.mark.parametrize("expression", ["sqrt(x)", "x^x"])
def test_only_one_side_in_the_real_domain(expression: str) -> None:
    """SymPy would also approach from the left, through complex numbers."""
    outcome = run_limit(expression, "0")
    assert outcome.side == "right"
    assert outcome.requested_side == "both"
    assert [n.code for n in outcome.notices] == [NoticeCode.ONE_SIDED_DOMAIN]


@pytest.mark.parametrize(
    ("expression", "point", "side", "code"),
    [
        ("sqrt(x)", "0", "left", ErrorCode.DOMAIN_ERROR),
        ("sqrt(-x^2 - 1)", "0", "both", ErrorCode.DOMAIN_ERROR),
        ("sqrt(x)", "-inf", "both", ErrorCode.DOMAIN_ERROR),
        ("x y", "0", "both", ErrorCode.AMBIGUOUS_INPUT),
        ("x + 1", "y", "both", ErrorCode.INVALID_INPUT_FOR_INTENT),
    ],
)
def test_limit_errors(expression: str, point: str, side: str, code: ErrorCode) -> None:
    with pytest.raises(MathError) as exc:
        run_limit(expression, point, side)
    assert exc.value.code is code

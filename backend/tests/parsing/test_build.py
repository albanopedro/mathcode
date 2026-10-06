import pytest
import sympy as sp

from app.core.errors import ErrorCode, MathError
from app.core.limits import MAX_RESULT_DIGITS, MAX_SYMBOLIC_EXPONENT
from app.core.notices import NoticeCode
from app.parsing import parse
from app.parsing.ast import Equation
from app.parsing.build import ExpressionBuilder, digits, symbol

x = symbol("x")


def build(source: str) -> tuple[sp.Expr, ExpressionBuilder]:
    tree = parse(source).tree
    assert not isinstance(tree, Equation)
    builder = ExpressionBuilder()
    return builder.build(tree), builder


def value(source: str) -> sp.Expr:
    return build(source)[0]


def error(source: str) -> MathError:
    with pytest.raises(MathError) as exc:
        build(source)
    return exc.value


@pytest.mark.parametrize(
    ("source", "expected"),
    [
        ("0.1 + 0.2", sp.Rational(3, 10)),
        ("3,5", sp.Rational(7, 2)),
        ("2^10", sp.Integer(1024)),
        ("2^-2", sp.Rational(1, 4)),
        ("-2^2", sp.Integer(-4)),
        ("(-2)^2", sp.Integer(4)),
        ("2^3^2", sp.Integer(512)),
        ("sqrt(8)", 2 * sp.sqrt(2)),
        ("√9", sp.Integer(3)),
        ("sin(30°)", sp.Rational(1, 2)),
        ("cos(pi)", sp.Integer(-1)),
        ("log(1000)", sp.Integer(3)),
        ("log(8; 2)", sp.Integer(3)),
        ("ln(e)", sp.Integer(1)),
        ("abs(-3)", sp.Integer(3)),
        ("2x + x", 3 * x),
    ],
)
def test_values(source: str, expected: sp.Expr) -> None:
    assert sp.simplify(value(source) - expected) == 0


def test_variables_are_real() -> None:
    assert value("x").is_real is True
    assert sp.simplify(value("sqrt(x^2)")) == sp.Abs(x)


@pytest.mark.parametrize(
    ("source", "expected"),
    [
        ("(-8)^(1/3)", sp.Integer(-2)),
        ("(-8)^(2/3)", sp.Integer(4)),
        ("(-8)^(-1/3)", sp.Rational(-1, 2)),
        ("(-32)^0.2", sp.Integer(-2)),
    ],
)
def test_odd_roots_of_negative_numbers_are_real(source: str, expected: sp.Expr) -> None:
    result, builder = build(source)
    assert result == expected
    assert [n.code for n in builder.notices] == [NoticeCode.REAL_ROOT]


@pytest.mark.parametrize(
    ("source", "code"),
    [
        ("1/0", ErrorCode.DIVISION_BY_ZERO),
        ("1/(2 - 2)", ErrorCode.DIVISION_BY_ZERO),
        ("x/(x - x)", ErrorCode.DIVISION_BY_ZERO),
        ("0^(-1)", ErrorCode.DIVISION_BY_ZERO),
        ("0^0", ErrorCode.DOMAIN_ERROR),
        ("sqrt(-4)", ErrorCode.DOMAIN_ERROR),
        ("√(-1)", ErrorCode.DOMAIN_ERROR),
        ("(-4)^(1/2)", ErrorCode.DOMAIN_ERROR),
        ("(-2)^pi", ErrorCode.DOMAIN_ERROR),
        ("ln(0)", ErrorCode.DOMAIN_ERROR),
        ("log(-5)", ErrorCode.DOMAIN_ERROR),
        ("log(8; 1)", ErrorCode.DOMAIN_ERROR),
        ("log(8; -2)", ErrorCode.DOMAIN_ERROR),
        ("asin(2)", ErrorCode.DOMAIN_ERROR),
        ("acos(-1.5)", ErrorCode.DOMAIN_ERROR),
        ("tan(pi/2)", ErrorCode.DOMAIN_ERROR),
        ("tan(90°)", ErrorCode.DOMAIN_ERROR),
    ],
)
def test_domain_and_division_errors(source: str, code: ErrorCode) -> None:
    assert error(source).code is code


def test_division_by_zero_points_at_the_operator() -> None:
    assert error("10 + 1/0").position == 6


@pytest.mark.parametrize(
    "source",
    ["10^4001", "9^9^9^9", "(1/3)^9000", "2^(10^5000)", "(10^2000)*(10^2001)", "sqrt(2)^30000"],
)
def test_huge_numbers_are_refused_before_being_computed(source: str) -> None:
    assert error(source).code is ErrorCode.LIMIT_EXCEEDED


def test_largest_accepted_power() -> None:
    result = value("10^3999")
    assert digits(result) <= MAX_RESULT_DIGITS


def test_symbolic_exponent_limit() -> None:
    value(f"(x + 1)^{MAX_SYMBOLIC_EXPONENT}")
    assert error(f"(x + 1)^{MAX_SYMBOLIC_EXPONENT + 1}").code is ErrorCode.LIMIT_EXCEEDED


def test_records_denominators_before_sympy_cancels_them() -> None:
    result, builder = build("x/x")
    assert result == 1
    assert builder.denominators == [x]


def test_records_negative_powers_as_denominators() -> None:
    _, builder = build("x^(-2) + 1")
    assert builder.denominators == [x]


def test_log_without_base_is_base_ten_with_notice() -> None:
    _, builder = build("log(100)")
    assert [n.code for n in builder.notices] == [NoticeCode.LOG_BASE_10]
    _, builder = build("log(100; 10) + ln(5)")
    assert builder.notices == []


@pytest.mark.parametrize(
    ("source", "warns"),
    [
        ("sin(30)", True),
        ("cos(1) + 1", True),
        ("sin(30°)", False),
        ("sin(pi/6)", False),
        ("sin(x)", False),
        ("sqrt(30)", False),
    ],
)
def test_angle_in_radians_notice(source: str, warns: bool) -> None:
    _, builder = build(source)
    assert (NoticeCode.ANGLE_IN_RADIANS in {n.code for n in builder.notices}) is warns

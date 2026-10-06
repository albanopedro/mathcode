import pytest
import sympy as sp

from app.core.errors import ErrorCode, MathError
from app.core.notices import NoticeCode
from app.math_engine.arithmetic import evaluate
from app.models.intents import ArithmeticParams


def run(expression: str) -> sp.Expr:
    return evaluate(ArithmeticParams(expression=expression)).value


@pytest.mark.parametrize(
    ("expression", "expected"),
    [
        ("2 + 2", sp.Integer(4)),
        ("0.1 + 0.2", sp.Rational(3, 10)),
        ("1/3 + 1/6", sp.Rational(1, 2)),
        ("2^100", sp.Integer(2) ** 100),
        ("7/2*2", sp.Integer(7)),
        ("sqrt(2)*sqrt(8)", sp.Integer(4)),
        ("sin(pi/12)^2 + cos(pi/12)^2", sp.Integer(1)),
        ("sen(30°) + cos(60°)", sp.Integer(1)),
        ("log(0.001)", sp.Integer(-3)),
        ("(-27)^(1/3)", sp.Integer(-3)),
        ("-5 - -5", sp.Integer(0)),
        ("1 - 1", sp.Integer(0)),
    ],
)
def test_exact_values(expression: str, expected: sp.Expr) -> None:
    assert run(expression) == expected


def test_irrational_result_stays_exact() -> None:
    assert run("sqrt(12)") == 2 * sp.sqrt(3)


def test_keeps_parsing_and_conversion_notices() -> None:
    outcome = evaluate(ArithmeticParams(expression="log(100) + 1,5"))
    assert {n.code for n in outcome.notices} == {NoticeCode.LOG_BASE_10, NoticeCode.DECIMAL_COMMA}


@pytest.mark.parametrize(
    ("expression", "code"),
    [
        ("x + 1", ErrorCode.INVALID_INPUT_FOR_INTENT),
        ("2 + 2 = 4", ErrorCode.INVALID_INPUT_FOR_INTENT),
        ("5/0", ErrorCode.DIVISION_BY_ZERO),
        ("sqrt(-1)", ErrorCode.DOMAIN_ERROR),
        ("10^5000", ErrorCode.LIMIT_EXCEEDED),
        ("", ErrorCode.EMPTY_INPUT),
        ("2 +* 3", ErrorCode.PARSE_ERROR),
    ],
)
def test_errors(expression: str, code: ErrorCode) -> None:
    with pytest.raises(MathError) as exc:
        run(expression)
    assert exc.value.code is code

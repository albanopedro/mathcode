import pytest
import sympy as sp

from app.core.errors import ErrorCode, MathError
from app.core.notices import NoticeCode
from app.math_engine.algebra import EquationOutcome, SolutionKind, simplify, solve_linear
from app.models.intents import SimplifyParams, SolveEquationParams
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


def test_simplify_rejects_an_equation() -> None:
    with pytest.raises(MathError) as exc:
        simplify(SimplifyParams(expression="x = 1"))
    assert exc.value.code is ErrorCode.INVALID_INPUT_FOR_INTENT


# -- first-degree equations ----------------------------------------------------------


def solve(equation: str, variable: str | None = None) -> EquationOutcome:
    return solve_linear(SolveEquationParams(equation=equation, variable=variable))


@pytest.mark.parametrize(
    ("equation", "solution"),
    [
        ("2x + 5 = 17", sp.Integer(6)),
        ("3x = 0", sp.Integer(0)),
        ("x/2 = 3", sp.Integer(6)),
        ("0.5x - 1 = 2", sp.Integer(6)),
        ("5 = 2 - x", sp.Integer(-3)),
        ("2(x + 1) = 3(x - 1)", sp.Integer(5)),
        ("(x + 1)^2 = x^2", sp.Rational(-1, 2)),
        ("x^2 - x^2 + x = 3", sp.Integer(3)),
        ("sqrt(2)x = 2", sp.sqrt(2)),
        ("pi x = 1", 1 / sp.pi),
    ],
)
def test_unique_solution(equation: str, solution: sp.Expr) -> None:
    outcome = solve(equation)
    assert outcome.kind is SolutionKind.UNIQUE
    assert outcome.solution is not None
    assert sp.simplify(outcome.solution - solution) == 0


def test_no_solution() -> None:
    outcome = solve("x + 1 = x + 2")
    assert outcome.kind is SolutionKind.NONE
    assert outcome.solution is None


def test_every_real_is_a_solution() -> None:
    outcome = solve("2(x + 1) = 2x + 2")
    assert outcome.kind is SolutionKind.ALL_REALS


def test_explicit_variable_must_appear() -> None:
    assert solve("2y = 4", variable="y").solution == 2
    with pytest.raises(MathError) as exc:
        solve("2y = 4", variable="x")
    assert exc.value.code is ErrorCode.INVALID_INPUT_FOR_INTENT


@pytest.mark.parametrize(
    ("equation", "code"),
    [
        ("x^2 = 4", ErrorCode.UNSUPPORTED_FEATURE),
        ("x^3 + x = 1", ErrorCode.UNSUPPORTED_FEATURE),
        ("x/x = 1", ErrorCode.UNSUPPORTED_FEATURE),
        ("1/x = 2", ErrorCode.UNSUPPORTED_FEATURE),
        ("sqrt(x) = 3", ErrorCode.UNSUPPORTED_FEATURE),
        ("sqrt(x)^2 = -1", ErrorCode.UNSUPPORTED_FEATURE),
        ("sin(x) = 0", ErrorCode.UNSUPPORTED_FEATURE),
        ("2^x = 8", ErrorCode.UNSUPPORTED_FEATURE),
        ("x^0.5 = 2", ErrorCode.UNSUPPORTED_FEATURE),
        ("x° = 1", ErrorCode.UNSUPPORTED_FEATURE),
        ("x + y = 2", ErrorCode.UNSUPPORTED_FEATURE),
        ("2 = 2", ErrorCode.INVALID_INPUT_FOR_INTENT),
        ("2x + 1", ErrorCode.INVALID_INPUT_FOR_INTENT),
        ("x = 1/0", ErrorCode.DIVISION_BY_ZERO),
    ],
)
def test_equation_errors(equation: str, code: ErrorCode) -> None:
    with pytest.raises(MathError) as exc:
        solve(equation)
    assert exc.value.code is code

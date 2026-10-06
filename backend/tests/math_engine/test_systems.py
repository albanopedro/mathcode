import pytest
import sympy as sp

from app.core.errors import ErrorCode, MathError
from app.math_engine.systems import SystemKind, SystemOutcome, solve_system
from app.models.intents import SolveSystemParams
from app.parsing.build import symbol

x, y, z = symbol("x"), symbol("y"), symbol("z")


def solve(system: str) -> SystemOutcome:
    return solve_system(SolveSystemParams(system=system))


@pytest.mark.parametrize(
    ("system", "solution"),
    [
        ("x + y = 3; x - y = 1", (2, 1)),
        ("x + y = 3, x - y = 1", (2, 1)),
        ("x/3 + y = 1; x - y = 2", (sp.Rational(9, 4), sp.Rational(1, 4))),
        ("x + y + z = 6; x - y = 0; 2z = 4", (2, 2, 2)),
        ("2x = 4; 3y = 9", (2, 3)),
    ],
)
def test_unique_solution(system: str, solution: tuple) -> None:
    outcome = solve(system)
    assert outcome.kind is SystemKind.UNIQUE
    assert outcome.solution == solution
    assert outcome.free == ()


def test_variables_are_sorted_by_name() -> None:
    assert solve("y + x = 3; x - y = 1").variables == (x, y)


def test_infinite_solutions_are_parametric() -> None:
    outcome = solve("x + y = 3; 2x + 2y = 6")
    assert outcome.kind is SystemKind.INFINITE
    assert outcome.solution == (3 - y, y)
    assert outcome.free == (y,)


def test_a_single_equation_is_a_system_of_one() -> None:
    outcome = solve("x + y = 3")
    assert outcome.kind is SystemKind.INFINITE


def test_inconsistent_system() -> None:
    outcome = solve("x + y = 3; x + y = 4")
    assert outcome.kind is SystemKind.NONE
    assert outcome.solution is None


@pytest.mark.parametrize(
    ("system", "fragment"),
    [
        ("x*y = 2; x + y = 3", "grau 2"),
        ("x^2 + y = 1; x - y = 0", "grau 2"),
        ("1/x + y = 1; x - y = 0", "denominador"),
        ("sin(x) + y = 1; x - y = 0", "sin"),
    ],
)
def test_nonlinear_systems_are_not_supported(system: str, fragment: str) -> None:
    with pytest.raises(MathError) as exc:
        solve(system)
    assert exc.value.code is ErrorCode.UNSUPPORTED_FEATURE
    assert fragment in exc.value.message


@pytest.mark.parametrize(
    ("system", "code"),
    [
        ("x + 1", ErrorCode.INVALID_INPUT_FOR_INTENT),
        ("1 = 1; 2 = 2", ErrorCode.INVALID_INPUT_FOR_INTENT),
    ],
)
def test_system_errors(system: str, code: ErrorCode) -> None:
    with pytest.raises(MathError) as exc:
        solve(system)
    assert exc.value.code is code

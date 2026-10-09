import pytest
import sympy as sp

from app.core.errors import ErrorCode, MathError
from app.core.notices import NoticeCode
from app.math_engine.equations import EquationOutcome, SolutionKind, solve_equation
from app.math_engine.polynomials import Shape
from app.models.intents import SolveEquationParams

R = sp.Rational


def solve(equation: str, variable: str | None = None) -> EquationOutcome:
    return solve_equation(SolveEquationParams(equation=equation, variable=variable))


# -- first degree (Phase 2 cases still hold) ----------------------------------------


@pytest.mark.parametrize(
    ("equation", "solution"),
    [
        ("2x + 5 = 17", sp.Integer(6)),
        ("3x = 0", sp.Integer(0)),
        ("x/2 = 3", sp.Integer(6)),
        ("0.5x - 1 = 2", sp.Integer(6)),
        ("5 = 2 - x", sp.Integer(-3)),
        ("2(x + 1) = 3(x - 1)", sp.Integer(5)),
        ("(x + 1)^2 = x^2", R(-1, 2)),
        ("x^2 - x^2 + x = 3", sp.Integer(3)),
        ("sqrt(2)x = 2", sp.sqrt(2)),
        ("pi x = 1", 1 / sp.pi),
    ],
)
def test_first_degree(equation: str, solution: sp.Expr) -> None:
    outcome = solve(equation)
    assert outcome.kind is SolutionKind.FINITE
    assert len(outcome.solutions) == 1
    assert sp.simplify(outcome.solutions[0] - solution) == 0


def test_no_solution() -> None:
    outcome = solve("x + 1 = x + 2")
    assert outcome.kind is SolutionKind.NONE
    assert outcome.solutions == ()


def test_every_real_is_a_solution() -> None:
    assert solve("2(x + 1) = 2x + 2").kind is SolutionKind.ALL_REALS


def test_explicit_variable_must_appear() -> None:
    assert solve("2y = 4", variable="y").solutions == (2,)
    with pytest.raises(MathError) as exc:
        solve("2y = 4", variable="x")
    assert exc.value.code is ErrorCode.INVALID_INPUT_FOR_INTENT


# -- polynomials -----------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("equation", "solutions", "multiplicities"),
    [
        ("x^2 - 5x + 6 = 0", (2, 3), (1, 1)),
        ("x^2 = 4", (-2, 2), (1, 1)),
        ("x^2 = 2", (-sp.sqrt(2), sp.sqrt(2)), (1, 1)),
        ("x^3 = x", (-1, 0, 1), (1, 1, 1)),
        ("(x - 1)^2 (x + 2) = 0", (-2, 1), (1, 2)),
        ("x^2 - 2x + 1 = 0", (1,), (2,)),
    ],
)
def test_polynomial_roots_in_order_with_multiplicity(
    equation: str, solutions: tuple, multiplicities: tuple
) -> None:
    outcome = solve(equation)
    assert outcome.shape is Shape.POLYNOMIAL
    assert outcome.solutions == solutions
    assert outcome.multiplicities == multiplicities
    assert outcome.candidates is not None  # rational coefficients: Sturm can count


def test_complex_solutions_are_omitted_with_a_notice() -> None:
    outcome = solve("x^2 + 1 = 0")
    assert outcome.kind is SolutionKind.NONE
    assert [n.code for n in outcome.notices] == [NoticeCode.COMPLEX_SOLUTIONS_OMITTED]

    outcome = solve("x^3 = 1")
    assert outcome.solutions == (1,)
    assert "2 solução(ões) complexa(s)" in outcome.notices[0].message


def test_roots_without_radicals_are_exact_and_flagged() -> None:
    outcome = solve("x^3 = 3x - 1")  # three real roots: Cardano needs complex numbers
    assert len(outcome.solutions) == 3
    assert all(isinstance(s, sp.CRootOf) for s in outcome.solutions)
    assert NoticeCode.ROOTS_SHOWN_APPROXIMATELY in {n.code for n in outcome.notices}


def test_irrational_coefficients_use_solveset() -> None:
    outcome = solve("sqrt(2) x^2 = 1")
    assert len(outcome.solutions) == 2
    assert outcome.candidates is None  # Sturm needs rational coefficients
    assert outcome.multiplicities == ()


# -- rational equations ------------------------------------------------------------------------


def test_rational_equation() -> None:
    outcome = solve("1/x = 2")
    assert outcome.shape is Shape.RATIONAL
    assert outcome.solutions == (R(1, 2),)
    assert outcome.excluded == (0,)


def test_root_that_zeros_a_denominator_is_rejected() -> None:
    outcome = solve("(x^2 - 1)/(x - 1) = 0")
    assert outcome.solutions == (-1,)
    assert outcome.rejected == (1,)


def test_identity_except_where_undefined() -> None:
    outcome = solve("x/x = 1")
    assert outcome.kind is SolutionKind.ALL_REALS
    assert outcome.excluded == (0,)


@pytest.mark.parametrize("equation", ["1/x = 0", "1/(x^2 + 1) = 0"])
def test_rational_without_solution(equation: str) -> None:
    assert solve(equation).kind is SolutionKind.NONE


# -- other shapes ----------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("equation", "solutions"),
    [
        ("sqrt(x) = 3", (9,)),
        ("sqrt(x + 2) = x", (2,)),  # x = -1 is extraneous
        ("abs(x) = 3", (-3, 3)),
        ("2^x = 8", (3,)),
        ("ln(x) = 1", (sp.E,)),
    ],
)
def test_other_equations(equation: str, solutions: tuple) -> None:
    outcome = solve(equation)
    assert outcome.shape is Shape.OTHER
    assert outcome.solutions == solutions


def test_other_equation_without_solution() -> None:
    assert solve("sqrt(x) = -1").kind is SolutionKind.NONE


@pytest.mark.parametrize(
    ("equation", "fragment"),
    [("sin(x) = x/10", "forma exata"), ("x = cos(x)", "forma exata")],
)
def test_unsupported_equations(equation: str, fragment: str) -> None:
    with pytest.raises(MathError) as exc:
        solve(equation)
    assert exc.value.code is ErrorCode.UNSUPPORTED_FEATURE
    assert fragment in exc.value.message


@pytest.mark.parametrize(
    ("equation", "code"),
    [
        ("x + y = 2", ErrorCode.UNSUPPORTED_FEATURE),
        ("2 = 2", ErrorCode.INVALID_INPUT_FOR_INTENT),
        ("2x + 1", ErrorCode.INVALID_INPUT_FOR_INTENT),
        ("x + y = 1; x - y = 0", ErrorCode.INVALID_INPUT_FOR_INTENT),
        ("x = 1/0", ErrorCode.DIVISION_BY_ZERO),
    ],
)
def test_equation_errors(equation: str, code: ErrorCode) -> None:
    with pytest.raises(MathError) as exc:
        solve(equation)
    assert exc.value.code is code


def test_more_than_one_variable_suggests_a_system() -> None:
    with pytest.raises(MathError) as exc:
        solve("x + y = 2")
    assert "';'" in exc.value.message

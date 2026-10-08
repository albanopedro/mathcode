"""Matrices: parsing, engine, verification and presentation (ADR 0012)."""

from dataclasses import replace

import pytest
import sympy as sp

from app.calculator import calculate
from app.core.errors import ErrorCode, MathError
from app.formatting.results import present_matrices
from app.math_engine.matrices import MatrixOutcome, matrices
from app.models.intents import MatrixOperation, MatrixParams
from app.models.result import VerificationStatus as S
from app.parsing import parse
from app.parsing.ast import Matrix
from app.verification.matrices import verify_matrices

M = sp.Matrix
R = sp.Rational


def run(expression: str, operation: MatrixOperation = "evaluate") -> MatrixOutcome:
    return matrices(MatrixParams(expression=expression, operation=operation))


# -- parsing --------------------------------------------------------------------------------------


def test_matrix_literal() -> None:
    tree = parse("[[1, 2], [3, 4]]").tree
    assert isinstance(tree, Matrix)
    assert len(tree.rows) == 2 and len(tree.rows[0]) == 2
    assert parse("[[1; 2]; [3; 4]]").canonical == "[[1, 2], [3, 4]]"  # ";" also separates
    assert parse("[[1,5, -2]]").canonical == "[[1.5, -2]]"  # "1,5" is still a decimal


@pytest.mark.parametrize(
    ("text", "message"),
    [
        ("[[1, 2], [3]]", "mesmo número de elementos"),
        ("[[1, 2], 3]", "entre colchetes"),  # a row without its brackets
        ("[[1, 2]", "Colchete aberto"),
        ("[[1, 2]]]", "sem o '['"),
        ("2[[1]]", "use *"),
        ("[[" + ", ".join(["1"] * 9) + "]]", "até 8"),
    ],
)
def test_bad_matrix_syntax(text: str, message: str) -> None:
    with pytest.raises(MathError) as exc:
        parse(text)
    assert message in exc.value.message


def test_matrices_are_refused_by_other_operations() -> None:
    result = calculate("[[1, 2], [3, 4]]", "simplify")
    assert result.error is not None
    assert "operações Matrizes e Vetores" in result.error.message


def test_automatic_detects_matrix_expressions() -> None:
    result = calculate("[[1, 2], [3, 4]] * [[5, 6], [7, 8]]")
    assert result.intent == "matrix"
    assert result.result is not None and result.result.plain == "[[19, 22], [43, 50]]"


# -- the engine -----------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("expression", "operation", "expected"),
    [
        ("[[1, 2], [3, 4]]", "determinant", sp.Integer(-2)),
        ("[[1, 2], [3, 4]]", "inverse", M([[-2, 1], [R(3, 2), R(-1, 2)]])),
        ("[[1, 2, 3], [4, 5, 6]]", "transpose", M([[1, 4], [2, 5], [3, 6]])),
        ("[[1, 2], [3, 4]]", "trace", sp.Integer(5)),
        ("[[1, 2, 3], [4, 5, 6], [7, 8, 9]]", "rank", sp.Integer(2)),
        ("[[1, 2], [3, 4]] * [[5, 6], [7, 8]]", "evaluate", M([[19, 22], [43, 50]])),
        ("[[1, 2], [3, 4]]^-2", "evaluate", M([[R(11, 2), R(-5, 2)], [R(-15, 4), R(7, 4)]])),
        ("2*[[1,5, 2]] / 4 - [[1, 1]]", "evaluate", M([[R(-1, 4), 0]])),
        ("[[pi, 1], [2, e]]", "determinant", sp.E * sp.pi - 2),
        ("[[1, 2], [3, 4]] * 2", "determinant", sp.Integer(-8)),  # the operation acts on A
    ],
)
def test_results(expression: str, operation: str, expected: sp.Expr) -> None:
    assert sp.simplify(run(expression, operation).result - expected) == 0 * expected


@pytest.mark.parametrize(
    ("expression", "operation", "message"),
    [
        ("[[1, 2], [2, 4]]", "inverse", "singular"),
        ("[[1, 2, 3], [4, 5, 6]]", "determinant", "quadradas"),
        ("[[1, 2, 3], [4, 5, 6]]", "trace", "quadradas"),
        ("[[1, 2]] + [[1], [2]]", "evaluate", "mesmo tamanho"),
        ("[[1, 2]] * [[1, 2]]", "evaluate", "número de colunas"),
        ("[[1, 2], [3, 4]] + 1", "evaluate", "matriz com matriz"),
        ("1 / [[1, 2], [3, 4]]", "evaluate", "divisão por matriz"),
        ("[[1, 2], [3, 4]]^(1/2)", "evaluate", "inteiro"),
        ("[[1, 2], [3, 4]]^21", "evaluate", "inteiro"),
        ("[[1, 2], [2, 4]]^-1", "evaluate", "singular"),
        ("[[1, 2, 3]]^2", "evaluate", "quadradas"),
        ("[[1, x]]", "evaluate", "sem variáveis"),
        ("sin([[1]])", "evaluate", "Funções"),
        ("2 + 3", "evaluate", "não tem matriz"),
        ("[[1]] = [[1]]", "evaluate", "sem '='"),
    ],
)
def test_errors_are_explained(expression: str, operation: str, message: str) -> None:
    with pytest.raises(MathError) as exc:
        run(expression, operation)
    assert message in exc.value.message


def test_division_by_zero_in_a_matrix() -> None:
    with pytest.raises(MathError) as exc:
        run("[[1, 2]] / 0")
    assert exc.value.code is ErrorCode.DIVISION_BY_ZERO


# -- verification ---------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("expression", "operation", "methods"),
    [
        ("[[1, 2], [3, 4]]", "determinant", ["comparison"]),
        ("[[1, 2], [3, 4]]", "inverse", ["comparison", "symbolic"]),
        ("[[1, 2, 3], [4, 5, 6]]", "transpose", ["comparison", "symbolic"]),
        ("[[1, 2], [3, 4]]", "trace", ["comparison"]),
        ("[[1, 2, 3], [4, 5, 6], [7, 8, 9]]", "rank", ["comparison"]),
        ("[[1, 2], [3, 4]]^-2 * [[1, 0], [0, 2]]", "evaluate", ["comparison"]),
    ],
)
def test_rational_matrices_are_verified_exactly(
    expression: str, operation: str, methods: list[str]
) -> None:
    report = verify_matrices(run(expression, operation))
    assert report.status is S.VERIFIED_SYMBOLIC
    assert report.methods == methods


@pytest.mark.parametrize(
    "operation", ["evaluate", "determinant", "inverse", "transpose", "trace", "rank"]
)
def test_irrational_matrices_are_verified_numerically(operation: str) -> None:
    report = verify_matrices(run("[[sqrt(2), 1], [pi, 2]]", operation))
    assert report.status is S.VERIFIED_NUMERIC
    assert report.methods == ["numeric"]


@pytest.mark.parametrize(
    ("expression", "operation", "tamper"),
    [
        ("[[1, 2], [3, 4]]", "determinant", lambda o: replace(o, result=sp.Integer(2))),
        ("[[1, 2], [3, 4]]", "inverse", lambda o: replace(o, result=o.result.T)),
        ("[[1, 2, 3], [4, 5, 6]]", "transpose", lambda o: replace(o, result=o.operand)),
        ("[[1, 2], [3, 4]]", "trace", lambda o: replace(o, result=sp.Integer(4))),
        ("[[1, 2], [2, 4]]", "rank", lambda o: replace(o, result=sp.Integer(2))),
        ("[[1, 2]] * 3", "evaluate", lambda o: replace(o, operand=M([[3, 7]]), result=o.result)),
        ("[[sqrt(2), 1], [1, 1]]", "determinant", lambda o: replace(o, result=sp.sqrt(2))),
        ("[[sqrt(2), 1], [1, 1]]", "inverse", lambda o: replace(o, result=o.result * 2)),
    ],
)
def test_catches_wrong_results(expression: str, operation: str, tamper: object) -> None:
    report = verify_matrices(tamper(run(expression, operation)))  # type: ignore[operator]
    assert report.status is S.FAILED


# -- presentation ---------------------------------------------------------------------------------


def test_presentation() -> None:
    p = present_matrices(run("[[1, 2], [3, 4]]", "inverse"))
    assert p.result.plain == "A⁻¹ = [[-2, 1], [3/2, -1/2]]"
    assert p.result.latex.startswith(r"A^{-1} = \left[\begin{matrix}")
    assert p.result.approx is None
    assert p.details == {
        "operation": "inverse",
        "rows": 2,
        "cols": 2,
        "matrix": "[[1, 2], [3, 4]]",
        "matrix_latex": r"\left[\begin{matrix}1 & 2\\3 & 4\end{matrix}\right]",
    }


def test_irrational_entries_have_an_approximation() -> None:
    p = present_matrices(run("[[sqrt(2), 1]]"))
    assert p.result.plain == "[[sqrt(2), 1]]"
    assert p.result.approx == "[[1.4142135623731, 1]]"


def test_scalar_results() -> None:
    assert present_matrices(run("[[1, 2], [3, 4]]", "determinant")).result.latex == (
        r"\det(A) = -2"
    )
    assert present_matrices(run("[[1, 2], [3, 4]]", "rank")).result.plain == "posto = 2"

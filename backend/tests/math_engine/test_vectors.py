"""Vectors: parsing, engine, verification and presentation (ADR 0013)."""

from dataclasses import replace

import pytest
import sympy as sp

from app.calculator import calculate
from app.core.errors import MathError
from app.formatting.results import present_vectors
from app.math_engine.matrices import VectorValue
from app.math_engine.vectors import VectorOutcome, vectors
from app.models.intents import VectorOperation, VectorParams
from app.models.result import VerificationStatus as S
from app.parsing import parse
from app.parsing.ast import ExpressionList, Vector
from app.verification.vectors import verify_vectors


def run(expression: str, operation: VectorOperation = "evaluate") -> VectorOutcome:
    return vectors(VectorParams(expression=expression, operation=operation))


def vec(*entries: object) -> VectorValue:
    return VectorValue(sp.ImmutableMatrix([sp.sympify(e) for e in entries]))


# -- parsing --------------------------------------------------------------------------------------


def test_vector_literal() -> None:
    tree = parse("[1, 2, 3]").tree
    assert isinstance(tree, Vector) and len(tree.entries) == 3
    assert parse("[1,5; -2]").canonical == "[1.5, -2]"


def test_two_vectors_form_a_list() -> None:
    tree = parse("[1, 2]; [3, 4]").tree
    assert isinstance(tree, ExpressionList) and len(tree.expressions) == 2


@pytest.mark.parametrize(
    ("text", "message"),
    [
        ("[1, [2]]", "não outros vetores"),
        ("[" + ", ".join(["1"] * 9) + "]", "até 8"),
        ("[1, 2", "Colchete aberto"),
    ],
)
def test_bad_vector_syntax(text: str, message: str) -> None:
    with pytest.raises(MathError) as exc:
        parse(text)
    assert message in exc.value.message


def test_automatic_detects_vectors() -> None:
    result = calculate("2*[1, 0] + [0, 3]")
    assert result.intent == "vector"
    assert result.result is not None and result.result.plain == "[2, 3]"


# -- the engine -----------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("expression", "operation", "expected"),
    [
        ("[3, 4]", "norm", sp.Integer(5)),
        ("[1, 2, 2]", "unit", vec("1/3", "2/3", "2/3")),
        ("[1, 1]", "unit", vec(sp.sqrt(2) / 2, sp.sqrt(2) / 2)),
        ("[1, 2, 3]; [4, 5, 6]", "dot", sp.Integer(32)),
        ("[1, 2, 3]; [4, 5, 6]", "cross", vec(-3, 6, -3)),
        ("[1, 0]; [1, 1]", "angle", sp.pi / 4),
        ("[1, 2]; [-2, 1]", "angle", sp.pi / 2),
        ("[3, 4]; [4, 3]", "angle", sp.acos(sp.Rational(24, 25))),
        ("2*[1, 0] - [0, 1]/2", "evaluate", vec(2, "-1/2")),
        ("[[1, 2], [3, 4]] * [1, 1]", "norm", sp.sqrt(58)),  # A·v is a vector
    ],
)
def test_results(expression: str, operation: VectorOperation, expected: object) -> None:
    result = run(expression, operation).result
    if isinstance(expected, VectorValue):
        assert isinstance(result, VectorValue) and result.entries == expected.entries
    else:
        assert result == expected


@pytest.mark.parametrize(
    ("expression", "operation", "message"),
    [
        ("[0, 0]", "unit", "vetor nulo"),
        ("[0, 0]; [1, 1]", "angle", "nulo"),
        ("[1, 2]", "dot", "dois vetores"),
        ("[1, 2]; [3, 4]", "norm", "um vetor só"),
        ("[1, 2]; [3, 4]", "evaluate", "escolha um cálculo"),
        ("[1, 2]; [3, 4]", "cross", "3 componentes"),
        ("[1, 2]; [3, 4, 5]", "dot", "mesmo número de componentes"),
        ("[1, 2] + [1, 2, 3]", "evaluate", "mesmo número de componentes"),
        ("[1, 2] * [3, 4]", "evaluate", "ambíguo"),
        ("[1, 2] * [[1, 2], [3, 4]]", "evaluate", "matriz antes"),
        ("[1, 2]^2", "evaluate", "Vetores não têm potência"),
        ("[1, 2] + 1", "evaluate", "vetor com vetor"),
        ("[[1, 2]]", "norm", "é uma matriz"),
        ("5", "norm", "entre colchetes"),
        ("[1, x]", "norm", "sem variáveis"),
    ],
)
def test_errors_are_explained(expression: str, operation: VectorOperation, message: str) -> None:
    with pytest.raises(MathError) as exc:
        run(expression, operation)
    assert message in exc.value.message


# -- verification ---------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("expression", "operation"),
    [
        ("[3, 4]", "norm"),
        ("[1, 1]", "unit"),
        ("[1, 2, 3]; [4, 5, 6]", "dot"),
        ("[1, 2, 3]; [4, 5, 6]", "cross"),
        ("[1, 0]; [1, 1]", "angle"),
        ("[3, 4]; [4, 3]", "angle"),
        ("[1, 0]; [-1, 0]", "angle"),
        ("2*[1, 0] + [0, 3]", "evaluate"),
    ],
)
def test_rational_vectors_are_verified_exactly(expression: str, operation: VectorOperation) -> None:
    report = verify_vectors(run(expression, operation))
    assert report.status is S.VERIFIED_SYMBOLIC


def test_cross_product_checks_orthogonality_and_lagrange() -> None:
    report = verify_vectors(run("[1, 2, 3]; [4, 5, 6]", "cross"))
    assert any("perpendicular" in c.message and "Lagrange" in c.message for c in report.checks)


@pytest.mark.parametrize("operation", ["norm", "unit", "evaluate"])
def test_irrational_vector_is_verified_numerically(operation: VectorOperation) -> None:
    assert verify_vectors(run("[sqrt(2), pi]", operation)).status is S.VERIFIED_NUMERIC


@pytest.mark.parametrize("operation", ["dot", "cross", "angle"])
def test_irrational_pairs_are_verified_numerically(operation: VectorOperation) -> None:
    report = verify_vectors(run("[sqrt(2), 1, 0]; [0, 1, pi]", operation))
    assert report.status is S.VERIFIED_NUMERIC


@pytest.mark.parametrize(
    ("expression", "operation", "tamper"),
    [
        ("[3, 4]", "norm", lambda o: replace(o, result=sp.Integer(7))),
        ("[3, 4]", "norm", lambda o: replace(o, result=sp.Integer(-5))),
        ("[3, 4]", "unit", lambda o: replace(o, result=vec("4/5", "3/5"))),
        ("[3, 4]", "unit", lambda o: replace(o, result=vec(3, 4))),
        ("[1, 2, 3]; [4, 5, 6]", "dot", lambda o: replace(o, result=sp.Integer(31))),
        ("[1, 2, 3]; [4, 5, 6]", "cross", lambda o: replace(o, result=vec(3, -6, 3))),
        ("[1, 0]; [1, 1]", "angle", lambda o: replace(o, result=sp.pi / 3)),
        ("[1, 2]", "evaluate", lambda o: replace(o, vectors=(vec(1, 3),), result=vec(1, 3))),
        ("[sqrt(2), pi]", "norm", lambda o: replace(o, result=sp.Integer(3))),
        ("[sqrt(2), 1, 0]; [0, 1, pi]", "angle", lambda o: replace(o, result=sp.Integer(1))),
    ],
)
def test_catches_wrong_results(expression: str, operation: VectorOperation, tamper: object) -> None:
    report = verify_vectors(tamper(run(expression, operation)))  # type: ignore[operator]
    assert report.status is S.FAILED


# -- presentation ---------------------------------------------------------------------------------


def test_vector_presentation() -> None:
    p = present_vectors(run("[1, 2, 3]; [4, 5, 6]", "cross"))
    assert p.result.plain == "u×v = [-3, 6, -3]"
    assert p.result.latex == r"u \times v = \left(-3,\ 6,\ -3\right)"
    assert p.details == {
        "operation": "cross",
        "dimension": 3,
        "vectors": ["[1, 2, 3]", "[4, 5, 6]"],
        "vectors_latex": [r"\left(1,\ 2,\ 3\right)", r"\left(4,\ 5,\ 6\right)"],
    }


def test_angle_in_radians_and_degrees() -> None:
    exact = present_vectors(run("[1, 0]; [1, 1]", "angle"))
    assert exact.result.plain == "θ = pi/4 rad = 45°"
    assert exact.result.latex == r"\theta = \frac{\pi}{4} = 45^\circ"
    assert exact.details["degrees"] == "45"

    assert exact.result.approx == "0.785398163397448 rad"

    approximate = present_vectors(run("[3, 4]; [4, 3]", "angle"))
    assert approximate.result.plain == "θ = acos(24/25) rad ≈ 16.2602°"  # 6 digits shown
    assert approximate.details["degrees"] is None
    assert approximate.details["degrees_approx"] == "16.260204708312"  # all 15 digits


def test_norm_with_its_approximation() -> None:
    p = present_vectors(run("[1, 2, 3]", "norm"))
    assert (p.result.plain, p.result.approx) == ("‖u‖ = sqrt(14)", "3.74165738677394")

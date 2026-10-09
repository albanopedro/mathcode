"""Critical points, maxima, minima and the vertex (Phase 12, ADR 0021)."""

import pytest
import sympy as sp

from app.core.errors import ErrorCode, MathError
from app.core.notices import NoticeCode
from app.math_engine.extrema import ExtremaOutcome, extrema
from app.models.intents import ExtremaParams


def run(text: str, variable: str | None = None) -> ExtremaOutcome:
    return extrema(ExtremaParams(expression=text, variable=variable))


def found(text: str) -> list[tuple[str, str, str]]:
    return [(str(p.x), str(p.y), p.kind) for p in run(text).points]


@pytest.mark.parametrize(
    ("text", "points"),
    [
        ("x^2 - 4x + 3", [("2", "-1", "min")]),
        ("-2x^2 + 4x", [("1", "2", "max")]),
        ("x^3 - 3x", [("-1", "2", "max"), ("1", "-2", "min")]),
        ("x^4 - 2x^2", [("-1", "-1", "min"), ("0", "0", "max"), ("1", "-1", "min")]),
        ("x^5 - 5x + 1", [("-1", "5", "max"), ("1", "-3", "min")]),
        ("x/(x^2 + 1)", [("-1", "-1/2", "min"), ("1", "1/2", "max")]),
    ],
)
def test_maxima_and_minima(text: str, points: list[tuple[str, str, str]]) -> None:
    assert found(text) == points


def test_a_flat_point_that_is_not_an_extremum() -> None:
    # f'' = 0 at x = 0 in both: the first derivative test still decides.
    assert found("x^4") == [("0", "0", "min")]
    assert found("x^3") == [("0", "0", "none")]


@pytest.mark.parametrize("text", ["x^3 + x", "1/x", "2x + 1"])
def test_no_critical_points(text: str) -> None:
    assert run(text).points == ()


def test_exact_irrational_points() -> None:
    outcome = run("(x^2 - 1)/(x - 2)")
    assert [p.x for p in outcome.points] == [2 - sp.sqrt(3), 2 + sp.sqrt(3)]
    assert [p.y for p in outcome.points] == [4 - 2 * sp.sqrt(3), 4 + 2 * sp.sqrt(3)]
    assert [p.kind for p in outcome.points] == ["max", "min"]


def test_near_the_edge_of_the_domain_the_test_point_moves_closer() -> None:
    # The left test point x = 1/e − 1 would be outside the domain of ln.
    outcome = run("x*ln(x)")
    assert [(p.x, p.y, p.kind) for p in outcome.points] == [(sp.exp(-1), -sp.exp(-1), "min")]
    assert NoticeCode.NOT_DIFFERENTIABLE_POINTS in {n.code for n in outcome.notices}


def test_natural_log_survives_the_trip_through_text() -> None:
    # f' = ln(x) + 1 is solved from text: printed as log(x) it would be base 10.
    assert run("x*ln(x)").equation.solutions == (sp.exp(-1),)


def test_the_vertex_of_a_parabola() -> None:
    assert run("x^2 - 4x + 3").quadratic
    assert not run("x^3 - 3x").quadratic


def test_another_variable() -> None:
    outcome = run("t^2 - 2t", "t")
    assert outcome.variable.name == "t"
    assert [(str(p.x), p.kind) for p in outcome.points] == [("1", "min")]


def test_notices_of_the_derivative_equation_are_not_shown() -> None:
    # "complex solutions omitted" is about f'(x) = 0, not about what was asked.
    assert NoticeCode.COMPLEX_SOLUTIONS_OMITTED not in {n.code for n in run("x^3 + x").notices}


@pytest.mark.parametrize(
    ("text", "code", "words"),
    [
        ("5", ErrorCode.INVALID_INPUT_FOR_INTENT, "uma variável"),
        ("x + y", ErrorCode.UNSUPPORTED_FEATURE, "mais de uma variável"),
        ("sin(x)", ErrorCode.UNSUPPORTED_FEATURE, "periódicas"),
        ("abs(x)", ErrorCode.UNSUPPORTED_FEATURE, "módulo"),
        ("x^2 = 4", ErrorCode.INVALID_INPUT_FOR_INTENT, "equação"),
    ],
)
def test_out_of_scope_is_explained(text: str, code: ErrorCode, words: str) -> None:
    with pytest.raises(MathError) as exc:
        run(text)
    assert exc.value.code is code
    assert words in exc.value.message


def test_a_constant_function_has_no_strict_extremum() -> None:
    with pytest.raises(MathError) as exc:
        run("x - x + 3", "x")
    assert "constante" in exc.value.message

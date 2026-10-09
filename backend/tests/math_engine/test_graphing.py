import math

import pytest
import sympy as sp

from app.core.errors import ErrorCode, MathError
from app.core.limits import GRAPH_SAMPLES, MAX_GRAPH_FUNCTIONS
from app.core.notices import NoticeCode
from app.math_engine.graphing import GraphOutcome, graph, is_graph_input
from app.models.intents import GraphParams
from app.parsing import parse


def draw(expression: str, x_min: str | None = None, x_max: str | None = None) -> GraphOutcome:
    return graph(GraphParams(expression=expression, x_min=x_min, x_max=x_max))


def roots(outcome: GraphOutcome, function: int = 0) -> list[float]:
    return [p.x_value for p in outcome.points if p.kind == "root" and p.function == function]


# -- input -------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("x^2; 2x + 1", True),
        ("y = x^2", True),
        ("y = x^2; y = 2x", True),
        ("x^2", False),  # a single expression is simplified unless "Gráfico" is chosen
        ("x = 2", False),
        ("y = y + 1", False),
        ("x + y = 3; x - y = 1", False),
    ],
)
def test_detection(text: str, expected: bool) -> None:
    assert is_graph_input(parse(text).tree) is expected


@pytest.mark.parametrize(
    ("text", "labels"),
    [
        ("x^2 - 4x + 3", ["x^2 - 4*x + 3"]),
        ("y = x^2", ["x^2"]),
        ("x^2; 2x + 1", ["x^2", "2*x + 1"]),
        ("y = sin(x); y = cos(x)", ["sin(x)", "cos(x)"]),
    ],
)
def test_functions(text: str, labels: list[str]) -> None:
    assert [f.label for f in draw(text).functions] == labels


def test_samples_cover_the_default_range() -> None:
    outcome = draw("x")
    (function,) = outcome.functions
    assert len(function.xs) == GRAPH_SAMPLES
    assert (function.xs[0], function.xs[-1]) == (-10.0, 10.0)
    assert (outcome.x_min, outcome.x_max) == (-10, 10)


def test_custom_range_accepts_expressions() -> None:
    outcome = draw("sin(x)", "-2pi", "2pi")
    assert outcome.x_min == -2 * sp.pi
    assert math.isclose(outcome.functions[0].xs[-1], 2 * math.pi)


# -- domain and gaps -------------------------------------------------------------------------


def test_outside_the_domain_is_a_gap() -> None:
    (function,) = draw("sqrt(x)").functions
    defined = [x for x, y in zip(function.xs, function.ys, strict=True) if y is not None]
    assert min(defined) == 0
    assert sum(y is None for y in function.ys) == GRAPH_SAMPLES // 2


def test_asymptotes_break_the_line() -> None:
    """tan jumps from +∞ to -∞: the line must not cross the whole plot."""
    outcome = draw("tan(x)")
    (function,) = outcome.functions
    low, high = outcome.y_range
    span = high - low
    pairs = zip(function.ys, function.ys[1:], strict=False)
    for a, b in pairs:
        if a is not None and b is not None:
            assert not (a * b < 0 and abs(a - b) > span)
    assert sum(y is None for y in function.ys) >= 6  # one per asymptote


def test_y_range_is_clipped_near_asymptotes() -> None:
    outcome = draw("1/x")
    low, high = outcome.y_range
    assert outcome.y_clipped
    assert -20 < low < 0 < high < 20
    assert NoticeCode.Y_RANGE_CLIPPED in {n.code for n in outcome.notices}


def test_y_range_keeps_a_steep_but_regular_function() -> None:
    outcome = draw("e^x")
    assert not outcome.y_clipped
    assert outcome.y_range[1] > math.exp(10)


# -- relevant points --------------------------------------------------------------------------


def test_exact_roots_and_intercept() -> None:
    outcome = draw("x^2 - 4x + 3")
    assert roots(outcome) == [1.0, 3.0]
    assert all(p.exact for p in outcome.points)
    (intercept,) = [p for p in outcome.points if p.kind == "y_intercept"]
    assert intercept.y == 3


def test_roots_outside_the_range_are_left_out() -> None:
    assert roots(draw("x^2 - 4x + 3", "-5", "2")) == [1.0]


def test_roots_without_radicals() -> None:
    assert [round(r, 6) for r in roots(draw("x^3 - 3x + 1"))] == [-1.879385, 0.347296, 1.532089]


def test_numeric_roots_by_sign_change() -> None:
    outcome = draw("sin(x) - x/10")  # no exact form: found by sign change and bisection
    found = roots(outcome)
    assert len(found) == 7
    assert all(abs(math.sin(r) - r / 10) < 1e-9 for r in found)
    assert not any(p.exact for p in outcome.points if p.kind == "root")
    assert NoticeCode.NUMERIC_ROOTS in {n.code for n in outcome.notices}


def test_periodic_roots_are_exact_in_the_visible_range() -> None:
    outcome = draw("sin(x)")  # x = kπ (ADR 0016), listed inside [-10, 10]
    assert [round(r, 9) for r in roots(outcome)] == [round(k * math.pi, 9) for k in range(-3, 4)]
    assert all(p.exact for p in outcome.points if p.kind == "root")


def test_roots_at_the_edges_of_the_range() -> None:
    assert [round(r, 9) for r in roots(draw("sin(x)", "-2pi", "2pi"))] == [
        round(k * math.pi, 9) for k in range(-2, 3)
    ]


def test_poles_are_not_roots() -> None:
    """tan also changes sign at its poles (±pi/2...): only true zeros count."""
    found = roots(draw("tan(x)"))
    assert all(abs(math.sin(r)) < 1e-9 for r in found)


def test_no_intercept_when_zero_is_outside_the_domain_or_range() -> None:
    assert not [p for p in draw("1/x").points if p.kind == "y_intercept"]
    assert not [p for p in draw("x^2", "1", "5").points if p.kind == "y_intercept"]


def test_constant_function() -> None:
    outcome = draw("5")
    assert roots(outcome) == []
    assert outcome.y_range[0] < 5 < outcome.y_range[1]


# -- errors -----------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("text", "x_min", "x_max", "code"),
    [
        ("x y", None, None, ErrorCode.UNSUPPORTED_FEATURE),
        ("x = 2", None, None, ErrorCode.INVALID_INPUT_FOR_INTENT),
        ("ln(x)", "-5", "-1", ErrorCode.DOMAIN_ERROR),
        ("x", "5", "1", ErrorCode.INVALID_INPUT_FOR_INTENT),
        ("x", "0", "inf", ErrorCode.INVALID_INPUT_FOR_INTENT),
        ("x", "0", "10^7", ErrorCode.LIMIT_EXCEEDED),
        ("x", "y", "1", ErrorCode.INVALID_INPUT_FOR_INTENT),
        ("; ".join(["x"] * (MAX_GRAPH_FUNCTIONS + 1)), None, None, ErrorCode.LIMIT_EXCEEDED),
    ],
)
def test_errors(text: str, x_min: str | None, x_max: str | None, code: ErrorCode) -> None:
    with pytest.raises(MathError) as exc:
        draw(text, x_min, x_max)
    assert exc.value.code is code


def test_near_pole_samples_are_not_zeros() -> None:
    """On [-2pi, 2pi] a sample of tan lands ~1e-14 from a pole (|y| ~ 1e14): a zero
    tolerance relative to max|y| took values up to ~100 for zeros (seen in Phase 7)."""
    found = roots(draw("tan(x)", "-2pi", "2pi"))
    assert [round(r, 6) for r in found] == [round(k * math.pi, 6) for k in range(-2, 3)]

"""The graph verifier checks the highlighted points, and catches wrong ones."""

from dataclasses import replace

import pytest
import sympy as sp

from app.math_engine.graphing import GraphOutcome, graph
from app.models.intents import GraphParams
from app.models.result import VerificationStatus as S
from app.verification.graphing import verify_graph


def draw(expression: str, x_min: str | None = None, x_max: str | None = None) -> GraphOutcome:
    return graph(GraphParams(expression=expression, x_min=x_min, x_max=x_max))


@pytest.mark.parametrize("expression", ["x^2 - 4x + 3", "x^3 - 3x + 1", "x^2; 2x + 1", "5"])
def test_exact_and_complete_roots_are_verified(expression: str) -> None:
    assert verify_graph(draw(expression)).status is S.VERIFIED_NUMERIC


@pytest.mark.parametrize("expression", ["sin(x) - x/10", "tan(x) - x"])
def test_roots_by_sign_change_are_partial(expression: str) -> None:
    report = verify_graph(draw(expression))
    assert report.status is S.PARTIAL
    assert any("mudança de sinal" in check.message for check in report.checks)


def test_nothing_to_check_is_not_applicable() -> None:
    assert verify_graph(draw("1/x", "1", "5")).status is S.NOT_APPLICABLE


def test_catches_a_wrong_root() -> None:
    outcome = draw("x^2 - 4x + 3")
    wrong_point = replace(outcome.points[0], x=sp.Integer(2), x_value=2.0, x_decimal="2")
    wrong = replace(outcome, points=(wrong_point, *outcome.points[1:]))
    report = verify_graph(wrong)
    assert report.status is S.FAILED
    assert "não 0" in report.checks[-1].message


def test_catches_a_wrong_numeric_root() -> None:
    outcome = draw("sin(x)")
    point = outcome.points[0]
    wrong_point = replace(point, x_value=point.x_value + 0.1, x_decimal=str(point.x_value + 0.1))
    wrong = replace(outcome, points=(wrong_point, *outcome.points[1:]))
    assert verify_graph(wrong).status is S.FAILED


def test_catches_a_wrong_intercept() -> None:
    outcome = draw("x^2 - 4x + 3")
    points = [
        replace(p, y=sp.Integer(4), y_value=4.0) if p.kind == "y_intercept" else p
        for p in outcome.points
    ]
    assert verify_graph(replace(outcome, points=tuple(points))).status is S.FAILED


def test_every_status_and_reason_has_a_message() -> None:
    """NOT_APPLICABLE had none until graphs used it, and the pipeline broke."""
    from app.models.result import ReasonCode
    from app.verification.reports import message_for

    for status in S:
        assert message_for(status)
    for reason in ReasonCode:
        assert message_for(S.UNVERIFIED, reason).startswith("Não foi possível verificar")


def test_catches_a_root_next_to_a_pole() -> None:
    outcome = draw("tan(x)", "-2pi", "2pi")
    near_pole = replace(outcome.points[0], x_value=-1.555088364, x_decimal="-1.555088364")
    wrong = replace(outcome, points=(near_pole, *outcome.points[1:]))
    assert verify_graph(wrong).status is S.FAILED

"""Turning (text, intent, options) into typed params, with readable errors."""

import pytest

from app.core.errors import ErrorCode, MathError
from app.interpreter.detect import interpret
from app.models.intents import (
    DerivativeParams,
    IntegralParams,
    IntentName,
    LimitParams,
    SolveEquationParams,
)


@pytest.mark.parametrize(
    ("text", "intent"),
    [
        ("2 + 2", IntentName.ARITHMETIC),
        ("x + x", IntentName.SIMPLIFY),
        ("x = 1", IntentName.SOLVE_EQUATION),
        ("x + y = 1; x - y = 0", IntentName.SOLVE_SYSTEM),
    ],
)
def test_detection(text: str, intent: IntentName) -> None:
    assert interpret(text).intent is intent


def test_calculus_must_be_asked_for() -> None:
    assert interpret("x^2").intent is IntentName.SIMPLIFY


def test_options_fill_the_params() -> None:
    request = interpret("x^2 sin(x)", "derivative", {"variable": "x", "order": 2})
    assert request.params == DerivativeParams(expression="x^2 sin(x)", variable="x", order=2)

    request = interpret("x^2", "integral", {"lower": "0", "upper": "1"})
    assert request.params == IntegralParams(expression="x^2", lower="0", upper="1")

    request = interpret("sin(x)/x", "limit", {"point": "0", "side": "right"})
    assert request.params == LimitParams(expression="sin(x)/x", point="0", side="right")

    request = interpret("2y = 4", "solve_equation", {"variable": "y"})
    assert request.params == SolveEquationParams(equation="2y = 4", variable="y")


@pytest.mark.parametrize(
    ("intent", "options", "message"),
    [
        (
            "derivative",
            {"order": 11},
            "A ordem da derivada precisa ser um número inteiro de 1 a 10.",
        ),
        (
            "derivative",
            {"order": 0},
            "A ordem da derivada precisa ser um número inteiro de 1 a 10.",
        ),
        ("derivative", {"variable": "xy"}, "A variável precisa ser uma única letra, como x."),
        (
            "integral",
            {"lower": "0"},
            "Informe os dois limites de integração, ou nenhum (integral indefinida).",
        ),
        ("limit", {}, "Informe o ponto do limite, como 0, pi/2 ou inf."),
        (
            "limit",
            {"point": "0", "side": "up"},
            "O lado do limite precisa ser 'both', 'left' ou 'right'.",
        ),
        ("simplify", {"order": 2}, "Parâmetro não aceito por esta operação: order."),
        ("derivative", {"lower": "0"}, "Parâmetro não aceito por esta operação: lower."),
    ],
)
def test_invalid_options_are_explained(intent: str, options: dict, message: str) -> None:
    with pytest.raises(MathError) as exc:
        interpret("x^2", intent, options)
    assert exc.value.code is ErrorCode.INVALID_INPUT_FOR_INTENT
    assert exc.value.message == message


def test_options_need_an_explicit_intent() -> None:
    with pytest.raises(MathError) as exc:
        interpret("x^2", None, {"order": 2})
    assert exc.value.code is ErrorCode.INVALID_INPUT_FOR_INTENT


def test_unknown_intent() -> None:
    with pytest.raises(MathError) as exc:
        interpret("x^2", "teleport")
    assert exc.value.code is ErrorCode.UNSUPPORTED_INTENT

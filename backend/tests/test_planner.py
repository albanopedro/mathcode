"""Compound requests become a plan of ordinary requests (Phase 12, ADR 0021)."""

import subprocess
import sys

import pytest

from app.core.errors import ErrorCode, MathError
from app.interpreter.planner import MAX_STEPS, ExecutionPlan, plan_request
from app.models.intents import IntentName as I


def plan(text: str) -> ExecutionPlan:
    found = plan_request(text)
    assert found is not None
    return found


def steps(text: str) -> list[tuple[str, I, str, dict[str, str | int]]]:
    return [(s.title, s.intent, s.input, s.options) for s in plan(text).steps]


def test_a_list_of_calculations() -> None:
    assert steps("raízes, vértice e gráfico de x^2 - 4x + 3") == [
        ("Raízes", I.SOLVE_EQUATION, "x^2 - 4x + 3 = 0", {"variable": "x"}),
        ("Vértice", I.EXTREMA, "x^2 - 4x + 3", {"variable": "x"}),
        ("Gráfico", I.GRAPH, "x^2 - 4x + 3", {}),
    ]


def test_words_around_and_the_name_of_the_function() -> None:
    found = plan("Calcule as raízes e o vértice da função f(x) = x² - 4x + 3?")
    assert found.function == "x² - 4x + 3"
    assert [s.intent for s in found.steps] == [I.SOLVE_EQUATION, I.EXTREMA]


def test_the_study_of_a_function() -> None:
    found = plan("estude a função x^3 - 3x")
    assert found.rule == "study"
    assert [s.title for s in found.steps] == [
        "Raízes",
        "Valor em x = 0",
        "Derivada",
        "Máximos e mínimos",
        "Gráfico",
    ]
    assert found.steps[1].input == "(0)^3 - 3*(0)"


@pytest.mark.parametrize(
    "text",
    [
        "faça o estudo da função y = x^2 - 1",
        "análise completa de x^2 - 1",
        "analise x^2 - 1",
        "estudo da parábola x^2 - 1",
    ],
)
def test_ways_to_ask_for_a_study(text: str) -> None:
    assert plan(text).rule == "study"


def test_the_variable_and_the_second_derivative() -> None:
    assert steps("derivada e segunda derivada de t^3 em relação a t") == [
        ("Derivada", I.DERIVATIVE, "t^3", {"variable": "t"}),
        ("Segunda derivada", I.DERIVATIVE, "t^3", {"variable": "t", "order": 2}),
    ]


def test_the_same_calculation_asked_twice_is_one_step() -> None:
    assert [s.title for s in plan("vértice, máximo e gráfico de x^2").steps] == [
        "Vértice",
        "Gráfico",
    ]


@pytest.mark.parametrize(
    "text",
    [
        "raízes de x^2 - 4",  # one calculation: the usual rules
        "gráfico de sen(x) e cos(x)",  # "e" between functions
        "média e mediana de 1, 2, 3",  # statistics
        "o máximo e o mínimo de x^3 - 3x",  # one calculation, said twice
        "derivada e integral de x ao quadrado",  # math in words: the AI, if allowed
        "2 + 2",
    ],
)
def test_not_a_plan(text: str) -> None:
    assert plan_request(text) is None


@pytest.mark.parametrize(
    ("text", "code"),
    [
        ("raízes e gráfico de x^2 = 4", ErrorCode.INVALID_INPUT_FOR_INTENT),
        ("raízes e gráfico de 5", ErrorCode.INVALID_INPUT_FOR_INTENT),
        ("raízes e derivada de x + y", ErrorCode.AMBIGUOUS_INPUT),
    ],
)
def test_a_plan_of_what_is_not_a_function_is_explained(text: str, code: ErrorCode) -> None:
    with pytest.raises(MathError) as exc:
        plan_request(text)
    assert exc.value.code is code


def test_at_most_six_steps() -> None:
    every = "raízes, vértice, derivada, segunda derivada, integral, gráfico e fatoração de x^2"
    with pytest.raises(MathError) as exc:
        plan_request(every)
    assert str(MAX_STEPS) in exc.value.message


def test_the_planner_does_not_import_sympy() -> None:
    # It runs in the API process, which never imports SymPy (core/workers.py).
    code = "import sys, app.assistant, app.interpreter.planner; print('sympy' in sys.modules)"
    out = subprocess.run(  # noqa: S603 - fixed code, this interpreter
        [sys.executable, "-c", code], capture_output=True, text=True, check=True
    )
    assert out.stdout.strip() == "False"

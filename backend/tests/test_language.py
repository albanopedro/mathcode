"""Requests in Portuguese, read by local rules (no AI)."""

import pytest

from app.calculator import calculate
from app.core.errors import ErrorCode, MathError
from app.interpreter.language import LanguageMatch, match_language
from app.models.intents import IntentName as I


def match(text: str) -> LanguageMatch:
    found = match_language(text)
    assert found is not None, text
    return found


@pytest.mark.parametrize(
    "text",
    ["2 + 2", "x^2 + 3x", "a + b", "e^x", "sen(x)/x", "x + y = 3; x - y = 1", "2x + 5 = 17"],
)
def test_plain_math_is_not_a_phrase(text: str) -> None:
    assert match_language(text) is None


@pytest.mark.parametrize(
    ("text", "intent", "expression", "options"),
    [
        # the examples of the project brief
        ("derive x² + 3x", I.DERIVATIVE, "x² + 3x", {}),
        ("qual a derivada de x² + 3x?", I.DERIVATIVE, "x² + 3x", {}),
        ("integre sen(x)", I.INTEGRAL, "sen(x)", {}),
        ("fatore x² - 4", I.FACTOR, "x² - 4", {}),
        ("simplifique x² + 2x + x²", I.SIMPLIFY, "x² + 2x + x²", {}),
        ("resolve 2x + 5 = 17", None, "2x + 5 = 17", {}),
        ("15% de 780", I.ARITHMETIC, "15/100*(780)", {}),
        ("faça o gráfico de x² - 4x + 3", I.GRAPH, "x² - 4x + 3", {}),
        (
            "calcule o limite de sin(x)/x quando x tende a 0",
            I.LIMIT,
            "sin(x)/x",
            {"variable": "x", "point": "0", "side": "both"},
        ),
        # derivatives
        ("Qual é a segunda derivada de x^3?", I.DERIVATIVE, "x^3", {"order": 2}),
        ("derivada de ordem 3 de sen(x)", I.DERIVATIVE, "sen(x)", {"order": 3}),
        ("derive x y^2 em relação a y", I.DERIVATIVE, "x y^2", {"variable": "y"}),
        # integrals
        ("integral de x^2 de 0 a 1", I.INTEGRAL, "x^2", {"lower": "0", "upper": "1"}),
        ("integral de x^2 entre 0 e 1", I.INTEGRAL, "x^2", {"lower": "0", "upper": "1"}),
        ("integral de x^2 dx", I.INTEGRAL, "x^2", {"variable": "x"}),
        (
            "integral de e^(-x^2) de menos infinito a infinito",
            I.INTEGRAL,
            "e^(-x^2)",
            {"lower": "-infinito", "upper": "infinito"},
        ),
        # limits
        (
            "limite de 1/x quando x tende a 0+",
            I.LIMIT,
            "1/x",
            {"variable": "x", "point": "0", "side": "right"},
        ),
        (
            "lim de 1/x com x tendendo a 0 pela esquerda",
            I.LIMIT,
            "1/x",
            {"variable": "x", "point": "0", "side": "left"},
        ),
        (
            "limite de (1+1/x)^x quando x → infinito",
            I.LIMIT,
            "(1+1/x)^x",
            {"variable": "x", "point": "infinito", "side": "both"},
        ),
        # equations
        ("raízes de x² - 5x + 6", I.SOLVE_EQUATION, "x² - 5x + 6 = 0", {}),
        ("resolva x^2 - 4", I.SOLVE_EQUATION, "x^2 - 4 = 0", {}),
        ("resolva o sistema x + y = 3; x - y = 1", None, "x + y = 3; x - y = 1", {}),
        # graphs
        ("plote tan(x)", I.GRAPH, "tan(x)", {}),
        (
            "gráfico de sen(x) e cos(x) de -2pi a 2pi",
            I.GRAPH,
            "sen(x); cos(x)",
            {"x_min": "-2pi", "x_max": "2pi"},
        ),
        # others
        ("expanda (x+1)^3", I.EXPAND, "(x+1)^3", {}),
        ("divida x^3 - 1 por x - 1", I.POLYNOMIAL_DIVISION, "(x^3 - 1)/(x - 1)", {}),
        ("divida 10 por 4", None, "(10)/(4)", {}),
        ("quanto é 2^10?", None, "2^10", {}),
        ("qual o valor de 0.1 + 0.2", None, "0.1 + 0.2", {}),
        ("Por favor, me diga quanto é 3 * 4", None, "3 * 4", {}),
        ("GRÁFICO DE X^2", I.GRAPH, "X^2", {}),  # case and accents do not matter
    ],
)
def test_phrases(text: str, intent: I | None, expression: str, options: dict) -> None:
    found = match(text)
    assert (found.intent, found.text, found.options) == (intent, expression, options)


def test_the_math_text_is_cut_from_what_was_typed() -> None:
    found = match("qual a derivada de x² + 3x?")
    assert found.offset == 19
    assert "qual a derivada de x² + 3x?"[found.offset :].startswith("x² + 3x")


@pytest.mark.parametrize(
    "text",
    [
        "qual a média de 10, 20, 30?",
        "calcule o determinante dessa matriz",
        "qual o vértice dessa função?",
    ],
)
def test_future_features_are_explained(text: str) -> None:
    with pytest.raises(MathError) as exc:
        match_language(text)
    assert exc.value.code is ErrorCode.UNSUPPORTED_FEATURE


# -- through the whole pipeline -----------------------------------------------------------------


def test_phrase_result_carries_its_interpretation() -> None:
    result = calculate("qual a derivada de x² + 3x?")
    assert result.success
    assert result.result is not None and result.result.plain == "2*x + 3"
    assert result.input == "qual a derivada de x² + 3x?"
    assert result.interpretation is not None
    assert result.interpretation.method == "rules"
    assert result.interpretation.intent is I.DERIVATIVE
    assert result.interpretation.expression == "x² + 3x"


def test_auto_detected_phrase_gets_the_final_intent() -> None:
    result = calculate("resolve 2x + 5 = 17")
    assert result.interpretation is not None
    assert result.interpretation.intent is I.SOLVE_EQUATION


def test_error_positions_point_into_the_phrase() -> None:
    result = calculate("derive x² +")
    assert result.error is not None
    assert result.error.position == len("derive x² +")  # the end of what was typed
    assert result.interpretation is not None


def test_rewritten_text_drops_the_position() -> None:
    """'15% de 2 +' became '15/100*(2 +)': a position would point at nothing."""
    result = calculate("15% de 2 +")
    assert result.error is not None
    assert result.error.position is None


def test_explicit_operation_skips_the_rules() -> None:
    result = calculate("derive x", intent="simplify")
    assert result.error is not None  # "derive" is not math: no rule was applied
    assert result.interpretation is None


def test_plain_math_has_no_interpretation() -> None:
    assert calculate("2 + 2").interpretation is None

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
        "qual a área de um círculo de raio 5?",
        "qual a probabilidade de tirar 6 num dado?",
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


# -- statistics (Phase 10) ------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("text", "data", "measure"),
    [
        ("qual a média de 10, 20, 30?", "10, 20, 30", "mean"),
        ("média de 10, 20 e 30", "10, 20; 30", "mean"),  # the final "e" is a separator
        ("calcule a média das notas 7, 8 e 9,5", "7, 8; 9,5", "mean"),
        ("a mediana dos números 3; 1; 2", "3; 1; 2", "median"),
        ("moda de 1, 1, 2", "1, 1, 2", "mode"),
        ("desvio padrão de 2, 4, 4", "2, 4, 4", "std"),
        ("desvio-padrão amostral de 1, 2, 3", "1, 2, 3", "sample_std"),
        ("variância populacional de 1, 2", "1, 2", "variance"),
        ("variância amostral de 1, 2", "1, 2", "sample_variance"),
        ("amplitude de 4, 9, 1", "4, 9, 1", "range"),
        ("qual o maior valor de 3, -7, 2", "3, -7, 2", "max"),
        ("mínimo de 3, 7, 2", "3, 7, 2", "min"),
        ("soma de 1/2, 1/3", "1/2, 1/3", "sum"),
        ("média: 2, 4", "2, 4", "mean"),
    ],
)
def test_statistics_phrases(text: str, data: str, measure: str) -> None:
    found = match_language(text)
    assert found is not None
    assert found.intent is I.STATISTICS
    assert found.text == data
    assert found.options == {"measure": measure}


def test_statistics_summary_phrase() -> None:
    found = match_language("estatísticas de 10, 20, 30")
    assert found is not None and found.intent is I.STATISTICS and found.options == {}


def test_maximum_of_a_function_is_still_future() -> None:
    with pytest.raises(MathError) as exc:
        match_language("máximo de x^2 - 4x")
    assert exc.value.code is ErrorCode.UNSUPPORTED_FEATURE


def test_statistics_without_numbers_explains_the_format() -> None:
    with pytest.raises(MathError) as exc:
        match_language("média das idades da turma")
    assert "média de 10, 20, 30" in exc.value.message


def test_statistics_phrase_through_the_pipeline() -> None:
    result = calculate("qual a média de 10, 20, 30?")
    assert result.success and result.intent is I.STATISTICS
    assert result.result is not None and result.result.plain == "média = 20"
    assert result.interpretation is not None and result.interpretation.method == "rules"


def test_statistics_error_points_into_the_phrase() -> None:
    result = calculate("média de 10, 20, 1/0")
    assert result.error is not None and result.error.code is ErrorCode.DIVISION_BY_ZERO
    assert result.error.position == "média de 10, 20, 1/0".index("/")


def test_statistics_phrase_with_a_variable_explains_the_format() -> None:
    result = calculate("média de 10, 20, x")
    assert result.error is not None
    assert "média de 10, 20, 30" in result.error.message


# -- matrices (Phase 10) --------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("text", "operation"),
    [
        ("determinante de [[1, 2], [3, 4]]", "determinant"),
        ("calcule o determinante da matriz [[1, 2], [3, 4]]", "determinant"),
        ("qual a inversa de [[1, 2], [3, 4]]?", "inverse"),
        ("matriz inversa de [[1, 2], [3, 4]]", "inverse"),
        ("transposta de [[1, 2], [3, 4]]", "transpose"),
        ("o traço da matriz [[1, 2], [3, 4]]", "trace"),
        ("posto de [[1, 2], [3, 4]]", "rank"),
        ("determinante: [[1, 2], [3, 4]]", "determinant"),
    ],
)
def test_matrix_phrases(text: str, operation: str) -> None:
    found = match_language(text)
    assert found is not None
    assert found.intent is I.MATRIX
    assert found.text == "[[1, 2], [3, 4]]"
    assert found.options == {"operation": operation}
    assert text[found.offset :].startswith("[[1, 2]")


def test_matrix_words_without_brackets_explain_the_syntax() -> None:
    with pytest.raises(MathError) as exc:
        match_language("calcule o determinante dessa matriz")
    assert "[[1, 2], [3, 4]]" in exc.value.message


def test_inverse_of_a_function_is_not_a_matrix() -> None:
    assert match_language("inversa de x^2") is None


# -- vectors (Phase 10) ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("text", "data", "operation"),
    [
        ("norma de [3, 4]", "[3, 4]", "norm"),
        ("qual o módulo do vetor [3, 4]?", "[3, 4]", "norm"),
        ("vetor unitário de [3, 4]", "[3, 4]", "unit"),
        ("produto escalar de [1, 2] e [3, 4]", "[1, 2]; [3, 4]", "dot"),
        ("calcule o produto escalar dos vetores [1, 2]; [3, 4]", "[1, 2]; [3, 4]", "dot"),
        ("o produto vetorial entre [1, 0, 0] e [0, 1, 0]", "[1, 0, 0]; [0, 1, 0]", "cross"),
        ("ângulo entre os vetores [1, 0] e [1, 1]", "[1, 0]; [1, 1]", "angle"),
    ],
)
def test_vector_phrases(text: str, data: str, operation: str) -> None:
    found = match_language(text)
    assert found is not None
    assert found.intent is I.VECTOR
    assert found.text == data
    assert found.options == {"operation": operation}


def test_vector_words_without_brackets_explain_the_syntax() -> None:
    with pytest.raises(MathError) as exc:
        match_language("produto escalar de u e v")
    assert "[1, 2]" in exc.value.message

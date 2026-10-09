"""Requests in Portuguese, read by local rules (no AI)."""

import pytest

from app.ai import needs_ai
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
        "qual o máximo de x^2 - 4x?",
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


# -- geometry (Phase 10) --------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("text", "measures", "figure", "calculation"),
    [
        ("qual a área de um círculo de raio 5?", "r = 5", "circle", "area"),
        ("comprimento da circunferência de raio 2", "r = 2", "circle", "perimeter"),
        ("perímetro do quadrado de lado 4", "l = 4", "square", "perimeter"),
        ("área do retângulo de base 4 e altura 3", "b = 4; h = 3", "rectangle", "area"),
        ("área do triângulo de lados 3, 4 e 5", "a = 3; b = 4; c = 5", "triangle", "area"),
        (
            "classifique o triângulo de lados 2, 2 e 3",
            "a = 2; b = 2; c = 3",
            "triangle",
            "classify",
        ),
        ("área do trapézio de bases 6 e 4 e altura 3", "B = 6; b = 4; h = 3", "trapezoid", "area"),
        ("área do losango de diagonais 6 e 8", "D = 6; d = 8", "rhombus", "area"),
        ("área da esfera de raio 3", "r = 3", "sphere", "surface_area"),  # a solid: its surface
        ("volume do cilindro de raio 2 e altura 5", "r = 2; h = 5", "cylinder", "volume"),
        (
            "volume do paralelepípedo de comprimento 2, largura 3 e altura 4",
            "a = 2; b = 3; c = 4",
            "box",
            "volume",
        ),
        (
            "hipotenusa de um triângulo de catetos 3 e 4",
            "a = 3; b = 4",
            "right_triangle",
            "missing_side",
        ),
        (
            "cateto do triângulo retângulo de hipotenusa 13 e cateto 5",
            "c = 13; a = 5",
            "right_triangle",
            "missing_side",
        ),
        ("distância entre (1, 2) e (4, 6)", "(1, 2); (4, 6)", "points", "distance"),
        ("ponto médio entre (1, 2) e (3, 4)", "(1, 2); (3, 4)", "points", "midpoint"),
        ("equação da reta que passa por (1, 2) e (3, 4)", "(1, 2); (3, 4)", "points", "line"),
        (
            "área do polígono de vértices (0, 0), (4, 0), (4, 3) e (0, 3)",
            "(0, 0); (4, 0); (4, 3); (0, 3)",
            "points",
            "polygon_area",
        ),
    ],
)
def test_geometry_phrases(text: str, measures: str, figure: str, calculation: str) -> None:
    found = match_language(text)
    assert found is not None
    assert found.intent is I.GEOMETRY
    assert found.text == measures
    assert found.options == {"figure": figure, "calculation": calculation}


def test_geometry_phrase_without_measures_explains() -> None:
    with pytest.raises(MathError) as exc:
        match_language("área do círculo")
    assert "raio 5" in exc.value.message


def test_area_under_a_curve_is_not_geometry() -> None:
    assert match_language("área sob a curva de x^2 de 0 a 2") is None


def test_geometry_phrase_through_the_pipeline() -> None:
    result = calculate("qual a área de um círculo de raio 5?")
    assert result.success and result.intent is I.GEOMETRY
    assert result.result is not None and result.result.plain == "A = 25*pi"


# -- probability and counting (Phase 10) ----------------------------------------------------------


@pytest.mark.parametrize(
    ("text", "data", "calculation"),
    [
        ("qual o fatorial de 6?", "n = 6", "factorial"),
        ("8 fatorial", "n = 8", "factorial"),
        ("permutação de 5 elementos", "n = 5", "factorial"),
        ("quantas permutações de 4?", "n = 4", "factorial"),
        ("combinação de 10 tomados 3 a 3", "n = 10; k = 3", "combination"),
        ("quantas combinações de 10 elementos 3 a 3?", "n = 10; k = 3", "combination"),
        ("combinações de 10, 3 a 3", "n = 10; k = 3", "combination"),
        ("arranjo de 6 tomados 2 a 2", "n = 6; k = 2", "arrangement"),
        ("arranjos com repetição de 3 tomados 2 a 2", "n = 3; k = 2", "arrangement_repetition"),
        (
            "combinação com repetição de 3 tomados 2 a 2",
            "n = 3; k = 2",
            "combination_repetition",
        ),
        ("anagramas de BANANA", "BANANA", "anagrams"),
        ("quantos anagramas tem a palavra BANANA?", "BANANA", "anagrams"),
        ("número de anagramas da palavra matemática", "matemática", "anagrams"),
        ("binomial com n = 5, k = 3 e p = 1/2", "n = 5, k = 3; p = 1/2", "binomial_exact"),
        (
            "distribuição binomial no máximo n = 5; k = 3; p = 0,5",
            "n = 5; k = 3; p = 0,5",
            "binomial_at_most",
        ),
        (
            "probabilidade binomial pelo menos com n = 5, k = 3 e p = 50%",
            "n = 5, k = 3; p = 50%",
            "binomial_at_least",
        ),
        (
            "média e variância da binomial com n = 10 e p = 0,3",
            "n = 10; p = 0,3",
            "binomial_summary",
        ),
        (
            "probabilidade de A ou B com P(A) = 1/2, P(B) = 1/3 e P(A e B) = 1/6",
            "P(A) = 1/2, P(B) = 1/3; P(A e B) = 1/6",
            "union",
        ),
        (
            "probabilidade de A ou B com P(A) = 0,5 e P(B) = 0,3, independentes",
            "P(A) = 0,5; P(B) = 0,3",
            "union_independent",
        ),
        (
            "probabilidade de A e B, independentes, com P(A) = 1/2 e P(B) = 1/3",
            "P(A) = 1/2; P(B) = 1/3",
            "intersection_independent",
        ),
        ("qual a probabilidade de não A sendo P(A) = 30%?", "P(A) = 30%", "complement"),
        (
            "probabilidade de A dado B com P(A e B) = 0,1 e P(B) = 0,4",
            "P(A e B) = 0,1; P(B) = 0,4",
            "conditional",
        ),
        (
            "P(A ∪ B) com P(A) = 1/2, P(B) = 1/3 e P(A ∩ B) = 1/6",
            "P(A) = 1/2, P(B) = 1/3; P(A ∩ B) = 1/6",
            "union",
        ),
    ],
)
def test_probability_phrases(text: str, data: str, calculation: str) -> None:
    found = match(text)
    assert found.intent is I.PROBABILITY
    assert found.text == data
    assert found.options == {"calculation": calculation}


def test_probability_phrase_through_the_pipeline() -> None:
    result = calculate("quantos anagramas tem a palavra BANANA?")
    assert result.success and result.intent is I.PROBABILITY
    assert result.result is not None and result.result.plain == "anagramas de BANANA = 60"


def test_a_factorial_at_the_end_of_a_phrase_is_kept() -> None:
    assert match("quanto é 5!").text == "5!"
    assert match("calcule (2 + 1)!?").text == "(2 + 1)!"
    assert match("quanto é dois mais dois!").text == "dois mais dois"  # punctuation


def test_probability_word_problems_go_to_the_ai() -> None:
    # No rule can model "tirar 6 num dado": with "Permitir IA", the AI translates it.
    assert needs_ai("qual a probabilidade de tirar 6 num dado?")


# -- trigonometry (Phase 10) ----------------------------------------------------------------------


@pytest.mark.parametrize(
    ("text", "expression", "calculation"),
    [
        ("converta 30° para radianos", "30°", "convert"),
        ("30 graus em radianos", "30°", "convert"),
        ("pi/6 em graus", "pi/6", "convert"),
        ("converter pi/4 rad para graus", "pi/4", "convert"),
        ("reduza 150° ao primeiro quadrante", "150°", "reduce"),
        ("redução de 210 graus ao 1º quadrante", "210°", "reduce"),
        ("redução ao primeiro quadrante de sin(150°)", "sin(150°)", "reduce"),
        ("em que quadrante está o ângulo de 300°?", "300°", "reduce"),
        ("verifique a identidade sin(x)^2 + cos(x)^2 = 1", "sin(x)^2 + cos(x)^2 = 1", "identity"),
        ("prove que sin(2x) = 2sin(x)cos(x)", "sin(2x) = 2sin(x)cos(x)", "identity"),
        ("tan(x) = sin(x) é uma identidade?", "tan(x) = sin(x)", "identity"),
        ("resolva o triângulo com a = 5, b = 7 e C = 60°", "a = 5, b = 7; C = 60°", "triangle"),
        (
            "lei dos senos com a = 10, B = 30 graus e C = 45°",
            "a = 10, B = 30°; C = 45°",
            "triangle",
        ),
        ("quais os ângulos do triângulo de lados 3, 4 e 5?", "a = 3; b = 4; c = 5", "triangle"),
    ],
)
def test_trigonometry_phrases(text: str, expression: str, calculation: str) -> None:
    found = match(text)
    assert found.intent is I.TRIGONOMETRY
    assert found.text == expression
    assert found.options == {"calculation": calculation}


@pytest.mark.parametrize(
    ("text", "equation", "lower", "upper"),
    [
        ("resolva sin(x) = 1/2 de 0 a 4pi", "sin(x) = 1/2", "0", "4pi"),
        ("resolva sin(x) = 1/2 no intervalo [0, pi]", "sin(x) = 1/2", "0", "pi"),
        ("raízes de cos(x) entre 0 e 2pi", "cos(x) = 0", "0", "2pi"),
        ("resolva tan(x) = 1 entre menos pi e pi", "tan(x) = 1", "-pi", "pi"),
    ],
)
def test_equations_with_an_interval(text: str, equation: str, lower: str, upper: str) -> None:
    found = match(text)
    assert found.intent is I.SOLVE_EQUATION
    assert found.text == equation
    assert found.options == {"lower": lower, "upper": upper}


def test_show_the_graph_is_not_an_identity() -> None:
    assert match("mostre o gráfico de y = x^2").intent is I.GRAPH

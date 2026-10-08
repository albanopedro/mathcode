"""Rule-based interpretation of requests in Portuguese (Phase 8): local, no AI.

"qual a derivada de x² + 3x?" becomes the operation ``derivative`` and the math
text ``x² + 3x``. The rules only *split* the request: the math text still goes
through the safe parser (ADR 0002), and words never become code.

Keywords are matched without accents and case ("grafico" = "Gráfico"), but
the math text is cut from what the user typed, so "x²" stays "x²".
"""

import re
import unicodedata
from collections.abc import Callable
from dataclasses import dataclass, field

from app.core.errors import ErrorCode, MathError
from app.models.intents import IntentName
from app.parsing import parse
from app.parsing.ast import variables

type Options = dict[str, str | int]


@dataclass(frozen=True)
class LanguageMatch:
    # None: the operation is detected from the math text, as usual.
    intent: IntentName | None
    text: str  # the math part
    options: Options = field(default_factory=dict)
    # Where ``text`` starts in the request, so error positions still point at
    # what the user typed. None when the rule rewrote the text.
    offset: int | None = None
    rule: str = ""


def match_language(request: str) -> LanguageMatch | None:
    """The operation asked for in words, or None if this is not a phrase."""
    folded = _fold(request)
    start, end = 0, len(request)
    while end > start and folded[end - 1] in "?.! \t":
        end -= 1

    stripped = False
    for _ in range(6):
        lead = _LEADS.match(folded, start, end)
        if lead is None:
            break
        start, stripped = lead.end(), True
    article = _ARTICLE.match(folded, start, end)
    if article is not None:
        start = article.end()

    for name, pattern, build in _RULES:
        found = pattern.fullmatch(folded, start, end)
        if found is not None:
            return build(found, request, name)

    if stripped and start < end:
        # "quanto é 2 + 2?": only filler words around a math expression.
        return LanguageMatch(None, request[start:end].strip(), offset=start, rule="filler")
    return None


def _fold(text: str) -> str:
    """Lowercase without accents, one character for each character of ``text``."""
    return "".join(unicodedata.normalize("NFD", ch)[0].lower() for ch in text)


# -- words around the request --------------------------------------------------------------------

_LEADS = re.compile(
    r"(?:por\s+favor,?|me\s+(?:diga|mostre|de|da|ajude\s+a|ajuda\s+a)|voce\s+pode|pode|poderia"
    r"|qual\s+(?:e|eh|seria)|quais\s+(?:sao|seriam)|quanto\s+(?:e|eh|vale|da|daria)|quanto"
    r"|calcule|calcular|calcula|encontre|encontrar|ache|achar|determine|obtenha|qual|quais"
    r"|(?:o\s+)?valor\s+(?:de|da|do))\s+"
)
_KEYWORD = (
    r"(?:derivada|integral|primitiva|limite|grafico|raizes|raiz|zeros|zero|fatoracao"
    r"|simplificacao|segunda|terceira|quarta|quinta|media|mediana|moda|desvio|variancia"
    r"|amplitude|soma|resumo|estatisticas?|maior|menor|valor|inversa|transposta|traco|posto"
    r"|norma|modulo|comprimento|vetor|versor|produto|angulo"
    r"|perimetro|volume|distancia|ponto|reta|equacao|hipotenusa|cateto|classificacao"
    r"|determinante|matriz|area|perimetro|volume|probabilidade|vertice|maximo|minimo)"
)
_ARTICLE = re.compile(rf"(?:o|a|os|as)\s+(?={_KEYWORD})")

_OF = r"(?:\s+(?:de|da\s+funcao|das\s+funcoes|do\s+polinomio|da\s+expressao|do|da))?"
_VAR = r"(?:\s+em\s+relacao\s+(?:a|ao)\s+(?P<var>[a-z]))?"
_BOUNDS = (
    r"(?:\s+(?:de|entre|no\s+intervalo\s+de|para\s+x\s+de)\s+(?P<a>(?:menos\s+|mais\s+)?\S+)"
    r"\s+(?:a|ate|e)\s+(?P<b>(?:menos\s+|mais\s+)?\S+))?"
)

# -- builders ----------------------------------------------------------------------------------


def _grab(found: re.Match[str], request: str, group: str) -> str | None:
    if found.group(group) is None:
        return None
    return request[found.start(group) : found.end(group)].strip()


def _bound(text: str | None) -> str | None:
    """'menos infinito' -> '-infinito'; the value itself is read by the safe parser."""
    if text is None:
        return None
    folded = _fold(text)
    if folded.startswith("menos "):
        return "-" + text[6:].strip()
    if folded.startswith("mais "):
        return text[5:].strip()
    return text


def _plain(intent: IntentName | None) -> Callable[[re.Match[str], str, str], LanguageMatch]:
    def build(found: re.Match[str], request: str, rule: str) -> LanguageMatch:
        expr = _grab(found, request, "expr") or ""
        return LanguageMatch(intent, expr, offset=found.start("expr"), rule=rule)

    return build


_ORDINALS = {"segunda": 2, "terceira": 3, "quarta": 4, "quinta": 5}


def _derivative(found: re.Match[str], request: str, rule: str) -> LanguageMatch:
    options: Options = {}
    if found.group("ordw"):
        options["order"] = _ORDINALS[found.group("ordw")]
    elif found.group("ordn"):
        options["order"] = int(found.group("ordn"))
    if found.group("var"):
        options["variable"] = found.group("var")
    expr = _grab(found, request, "expr") or ""
    return LanguageMatch(
        IntentName.DERIVATIVE, expr, options, offset=found.start("expr"), rule=rule
    )


_DIFFERENTIAL = re.compile(r"\s*\bd(?P<var>[a-z])$")


def _integral(found: re.Match[str], request: str, rule: str) -> LanguageMatch:
    expr = _grab(found, request, "expr") or ""
    options: Options = {}
    differential = _DIFFERENTIAL.search(_fold(expr))
    if differential and len(expr) > differential.end() - differential.start():
        options["variable"] = differential.group("var")  # "x^2 dx"
        expr = expr[: differential.start()].rstrip()
    if found.group("var"):
        options["variable"] = found.group("var")
    lower, upper = _bound(_grab(found, request, "a")), _bound(_grab(found, request, "b"))
    if lower is not None and upper is not None:
        options |= {"lower": lower, "upper": upper}
    return LanguageMatch(IntentName.INTEGRAL, expr, options, offset=found.start("expr"), rule=rule)


def _limit(found: re.Match[str], request: str, rule: str) -> LanguageMatch:
    point = _bound(_grab(found, request, "point")) or ""
    side = "both"
    if found.group("sign"):
        side = "right" if found.group("sign") == "+" else "left"
    if found.group("side"):
        side = "left" if found.group("side") == "esquerda" else "right"
    options: Options = {"variable": found.group("var"), "point": point, "side": side}
    expr = _grab(found, request, "expr") or ""
    return LanguageMatch(IntentName.LIMIT, expr, options, offset=found.start("expr"), rule=rule)


def _roots(found: re.Match[str], request: str, rule: str) -> LanguageMatch:
    """'raízes de x² - 4' and 'resolva x² - 4' mean f(x) = 0."""
    expr = _grab(found, request, "expr") or ""
    if "=" in expr:
        return LanguageMatch(None, expr, offset=found.start("expr"), rule=rule)
    return LanguageMatch(IntentName.SOLVE_EQUATION, f"{expr} = 0", rule=rule)


def _graph(found: re.Match[str], request: str, rule: str) -> LanguageMatch:
    expr = _grab(found, request, "expr") or ""
    # "gráfico de sen(x) e cos(x)": "e" between functions is a list separator.
    listed = re.sub(r"\s+e\s+", "; ", expr)
    options: Options = {}
    lower, upper = _bound(_grab(found, request, "a")), _bound(_grab(found, request, "b"))
    if lower is not None and upper is not None:
        options |= {"x_min": lower, "x_max": upper}
    offset = found.start("expr") if listed == expr else None
    return LanguageMatch(IntentName.GRAPH, listed, options, offset=offset, rule=rule)


def _divide(found: re.Match[str], request: str, rule: str) -> LanguageMatch:
    text = f"({_grab(found, request, 'a')})/({_grab(found, request, 'b')})"
    try:
        has_variables = bool(variables(parse(text).tree))
    except MathError:
        has_variables = False  # the pipeline will explain the problem
    intent = IntentName.POLYNOMIAL_DIVISION if has_variables else None
    return LanguageMatch(intent, text, rule=rule)


def _percent(found: re.Match[str], request: str, rule: str) -> LanguageMatch:
    """'15% de 780' is (15/100)·780."""
    text = f"{_grab(found, request, 'p')}/100*({_grab(found, request, 'm')})"
    return LanguageMatch(IntentName.ARITHMETIC, text, rule=rule)


# -- statistics (Phase 10, ADR 0011) -------------------------------------------------------------

_NUMBER = r"[-+\u2212]?\s*\d+(?:[.,]\d+)?(?:\s*/\s*\d+(?:[.,]\d+)?)?"
# Values separated by "; ", ", " (with a space: "1,5" is a decimal) or a final " e ".
_DATA = rf"(?P<data>{_NUMBER}(?:\s*(?:;|,\s|\se\s)\s*{_NUMBER})*)"
_MEASURE = (
    r"(?:(?P<std>desvio[\s-]+padrao(?:\s+(?P<std_kind>amostral|populacional))?)"
    r"|(?P<variance>variancia(?:\s+(?P<variance_kind>amostral|populacional))?)"
    r"|(?P<median>mediana)"
    r"|(?P<mean>media(?:\s+aritmetica)?)"
    r"|(?P<mode>moda)"
    r"|(?P<range>amplitude(?:\s+total)?)"
    r"|(?P<sum>soma)"
    r"|(?P<max>(?:valor\s+)?maximo|maior\s+valor)"
    r"|(?P<min>(?:valor\s+)?minimo|menor\s+valor)"
    r"|(?P<summary>resumo\s+estatistico|estatisticas?|medidas\s+estatisticas))"
)
# Up to four words between the measure and the numbers: "média das notas 7, 8 e 9,5".
_FILLER = r"(?:\s+(?!e\b)[a-z]+){0,4}?\s*:?"


def _statistics(found: re.Match[str], request: str, rule: str) -> LanguageMatch:
    measure: str | None = None
    for name in ("std", "variance", "median", "mean", "mode", "range", "sum", "max", "min"):
        if found.group(name):
            measure = name
    if measure in ("std", "variance") and found.group(f"{measure}_kind") == "amostral":
        measure = f"sample_{measure}"
    data = _grab(found, request, "data") or ""
    listed = re.sub(r"\s+e\s+", "; ", data)  # "10, 20 e 30"
    options: Options = {} if measure is None else {"measure": measure}
    offset = found.start("data") if listed == data else None
    return LanguageMatch(IntentName.STATISTICS, listed, options, offset=offset, rule=rule)


def _statistics_without_data(found: re.Match[str], request: str, rule: str) -> LanguageMatch:
    raise MathError(
        ErrorCode.INVALID_INPUT_FOR_INTENT,
        "Para estatística, escreva os números separados por '; ' ou ', ', como em "
        "'média de 10, 20, 30' ou 'desvio padrão de 2; 4; 4; 5'.",
    )


# -- matrices (Phase 10, ADR 0012) ----------------------------------------------------------------

_MATRIX_OPERATIONS = {
    "determinante": "determinant",
    "inversa": "inverse",
    "transposta": "transpose",
    "traco": "trace",
    "posto": "rank",
}


def _matrix(found: re.Match[str], request: str, rule: str) -> LanguageMatch:
    operation = _MATRIX_OPERATIONS[found.group("op")]
    expr = _grab(found, request, "expr") or ""
    return LanguageMatch(
        IntentName.MATRIX, expr, {"operation": operation}, offset=found.start("expr"), rule=rule
    )


def _matrix_without_brackets(found: re.Match[str], request: str, rule: str) -> LanguageMatch:
    raise MathError(
        ErrorCode.INVALID_INPUT_FOR_INTENT,
        "Para matrizes, escreva os números entre colchetes, uma linha por colchete: "
        "'determinante de [[1, 2], [3, 4]]'.",
    )


# -- vectors (Phase 10, ADR 0013) -----------------------------------------------------------------

_VECTOR_OPERATIONS = {
    "norma": "norm",
    "modulo": "norm",
    "comprimento": "norm",
    "vetor unitario": "unit",
    "versor": "unit",
    "produto escalar": "dot",
    "produto interno": "dot",
    "produto vetorial": "cross",
    "angulo": "angle",
}


def _vector(found: re.Match[str], request: str, rule: str) -> LanguageMatch:
    operation = _VECTOR_OPERATIONS[re.sub(r"\s+", " ", found.group("op"))]
    expr = _grab(found, request, "expr") or ""
    listed = re.sub(r"\]\s+e\s+\[", "]; [", expr)  # "[1, 2] e [3, 4]"
    offset = found.start("expr") if listed == expr else None
    return LanguageMatch(
        IntentName.VECTOR, listed, {"operation": operation}, offset=offset, rule=rule
    )


def _vector_without_brackets(found: re.Match[str], request: str, rule: str) -> LanguageMatch:
    raise MathError(
        ErrorCode.INVALID_INPUT_FOR_INTENT,
        "Para vetores, escreva os componentes entre colchetes: 'produto escalar de [1, 2] e "
        "[3, 4]' ou 'norma de [3, 4]'.",
    )


# -- geometry (Phase 10, ADR 0014) ----------------------------------------------------------------

_FIGURES = {
    "circulo": "circle",
    "circunferencia": "circle",
    "quadrado": "square",
    "retangulo": "rectangle",
    "triangulo retangulo": "right_triangle",
    "triangulo": "triangle",
    "trapezio": "trapezoid",
    "losango": "rhombus",
    "paralelogramo": "parallelogram",
    "cubo": "cube",
    "paralelepipedo": "box",
    "esfera": "sphere",
    "cilindro": "cylinder",
    "cone": "cone",
}
_SOLIDS = {"cube", "box", "sphere", "cylinder", "cone"}
_GEOMETRY_VALUE = r"[-+]?\d+(?:[.,]\d+)?(?:\s*/\s*\d+(?:[.,]\d+)?)?"
_MEASURE_WORDS = (
    r"(?P<word>raio|diametro|lados|lado|bases|base\s+maior|base\s+menor|base|altura|aresta"
    r"|diagonais|diagonal\s+maior|diagonal\s+menor|catetos|cateto|hipotenusa|comprimento"
    r"|largura)"
)
_GEOMETRY_MEASURE = re.compile(
    rf"{_MEASURE_WORDS}\s*(?:de\s+|igual\s+a\s+|=\s*)?"
    rf"(?P<values>{_GEOMETRY_VALUE}(?:\s*(?:,|\be\b)\s*{_GEOMETRY_VALUE})*)"
)


def _measure_symbols(figure: str, word: str, count: int) -> list[str] | None:
    """The symbols that ``count`` values after ``word`` stand for, for this figure."""
    word = re.sub(r"\s+", " ", word)
    plural = {
        ("lados", 3): ["a", "b", "c"],
        ("bases", 2): ["B", "b"],
        ("diagonais", 2): ["D", "d"],
        ("catetos", 2): ["a", "b"],
    }
    if (word, count) in plural:
        return plural[(word, count)]
    if count != 1:
        return None
    single = {
        "raio": "r",
        "diametro": "d",
        "base maior": "B",
        "base menor": "b",
        "base": "b",
        "altura": "c" if figure == "box" else "h",
        "aresta": "a",
        "diagonal maior": "D",
        "diagonal menor": "d",
        "hipotenusa": "c",
        "comprimento": "a",
        "largura": "b",
        "lado": "l" if figure == "square" else None,
        "cateto": "a",
    }
    symbol = single.get(word)
    return None if symbol is None else [symbol]


def _geometry(found: re.Match[str], request: str, rule: str) -> LanguageMatch:
    figure = _FIGURES[re.sub(r"\s+", " ", found.group("figure"))]
    calculation = {
        "area": "surface_area" if figure in _SOLIDS else "area",
        "area da superficie": "surface_area",
        "area total": "surface_area",
        "perimetro": "perimeter",
        "comprimento": "perimeter",
        "volume": "volume",
        "classifique": "classify",
        "classificacao": "classify",
        "hipotenusa": "missing_side",
        "cateto": "missing_side",
    }[re.sub(r"\s+", " ", found.group("calc"))]
    if calculation == "missing_side":
        figure = "right_triangle"
    rest = _fold(request)[found.start("rest") : found.end("rest")]
    assignments: list[str] = []
    for measure in _GEOMETRY_MEASURE.finditer(rest):
        start, end = (
            found.start("rest") + measure.start("values"),
            found.start("rest") + measure.end("values"),
        )
        values = re.split(r"\s*(?:,\s|\be\b|,(?=\s*\D))\s*", request[start:end].strip())
        values = [v for v in values if v]
        symbols = _measure_symbols(figure, measure.group("word"), len(values))
        if symbols is None:
            continue
        taken = {a.split(" = ")[0] for a in assignments}
        if symbols == ["a"] and "a" in taken:  # "cateto 3" after another cateto
            symbols = ["b"]
        assignments += [f"{s} = {v}" for s, v in zip(symbols, values, strict=True)]
    if not assignments:
        raise MathError(
            ErrorCode.INVALID_INPUT_FOR_INTENT,
            "Informe as medidas com números, como em 'área do círculo de raio 5' ou 'volume "
            "do cilindro de raio 2 e altura 5'.",
        )
    options: Options = {"figure": figure, "calculation": calculation}
    return LanguageMatch(IntentName.GEOMETRY, "; ".join(assignments), options, rule=rule)


def _points(found: re.Match[str], request: str, rule: str) -> LanguageMatch:
    calculation = {
        "distancia": "distance",
        "ponto medio": "midpoint",
        "reta": "line",
        "equacao da reta": "line",
        "area do poligono": "polygon_area",
    }[re.sub(r"\s+", " ", found.group("calc"))]
    text = _grab(found, request, "points") or ""
    listed = re.sub(r"\)\s*(?:,|\be\b)\s*\(", "); (", text)
    options: Options = {"figure": "points", "calculation": calculation}
    return LanguageMatch(IntentName.GEOMETRY, listed, options, rule=rule)


def _geometry_without_figure(found: re.Match[str], request: str, rule: str) -> LanguageMatch:
    raise MathError(
        ErrorCode.INVALID_INPUT_FOR_INTENT,
        "Para geometria, escreva a figura e as medidas, como em 'área do círculo de raio 5', "
        "'volume da esfera de raio 3' ou 'distância entre (1, 2) e (4, 6)'.",
    )


def _future(found: re.Match[str], request: str, rule: str) -> LanguageMatch:
    raise MathError(
        ErrorCode.UNSUPPORTED_FEATURE,
        "Probabilidade e pontos como vértice e máximo de uma função ainda não são "
        "suportados; eles estão previstos para as próximas etapas.",
    )


# -- rules, in order ------------------------------------------------------------------------------

_RULES: list[tuple[str, re.Pattern[str], Callable[[re.Match[str], str, str], LanguageMatch]]] = [
    ("statistics", re.compile(rf"{_MEASURE}{_FILLER}\s+{_DATA}"), _statistics),
    (
        "statistics_without_data",
        re.compile(r"(?:media|mediana|moda|variancia|desvio[\s-]+padrao|amplitude)\b.*"),
        _statistics_without_data,
    ),
    (
        "matrix",
        re.compile(
            r"(?:(?:a\s+)?matriz\s+)?(?P<op>determinante|inversa|transposta|traco|posto)"
            r"(?:\s+(?:de|da|do))?(?:\s+(?:a\s+)?matriz)?\s*:?\s+(?P<expr>\[.*)"
        ),
        _matrix,
    ),
    (
        "vector",
        re.compile(
            r"(?P<op>norma|modulo|comprimento|vetor\s+unitario|versor|produto\s+escalar"
            r"|produto\s+interno|produto\s+vetorial|angulo)"
            r"(?:\s+(?:de|do|da|dos|das|entre))?(?:\s+(?:os\s+)?vetor(?:es)?)?\s*:?\s+(?P<expr>\[.*)"
        ),
        _vector,
    ),
    (
        "vector_without_brackets",
        re.compile(r"(?:produto\s+escalar|produto\s+vetorial|vetor\s+unitario|versor)\b[^\[]*"),
        _vector_without_brackets,
    ),
    (
        "matrix_without_brackets",
        re.compile(r"(?:determinante|matriz)\b[^\[]*"),
        _matrix_without_brackets,
    ),
    (
        "points",
        re.compile(
            r"(?P<calc>distancia|ponto\s+medio|equacao\s+da\s+reta|reta|area\s+do\s+poligono)"
            r"(?:\s+(?:que\s+passa|entre|de|do|da|dos|por|pelos))*"
            r"(?:\s+(?:os\s+)?(?:pontos|vertices|segmento))?(?:\s+(?:de|por))?"
            r"\s*:?\s+(?P<points>\(.*)"
        ),
        _points,
    ),
    (
        "geometry",
        re.compile(
            r"(?P<calc>area\s+da\s+superficie|area\s+total|area|perimetro|comprimento|volume"
            r"|classifique|classificacao|hipotenusa|cateto)"
            r"(?:\s+(?:de|do|da)(?:\s+(?:um|uma|o|a))?|\s+o|\s+a)?"
            r"(?:\s+(?:circunferencia\s+do|da\s+circunferencia\s+do))?"
            r"\s+(?P<figure>circulo|circunferencia|quadrado|retangulo|triangulo\s+retangulo"
            r"|triangulo|trapezio|losango|paralelogramo|cubo|paralelepipedo|esfera|cilindro"
            r"|cone)\b(?P<rest>.*)"
        ),
        _geometry,
    ),
    (
        "geometry_without_figure",
        re.compile(r"(?:area|perimetro|volume)\b(?!\s+(?:sob|abaixo|entre))[^(]*"),
        _geometry_without_figure,
    ),
    (
        "future",
        re.compile(r"(?:probabilidade|vertice|maximo|minimo)\b.*"),
        _future,
    ),
    (
        "derivative",
        re.compile(
            r"(?:(?P<ordw>segunda|terceira|quarta|quinta)\s+)?(?:derivada|derive|derivar|deriva)"
            r"(?:\s+de\s+ordem\s+(?P<ordn>\d+))?"
            rf"{_OF}\s+(?P<expr>.+?){_VAR}"
        ),
        _derivative,
    ),
    (
        "integral",
        re.compile(
            r"(?:integral|integre|integrar|integra|primitiva|antiderivada)"
            r"(?:\s+(?:definida|indefinida))?"
            rf"{_OF}\s+(?P<expr>.+?){_BOUNDS}{_VAR}"
        ),
        _integral,
    ),
    (
        "limit",
        re.compile(
            rf"(?:limite|lim){_OF}\s+(?P<expr>.+?)\s+(?:quando|com|para)\s+(?P<var>[a-z])\s+"
            r"(?:tende\s+(?:a|para)|tendendo\s+(?:a|para)|vai\s+para|indo\s+para|->|→)\s*"
            r"(?P<point>(?:menos\s+|mais\s+)?\S+?)(?P<sign>[+-])?"
            r"(?:\s+pela\s+(?P<side>esquerda|direita))?"
        ),
        _limit,
    ),
    (
        "roots",
        re.compile(
            r"(?:raizes|raiz|zeros|zero)"
            r"(?:\s+(?:de|da\s+funcao|do\s+polinomio|da\s+equacao|do|da))\s+(?P<expr>.+)"
        ),
        _roots,
    ),
    (
        "solve",
        re.compile(
            r"(?:resolva|resolve|resolver|solucione|solucionar)"
            r"(?:\s+(?:a\s+equacao|o\s+sistema|as\s+equacoes))?\s+(?P<expr>.+)"
        ),
        _roots,
    ),
    (
        "factor",
        re.compile(
            r"(?:fatore|fatorar|fatora|fatorize|decomponha|decompor"
            r"|fatoracao\s+(?:de|do|da))"
            r"(?:\s+em\s+fatores\s+primos)?(?:\s+(?:o\s+numero|a\s+expressao|o\s+polinomio))?"
            r"\s+(?P<expr>.+?)(?:\s+em\s+fatores(?:\s+primos)?)?"
        ),
        _plain(IntentName.FACTOR),
    ),
    (
        "expand",
        re.compile(
            r"(?:expanda|expandir|expande|desenvolva|desenvolver|desenvolve)"
            r"(?:\s+a\s+expressao)?\s+(?P<expr>.+)"
        ),
        _plain(IntentName.EXPAND),
    ),
    (
        "simplify",
        re.compile(
            r"(?:simplifique|simplificar|simplifica|reduza|simplificacao\s+(?:de|da|do))"
            r"(?:\s+a\s+expressao)?\s+(?P<expr>.+)"
        ),
        _plain(IntentName.SIMPLIFY),
    ),
    (
        "graph",
        re.compile(
            r"(?:(?:faca|fazer|faz|desenhe|desenhar|trace|tracar|mostre|mostrar|plote|plotar)\s+)?"
            rf"(?:o\s+|um\s+)?(?:grafico|plot){_OF}\s+(?P<expr>.+?){_BOUNDS}"
        ),
        _graph,
    ),
    (
        "graph_verb",
        re.compile(rf"(?:plote|plotar|plota|desenhe|trace)\s+(?P<expr>.+?){_BOUNDS}"),
        _graph,
    ),
    (
        "divide",
        re.compile(r"(?:divida|dividir|divide)\s+(?P<a>.+?)\s+por\s+(?P<b>.+)"),
        _divide,
    ),
    (
        "percent",
        re.compile(r"(?P<p>\d+(?:[.,]\d+)?)\s*%\s*(?:de|do|da|sobre)\s+(?P<m>.+)"),
        _percent,
    ),
]

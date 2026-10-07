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


def _future(found: re.Match[str], request: str, rule: str) -> LanguageMatch:
    raise MathError(
        ErrorCode.UNSUPPORTED_FEATURE,
        "Estatística, matrizes, geometria e pontos como vértice e máximo ainda não são "
        "suportados; eles estão previstos para fases futuras.",
    )


# -- rules, in order ------------------------------------------------------------------------------

_RULES: list[tuple[str, re.Pattern[str], Callable[[re.Match[str], str, str], LanguageMatch]]] = [
    (
        "future",
        re.compile(
            r"(?:media|mediana|moda|desvio|variancia|determinante|matriz|area|perimetro"
            r"|volume|probabilidade|vertice|maximo|minimo)\b.*"
        ),
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

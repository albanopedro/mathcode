"""Compound requests in Portuguese become an execution plan (Phase 12, ADR 0021).

"raízes, vértice e gráfico de x² − 4x + 3" lists three calculations of one
function: each becomes a step with an intent of its own, calculated and
verified like any request. "estude a função f" is a fixed study: roots, the
value at 0, the derivative, maxima and minima, and the graph.

The rules only *split* the request, like ``language.py``: the function still
goes through the safe parser in each step. Nothing here imports SymPy, so the
plan is made in the API process and its steps run in parallel in the pool.
"""

import re
from dataclasses import dataclass, field

from app.core.errors import ErrorCode, MathError
from app.interpreter.language import _LEADS, _VAR, _fold, function_text
from app.models.intents import IntentName
from app.parsing import parse
from app.parsing.ast import Equation, ExpressionList, System, variables

MAX_STEPS = 6

type Options = dict[str, str | int]


@dataclass(frozen=True)
class PlanStep:
    title: str
    intent: IntentName
    input: str
    options: Options = field(default_factory=dict)


@dataclass(frozen=True)
class ExecutionPlan:
    steps: tuple[PlanStep, ...]
    function: str  # the function the steps are about, as typed
    rule: str  # "list" or "study"


# Each calculation that can be listed, by the words that ask for it (folded).
_ITEMS: tuple[tuple[str, str], ...] = (
    ("roots", r"raizes|raiz|zeros|zero"),
    ("vertex", r"vertice"),
    (
        "extrema",
        r"(?:pontos\s+de\s+)?(?:maximos?\s+e\s+minimos?|minimos?\s+e\s+maximos?)"
        r"|(?:pontos\s+)?extremos|pontos\s+criticos|maximos?|minimos?",
    ),
    ("second_derivative", r"segunda\s+derivada|derivada\s+segunda"),
    ("derivative", r"derivada(?:\s+primeira)?"),
    ("integral", r"integral(?:\s+indefinida)?|primitiva"),
    ("graph", r"grafico"),
    ("factor", r"fatoracao|forma\s+fatorada"),
    ("y_intercept", r"(?:intersecao|interseccao)\s+com\s+o\s+eixo\s+y|f\s*\(\s*0\s*\)"),
)
_ITEM = "|".join(f"(?:{pattern})" for _, pattern in _ITEMS)
_ARTICLE = r"(?:(?:o|a|os|as|um|uma)\s+)?"
_SEPARATOR = r"(?:\s*,\s*e\s+|\s*,\s*|\s+e\s+)"
_OF = r"\s+(?:de|da|do|para)(?:\s+(?:funcao|parabola|polinomio|curva))?\s+"
_LIST = re.compile(
    rf"(?P<items>{_ARTICLE}(?:{_ITEM})(?:{_SEPARATOR}{_ARTICLE}(?:{_ITEM}))+){_OF}(?P<expr>.+?){_VAR}"
)
_STUDY = re.compile(
    r"(?:(?:faca|fazer|faz)\s+)?(?:o\s+|um\s+)?"
    r"(?:(?:estudo|analise)(?:\s+completa|\s+completo)?(?:\s+(?:de|da|do))"
    r"|estude|estudar|analise|analisar|analisa)"
    rf"(?:\s+(?:a|o))?(?:\s+(?:funcao|parabola|polinomio|curva))?\s+(?P<expr>.+?){_VAR}"
)
_STUDY_ITEMS = ("roots", "y_intercept", "derivative", "extrema", "graph")


def plan_request(request: str) -> ExecutionPlan | None:
    """The plan of a compound request, or None if this is not one."""
    folded = _fold(request)
    start, end = 0, len(request)
    while end > start and folded[end - 1] in "?.! \t":
        end -= 1
    for _ in range(6):
        lead = _LEADS.match(folded, start, end)
        if lead is None:
            break
        start = lead.end()

    found = _LIST.fullmatch(folded, start, end)
    if found is not None:
        names = [_name_of(item.group(0)) for item in re.finditer(_ITEM, found.group("items"))]
        return _plan(names, request, found, "list")
    found = _STUDY.fullmatch(folded, start, end)
    if found is not None:
        return _plan(list(_STUDY_ITEMS), request, found, "study")
    return None


def _name_of(words: str) -> str:
    for name, pattern in _ITEMS:
        if re.fullmatch(pattern, words):
            return name
    raise AssertionError(f"unknown item: {words}")


def _plan(names: list[str], request: str, found: re.Match[str], rule: str) -> ExecutionPlan | None:
    typed = request[found.start("expr") : found.end("expr")].strip()
    function, _ = function_text(typed)
    function = function.strip()
    variable = _variable(function, found.group("var"))
    if variable is None:
        return None  # not a function the parser reads: the usual paths explain it

    steps: list[PlanStep] = []
    for name in names:
        step = _step(name, function, variable)
        if all((step.intent, step.options) != (s.intent, s.options) for s in steps):
            steps.append(step)
    if len(steps) == 1:
        return None  # "o máximo e o mínimo de f" is one calculation: the usual rules
    if len(steps) > MAX_STEPS:
        raise MathError(
            ErrorCode.LIMIT_EXCEEDED,
            f"Peça no máximo {MAX_STEPS} cálculos de uma vez.",
        )
    return ExecutionPlan(tuple(steps), function, rule)


def _variable(function: str, requested: str | None) -> str | None:
    try:
        tree = parse(function).tree
    except MathError:
        return None
    if isinstance(tree, Equation | System | ExpressionList):
        raise MathError(
            ErrorCode.INVALID_INPUT_FOR_INTENT,
            "Esses cálculos são de uma função: escreva só a expressão, como "
            "x^2 - 4x + 3 (ou f(x) = x^2 - 4x + 3).",
        )
    names = variables(tree)
    if requested is not None:
        return requested
    if not names:
        raise MathError(
            ErrorCode.INVALID_INPUT_FOR_INTENT,
            "Esses cálculos são de uma função de uma variável, como x^2 - 4x + 3; um número "
            "não tem raízes, derivada ou gráfico.",
        )
    if len(names) > 1:
        raise MathError(
            ErrorCode.AMBIGUOUS_INPUT,
            f"A função tem mais de uma variável ({', '.join(sorted(names))}); diga em relação "
            'a qual, como "... em relação a x".',
        )
    return next(iter(names))


def _at_zero(function: str, variable: str) -> str:
    """The function with the variable replaced by 0, from its canonical text."""
    canonical = parse(function).canonical
    return re.sub(rf"(?<![A-Za-z]){variable}(?![A-Za-z])", "(0)", canonical)


def _step(name: str, function: str, variable: str) -> PlanStep:
    by_variable: Options = {"variable": variable}
    match name:
        case "roots":
            return PlanStep("Raízes", IntentName.SOLVE_EQUATION, f"{function} = 0", by_variable)
        case "vertex":
            return PlanStep("Vértice", IntentName.EXTREMA, function, by_variable)
        case "extrema":
            return PlanStep("Máximos e mínimos", IntentName.EXTREMA, function, by_variable)
        case "derivative":
            return PlanStep("Derivada", IntentName.DERIVATIVE, function, by_variable)
        case "second_derivative":
            return PlanStep(
                "Segunda derivada",
                IntentName.DERIVATIVE,
                function,
                by_variable | {"order": 2},
            )
        case "integral":
            return PlanStep("Integral", IntentName.INTEGRAL, function, by_variable)
        case "graph":
            return PlanStep("Gráfico", IntentName.GRAPH, function)
        case "factor":
            return PlanStep("Forma fatorada", IntentName.FACTOR, function)
        case "y_intercept":
            return PlanStep(
                f"Valor em {variable} = 0",
                IntentName.ARITHMETIC,
                _at_zero(function, variable),
            )
    raise AssertionError(f"no step for {name}")

"""Rule-based interpretation: which intent does this input ask for? (AI comes in Phase 8.)"""

from collections.abc import Mapping
from dataclasses import dataclass

from pydantic import BaseModel, ValidationError

from app.core.errors import ErrorCode, MathError
from app.core.limits import MAX_DERIVATIVE_ORDER
from app.math_engine.graphing import is_graph_input
from app.models.intents import (
    INTENT_OPTIONS,
    ArithmeticParams,
    DerivativeParams,
    ExpandParams,
    FactorParams,
    GeometryParams,
    GraphParams,
    IntegralParams,
    IntentName,
    IntentParams,
    LimitParams,
    MatrixParams,
    PolynomialDivisionParams,
    SimplifyParams,
    SolveEquationParams,
    SolveSystemParams,
    StatisticsParams,
    VectorParams,
)
from app.parsing import parse
from app.parsing.ast import (
    Equation,
    Matrix,
    System,
    has_brackets,
    has_points,
    variables,
    walk,
)

type Options = Mapping[str, str | int]

# The text goes into this field of each intent's params; options fill the rest.
_TEXT_FIELD: dict[IntentName, tuple[type[BaseModel], str]] = {
    IntentName.ARITHMETIC: (ArithmeticParams, "expression"),
    IntentName.SIMPLIFY: (SimplifyParams, "expression"),
    IntentName.FACTOR: (FactorParams, "expression"),
    IntentName.EXPAND: (ExpandParams, "expression"),
    IntentName.SOLVE_EQUATION: (SolveEquationParams, "equation"),
    IntentName.SOLVE_SYSTEM: (SolveSystemParams, "system"),
    IntentName.POLYNOMIAL_DIVISION: (PolynomialDivisionParams, "division"),
    IntentName.DERIVATIVE: (DerivativeParams, "expression"),
    IntentName.INTEGRAL: (IntegralParams, "expression"),
    IntentName.LIMIT: (LimitParams, "expression"),
    IntentName.GRAPH: (GraphParams, "expression"),
    IntentName.STATISTICS: (StatisticsParams, "data"),
    IntentName.MATRIX: (MatrixParams, "expression"),
    IntentName.VECTOR: (VectorParams, "expression"),
    IntentName.GEOMETRY: (GeometryParams, "measures"),
}

# User-facing explanation of an invalid option.
_OPTION_PROBLEMS = {
    "variable": "A variável precisa ser uma única letra, como x.",
    "order": f"A ordem da derivada precisa ser um número inteiro de 1 a {MAX_DERIVATIVE_ORDER}.",
    "lower": "O limite inferior precisa ter de 1 a 100 caracteres.",
    "upper": "O limite superior precisa ter de 1 a 100 caracteres.",
    "point": "Informe o ponto do limite, como 0, pi/2 ou inf.",
    "side": "O lado do limite precisa ser 'both', 'left' ou 'right'.",
    "x_min": "O início da faixa de x precisa ter de 1 a 100 caracteres.",
    "x_max": "O fim da faixa de x precisa ter de 1 a 100 caracteres.",
    "measure": (
        "Medida desconhecida. Use count, sum, mean, median, mode, min, max, range, variance, "
        "std, sample_variance ou sample_std."
    ),
    "operation": (
        "Cálculo desconhecido. Para matrizes: evaluate, determinant, inverse, transpose, trace "
        "ou rank; para vetores: evaluate, norm, unit, dot, cross ou angle."
    ),
    "figure": (
        "Figura desconhecida. Use circle, square, rectangle, triangle, trapezoid, rhombus, "
        "parallelogram, cube, box, sphere, cylinder, cone, right_triangle ou points."
    ),
    "calculation": (
        "Cálculo de geometria desconhecido. Use area, perimeter, volume, surface_area, "
        "classify, missing_side, distance, midpoint, line ou polygon_area."
    ),
}


@dataclass(frozen=True)
class IntentRequest:
    intent: IntentName
    params: IntentParams | BaseModel


def interpret(
    text: str, intent: str | None = None, options: Options | None = None
) -> IntentRequest:
    options = dict(options or {})
    if intent is None:
        if options:
            raise MathError(
                ErrorCode.INVALID_INPUT_FOR_INTENT,
                "Parâmetros extras só valem quando a operação é escolhida.",
            )
        name = _detect(text)
    else:
        try:
            name = IntentName(intent)
        except ValueError:
            raise MathError(
                ErrorCode.UNSUPPORTED_INTENT, f"Operação desconhecida: '{intent}'."
            ) from None

    unknown = sorted(set(options) - INTENT_OPTIONS.get(name, frozenset()))
    if unknown:
        raise MathError(
            ErrorCode.INVALID_INPUT_FOR_INTENT,
            f"Parâmetro não aceito por esta operação: {', '.join(unknown)}.",
        )

    model, field = _TEXT_FIELD[name]
    try:
        params = model.model_validate({field: text, **options})
    except ValidationError as exc:
        raise MathError(ErrorCode.INVALID_INPUT_FOR_INTENT, _explain(exc)) from None
    return IntentRequest(name, params)


def _explain(exc: ValidationError) -> str:
    for error in exc.errors():
        location = error["loc"][0] if error["loc"] else None
        if isinstance(location, str) and location in _OPTION_PROBLEMS:
            return _OPTION_PROBLEMS[location]
        if "both_bounds" in str(error.get("msg", "")):
            return "Informe os dois limites de integração, ou nenhum (integral indefinida)."
    return "Parâmetros inválidos para a operação."


def _detect(text: str) -> IntentName:
    """From the shape of the input. Factor, expand, division and calculus must be asked for."""
    tree = parse(text).tree
    if any(isinstance(node, Matrix) for node in walk(tree)):  # "[[1, 2], [3, 4]] * 2"
        return IntentName.MATRIX
    if has_brackets(tree):  # "[1, 2] + [3, 4]"
        return IntentName.VECTOR
    if has_points(tree):  # "(1, 2); (4, 6)": which calculation is up to the user
        raise MathError(
            ErrorCode.INVALID_INPUT_FOR_INTENT,
            "Para pontos, escolha a operação Geometria (Figura: Pontos) e o cálculo, ou "
            "escreva uma frase como 'distância entre (1, 2) e (4, 6)'.",
        )
    if is_graph_input(tree):  # "x^2; 2x + 1" or "y = x^2"
        return IntentName.GRAPH
    if isinstance(tree, System):
        return IntentName.SOLVE_SYSTEM
    if isinstance(tree, Equation):
        return IntentName.SOLVE_EQUATION
    return IntentName.SIMPLIFY if variables(tree) else IntentName.ARITHMETIC

"""Typed input of each intent. Interpretation produces these; execution consumes them."""

from enum import StrEnum
from typing import Annotated, Literal, Self

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StrictInt,
    StrictStr,
    StringConstraints,
    model_validator,
)

from app.core.limits import MAX_DERIVATIVE_ORDER

_VARIABLE = r"^[a-zA-Z]$"


class IntentName(StrEnum):
    ARITHMETIC = "arithmetic"
    SIMPLIFY = "simplify"
    FACTOR = "factor"
    EXPAND = "expand"
    SOLVE_EQUATION = "solve_equation"
    SOLVE_SYSTEM = "solve_system"
    POLYNOMIAL_DIVISION = "polynomial_division"
    DERIVATIVE = "derivative"
    INTEGRAL = "integral"
    LIMIT = "limit"
    GRAPH = "graph"
    STATISTICS = "statistics"
    MATRIX = "matrix"
    VECTOR = "vector"
    GEOMETRY = "geometry"
    PROBABILITY = "probability"
    TRIGONOMETRY = "trigonometry"


class _Params(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class ArithmeticParams(_Params):
    expression: str


class SimplifyParams(_Params):
    expression: str


class FactorParams(_Params):
    expression: str


class ExpandParams(_Params):
    expression: str


class SolveEquationParams(_Params):
    """``lower`` and ``upper``: where periodic solutions are listed (both or none, ADR 0016)."""

    equation: str
    variable: str | None = Field(default=None, pattern=_VARIABLE)
    lower: str | None = Field(default=None, min_length=1, max_length=100)
    upper: str | None = Field(default=None, min_length=1, max_length=100)

    @model_validator(mode="after")
    def _both_ends_or_none(self) -> Self:
        if (self.lower is None) != (self.upper is None):
            raise ValueError("both_ends")
        return self


class SolveSystemParams(_Params):
    system: str


class PolynomialDivisionParams(_Params):
    division: str  # "A / B"


class DerivativeParams(_Params):
    expression: str
    variable: str | None = Field(default=None, pattern=_VARIABLE)
    order: int = Field(default=1, ge=1, le=MAX_DERIVATIVE_ORDER)


class IntegralParams(_Params):
    """Indefinite without bounds; definite with both. Bounds are text: "0", "pi/2", "inf"."""

    expression: str
    variable: str | None = Field(default=None, pattern=_VARIABLE)
    lower: str | None = Field(default=None, min_length=1, max_length=100)
    upper: str | None = Field(default=None, min_length=1, max_length=100)

    @model_validator(mode="after")
    def _both_bounds_or_none(self) -> Self:
        if (self.lower is None) != (self.upper is None):
            raise ValueError("both_bounds")
        return self


class LimitParams(_Params):
    expression: str
    variable: str | None = Field(default=None, pattern=_VARIABLE)
    point: str = Field(min_length=1, max_length=100)
    side: Literal["both", "left", "right"] = "both"


class GraphParams(_Params):
    """One or more functions ("x^2; 2x + 1" or "y = x^2"), plotted over [x_min, x_max]."""

    expression: str
    x_min: str | None = Field(default=None, min_length=1, max_length=100)
    x_max: str | None = Field(default=None, min_length=1, max_length=100)


# Descriptive statistics (Phase 10, ADR 0011). Variance and standard deviation are
# the population ones (÷ n); the sample ones (÷ n − 1) have names of their own.
type Measure = Literal[
    "count",
    "sum",
    "mean",
    "median",
    "mode",
    "min",
    "max",
    "range",
    "variance",
    "std",
    "sample_variance",
    "sample_std",
]


class StatisticsParams(_Params):
    """A list of numbers ("10, 20, 30"); ``measure`` None asks for the whole summary."""

    data: str
    measure: Measure | None = None


# Matrices (Phase 10, ADR 0012): what to do with the matrix the expression evaluates to.
type MatrixOperation = Literal["evaluate", "determinant", "inverse", "transpose", "trace", "rank"]


class MatrixParams(_Params):
    """A matrix expression, such as "[[1, 2], [3, 4]] * 2", and what to compute from it."""

    expression: str
    operation: MatrixOperation = "evaluate"


# Vectors (Phase 10, ADR 0013). dot, cross and angle take two vectors: "u; v".
type VectorOperation = Literal["evaluate", "norm", "unit", "dot", "cross", "angle"]


class VectorParams(_Params):
    """A vector expression, or two separated by ";", and what to compute from them."""

    expression: str
    operation: VectorOperation = "evaluate"


# Geometry (Phase 10, ADR 0014). The catalog (measures and formulas of each figure)
# is in math_engine/geometry.py; here only the names.
type Figure = Literal[
    "circle",
    "square",
    "rectangle",
    "triangle",
    "trapezoid",
    "rhombus",
    "parallelogram",
    "cube",
    "box",
    "sphere",
    "cylinder",
    "cone",
    "right_triangle",
    "points",
]
type GeometryCalculation = Literal[
    "area",
    "perimeter",
    "volume",
    "surface_area",
    "classify",
    "missing_side",
    "distance",
    "midpoint",
    "line",
    "polygon_area",
]


class GeometryParams(_Params):
    """The measures ("r = 5", "b = 4; h = 3") or the points ("(1, 2); (4, 6)") of a figure."""

    measures: str
    figure: Figure
    calculation: GeometryCalculation


# Probability and counting (Phase 10, ADR 0015). The values each calculation takes are
# in math_engine/probability.py; here only the names.
type ProbabilityCalculation = Literal[
    "factorial",
    "arrangement",
    "arrangement_repetition",
    "combination",
    "combination_repetition",
    "anagrams",
    "complement",
    "intersection",
    "intersection_independent",
    "union",
    "union_independent",
    "conditional",
    "binomial_exact",
    "binomial_at_most",
    "binomial_at_least",
    "binomial_summary",
]


class ProbabilityParams(_Params):
    """The values ("n = 10; k = 3", "P(A) = 1/2; P(B) = 1/3") or the word of anagrams."""

    data: str
    calculation: ProbabilityCalculation


# Trigonometry (Phase 10, ADR 0016). Equations such as sin(x) = 1/2 are solve_equation.
type TrigonometryCalculation = Literal["convert", "reduce", "identity", "triangle"]


class TrigonometryParams(_Params):
    """An angle ("150°", "sin(150°)"), an identity ("lhs = rhs") or a triangle ("a = 5; ...")."""

    expression: str
    calculation: TrigonometryCalculation


type IntentParams = (
    ArithmeticParams
    | SimplifyParams
    | FactorParams
    | ExpandParams
    | SolveEquationParams
    | SolveSystemParams
    | PolynomialDivisionParams
    | DerivativeParams
    | IntegralParams
    | LimitParams
    | GraphParams
    | StatisticsParams
    | MatrixParams
    | VectorParams
    | GeometryParams
    | ProbabilityParams
    | TrigonometryParams
)

# Options a request may carry for each intent, besides the input text.
INTENT_OPTIONS: dict[IntentName, frozenset[str]] = {
    IntentName.SOLVE_EQUATION: frozenset({"variable", "lower", "upper"}),
    IntentName.DERIVATIVE: frozenset({"variable", "order"}),
    IntentName.INTEGRAL: frozenset({"variable", "lower", "upper"}),
    IntentName.LIMIT: frozenset({"variable", "point", "side"}),
    IntentName.GRAPH: frozenset({"x_min", "x_max"}),
    IntentName.STATISTICS: frozenset({"measure"}),
    IntentName.MATRIX: frozenset({"operation"}),
    IntentName.VECTOR: frozenset({"operation"}),
    IntentName.GEOMETRY: frozenset({"figure", "calculation"}),
    IntentName.PROBABILITY: frozenset({"calculation"}),
    IntentName.TRIGONOMETRY: frozenset({"calculation"}),
}

# An option value: a short text (variable, bound, point, side) or a small number
# (order). Strict types: in lax mode a long numeric text would become a huge int.
type OptionValue = (
    Annotated[StrictStr, StringConstraints(max_length=100)]
    | Annotated[StrictInt, Field(ge=-1000, le=1000)]
)

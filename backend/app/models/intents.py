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
    equation: str
    variable: str | None = Field(default=None, pattern=_VARIABLE)


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
)

# Options a request may carry for each intent, besides the input text.
INTENT_OPTIONS: dict[IntentName, frozenset[str]] = {
    IntentName.SOLVE_EQUATION: frozenset({"variable"}),
    IntentName.DERIVATIVE: frozenset({"variable", "order"}),
    IntentName.INTEGRAL: frozenset({"variable", "lower", "upper"}),
    IntentName.LIMIT: frozenset({"variable", "point", "side"}),
    IntentName.GRAPH: frozenset({"x_min", "x_max"}),
    IntentName.STATISTICS: frozenset({"measure"}),
}

# An option value: a short text (variable, bound, point, side) or a small number
# (order). Strict types: in lax mode a long numeric text would become a huge int.
type OptionValue = (
    Annotated[StrictStr, StringConstraints(max_length=100)]
    | Annotated[StrictInt, Field(ge=-1000, le=1000)]
)

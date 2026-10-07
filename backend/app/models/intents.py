"""Typed input of each intent. Interpretation produces these; execution consumes them."""

from enum import StrEnum
from typing import Literal, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

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
)

# Options a request may carry for each intent, besides the input text.
INTENT_OPTIONS: dict[IntentName, frozenset[str]] = {
    IntentName.SOLVE_EQUATION: frozenset({"variable"}),
    IntentName.DERIVATIVE: frozenset({"variable", "order"}),
    IntentName.INTEGRAL: frozenset({"variable", "lower", "upper"}),
    IntentName.LIMIT: frozenset({"variable", "point", "side"}),
    IntentName.GRAPH: frozenset({"x_min", "x_max"}),
}

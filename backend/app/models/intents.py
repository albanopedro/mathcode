"""Typed input of each intent. Interpretation produces these; execution consumes them."""

from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field


class IntentName(StrEnum):
    ARITHMETIC = "arithmetic"
    SIMPLIFY = "simplify"
    FACTOR = "factor"
    EXPAND = "expand"
    SOLVE_EQUATION = "solve_equation"
    SOLVE_SYSTEM = "solve_system"
    POLYNOMIAL_DIVISION = "polynomial_division"


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
    variable: str | None = Field(default=None, pattern=r"^[a-zA-Z]$")


class SolveSystemParams(_Params):
    system: str


class PolynomialDivisionParams(_Params):
    division: str  # "A / B"


type IntentParams = (
    ArithmeticParams
    | SimplifyParams
    | FactorParams
    | ExpandParams
    | SolveEquationParams
    | SolveSystemParams
    | PolynomialDivisionParams
)

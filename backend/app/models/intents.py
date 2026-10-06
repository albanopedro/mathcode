"""Typed input of each intent. Interpretation produces these; execution consumes them."""

from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field


class IntentName(StrEnum):
    ARITHMETIC = "arithmetic"
    SIMPLIFY = "simplify"
    SOLVE_EQUATION = "solve_equation"


class _Params(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class ArithmeticParams(_Params):
    expression: str


class SimplifyParams(_Params):
    expression: str


class SolveEquationParams(_Params):
    equation: str
    variable: str | None = Field(default=None, pattern=r"^[a-zA-Z]$")


type IntentParams = ArithmeticParams | SimplifyParams | SolveEquationParams

"""Rule-based interpretation: which intent does this input ask for? (AI comes in Phase 8.)"""

from dataclasses import dataclass

from pydantic import ValidationError

from app.core.errors import ErrorCode, MathError
from app.models.intents import (
    ArithmeticParams,
    ExpandParams,
    FactorParams,
    IntentName,
    IntentParams,
    PolynomialDivisionParams,
    SimplifyParams,
    SolveEquationParams,
    SolveSystemParams,
)
from app.parsing import parse
from app.parsing.ast import Equation, System, variables


@dataclass(frozen=True)
class IntentRequest:
    intent: IntentName
    params: IntentParams


def interpret(text: str, intent: str | None = None) -> IntentRequest:
    if intent is None:
        name = _detect(text)
    else:
        try:
            name = IntentName(intent)
        except ValueError:
            raise MathError(
                ErrorCode.UNSUPPORTED_INTENT, f"Operação desconhecida: '{intent}'."
            ) from None
    try:
        return IntentRequest(name, _params(name, text))
    except ValidationError as exc:
        raise MathError(
            ErrorCode.INVALID_INPUT_FOR_INTENT, "Parâmetros inválidos para a operação."
        ) from exc


def _detect(text: str) -> IntentName:
    """From the shape of the input. Factor, expand and division must be asked for."""
    tree = parse(text).tree
    if isinstance(tree, System):
        return IntentName.SOLVE_SYSTEM
    if isinstance(tree, Equation):
        return IntentName.SOLVE_EQUATION
    return IntentName.SIMPLIFY if variables(tree) else IntentName.ARITHMETIC


def _params(name: IntentName, text: str) -> IntentParams:
    match name:
        case IntentName.ARITHMETIC:
            return ArithmeticParams(expression=text)
        case IntentName.SIMPLIFY:
            return SimplifyParams(expression=text)
        case IntentName.FACTOR:
            return FactorParams(expression=text)
        case IntentName.EXPAND:
            return ExpandParams(expression=text)
        case IntentName.SOLVE_EQUATION:
            return SolveEquationParams(equation=text)
        case IntentName.SOLVE_SYSTEM:
            return SolveSystemParams(system=text)
        case IntentName.POLYNOMIAL_DIVISION:
            return PolynomialDivisionParams(division=text)

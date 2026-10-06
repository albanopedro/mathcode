from dataclasses import dataclass

import sympy as sp

from app.core.errors import ErrorCode, MathError
from app.core.notices import Notice
from app.math_engine.inputs import require_expression
from app.models.intents import ArithmeticParams
from app.parsing import ParseResult, parse
from app.parsing.ast import Node, variables
from app.parsing.build import ExpressionBuilder, ensure_within_limits

_UNDEFINED = (sp.zoo, sp.nan, sp.oo, -sp.oo)


@dataclass(frozen=True)
class ArithmeticOutcome:
    parsed: ParseResult
    tree: Node
    value: sp.Expr
    notices: tuple[Notice, ...]


def evaluate(params: ArithmeticParams) -> ArithmeticOutcome:
    parsed = parse(params.expression)
    tree = require_expression(parsed)
    if names := variables(tree):
        raise MathError(
            ErrorCode.INVALID_INPUT_FOR_INTENT,
            f"A expressão tem variáveis ({', '.join(sorted(names))}), "
            "então não é um cálculo numérico.",
        )

    builder = ExpressionBuilder()
    value = builder.build(tree)
    if not value.is_Rational:
        value = sp.simplify(value)
    _ensure_real(value)
    ensure_within_limits(value)
    return ArithmeticOutcome(parsed, tree, value, parsed.notices + tuple(builder.notices))


def _ensure_real(value: sp.Expr) -> None:
    if value.has(*_UNDEFINED):
        raise MathError(ErrorCode.DOMAIN_ERROR, "O resultado não é definido.")
    if value.is_extended_real is False or value.has(sp.I):
        raise MathError(ErrorCode.DOMAIN_ERROR, "O resultado não é um número real (o domínio é ℝ).")

from app.core.errors import ErrorCode, MathError
from app.parsing import ParseResult
from app.parsing.ast import Equation, Node


def require_expression(parsed: ParseResult) -> Node:
    if isinstance(parsed.tree, Equation):
        raise MathError(
            ErrorCode.INVALID_INPUT_FOR_INTENT,
            "Isto é uma equação. Para resolvê-la, use a operação de resolver equações.",
            parsed.tree.position,
        )
    return parsed.tree


def require_equation(parsed: ParseResult) -> Equation:
    if not isinstance(parsed.tree, Equation):
        raise MathError(
            ErrorCode.INVALID_INPUT_FOR_INTENT,
            "Isto não é uma equação: falta o sinal de '='.",
        )
    return parsed.tree

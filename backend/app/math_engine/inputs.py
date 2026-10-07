from app.core.errors import ErrorCode, MathError
from app.parsing import ParseResult
from app.parsing.ast import Equation, ExpressionList, Node, System


def _reject_lists(parsed: ParseResult) -> None:
    if isinstance(parsed.tree, System):
        raise MathError(
            ErrorCode.INVALID_INPUT_FOR_INTENT,
            "Isto é um sistema de equações. Para resolvê-lo, use a operação de resolver sistemas.",
            parsed.tree.position,
        )
    if isinstance(parsed.tree, ExpressionList):
        raise MathError(
            ErrorCode.INVALID_INPUT_FOR_INTENT,
            "Isto é uma lista de expressões. Para desenhá-las juntas, use a operação Gráfico.",
            parsed.tree.position,
        )


def require_expression(parsed: ParseResult) -> Node:
    _reject_lists(parsed)
    if isinstance(parsed.tree, Equation):
        raise MathError(
            ErrorCode.INVALID_INPUT_FOR_INTENT,
            "Isto é uma equação. Para resolvê-la, use a operação de resolver equações.",
            parsed.tree.position,
        )
    return parsed.tree


def require_equation(parsed: ParseResult) -> Equation:
    _reject_lists(parsed)
    if not isinstance(parsed.tree, Equation):
        raise MathError(
            ErrorCode.INVALID_INPUT_FOR_INTENT,
            "Isto não é uma equação: falta o sinal de '='.",
        )
    return parsed.tree


def require_system(parsed: ParseResult) -> System:
    """A system, or a single equation treated as a system of one."""
    if isinstance(parsed.tree, System):
        return parsed.tree
    if isinstance(parsed.tree, Equation):
        return System((parsed.tree,), parsed.tree.position)
    raise MathError(
        ErrorCode.INVALID_INPUT_FOR_INTENT,
        "Isto não é um sistema: escreva as equações separadas por ';', como x + y = 3; x - y = 1.",
    )

"""AST -> canonical text, showing the user how the input was understood."""

from app.parsing.ast import (
    Binary,
    Call,
    Constant,
    Degrees,
    Equation,
    ExpressionList,
    Negate,
    Node,
    Number,
    System,
    Tree,
    Variable,
)

_PRECEDENCE = {"+": 1, "-": 1, "*": 2, "/": 2, "^": 4}
_NEGATE = 3
_ATOM = 5


def to_text(tree: Tree) -> str:
    if isinstance(tree, System):
        return "; ".join(to_text(equation) for equation in tree.equations)
    if isinstance(tree, ExpressionList):
        return "; ".join(_text(expression) for expression in tree.expressions)
    if isinstance(tree, Equation):
        return f"{_text(tree.left)} = {_text(tree.right)}"
    return _text(tree)


def _precedence(node: Node) -> int:
    match node:
        case Binary(op=op):
            return _PRECEDENCE[op]
        case Negate():
            return _NEGATE
        case _:
            return _ATOM


def _wrap(node: Node, parens: bool) -> str:
    text = _text(node)
    return f"({text})" if parens else text


def _text(node: Node) -> str:
    match node:
        case Number(value=value):
            return value
        case Variable(name=name) | Constant(name=name):
            return name
        case Negate(operand=operand):
            return "-" + _wrap(operand, _precedence(operand) <= _NEGATE)
        case Degrees(operand=operand):
            return _wrap(operand, _precedence(operand) < _ATOM) + "°"
        case Call(name=name, args=args):
            return f"{name}({', '.join(_text(arg) for arg in args)})"
        case Binary():
            return _binary(node)


def _binary(node: Binary) -> str:
    precedence = _PRECEDENCE[node.op]
    left, right = _precedence(node.left), _precedence(node.right)
    if node.op == "^":
        left_parens = left <= precedence
        right_parens = right < precedence
    else:
        # (1/2)*x: make the reading of "1/2x" explicit.
        left_parens = left < precedence or (
            node.op == "*" and isinstance(node.left, Binary) and node.left.op == "/"
        )
        right_parens = right <= precedence if node.op in "-/" else right < precedence
    space = " " if precedence == 1 else ""
    return (
        f"{_wrap(node.left, left_parens)}{space}{node.op}{space}{_wrap(node.right, right_parens)}"
    )

"""The parser's own syntax tree: plain immutable data, never executed."""

from collections.abc import Iterator
from dataclasses import dataclass
from typing import Literal


@dataclass(frozen=True)
class Number:
    value: str  # decimal literal with "." as separator, e.g. "3.5"
    position: int


@dataclass(frozen=True)
class Variable:
    name: str
    position: int


@dataclass(frozen=True)
class Constant:
    name: Literal["pi", "e"]
    position: int


@dataclass(frozen=True)
class Negate:
    operand: Node
    position: int


@dataclass(frozen=True)
class Binary:
    op: Literal["+", "-", "*", "/", "^"]
    left: Node
    right: Node
    position: int
    implicit: bool = False  # multiplication written without "*", as in "2x"
    grouped: bool = False  # the whole operation was written inside parentheses


@dataclass(frozen=True)
class Call:
    name: str  # canonical name from vocabulary.FUNCTIONS
    args: tuple[Node, ...]
    position: int


@dataclass(frozen=True)
class Degrees:
    operand: Node
    position: int


type Node = Number | Variable | Constant | Negate | Binary | Call | Degrees


@dataclass(frozen=True)
class Equation:
    left: Node
    right: Node
    position: int  # of the "="


@dataclass(frozen=True)
class System:
    """Equations separated by ";" (or ", " with a space), solved together."""

    equations: tuple[Equation, ...]
    position: int  # of the first separator


@dataclass(frozen=True)
class ExpressionList:
    """Expressions separated by ";", such as several functions to plot together."""

    expressions: tuple[Node, ...]
    position: int  # of the first separator


type Tree = Node | Equation | System | ExpressionList


def children(node: Tree) -> tuple[Tree, ...]:
    match node:
        case System(equations=equations):
            return equations
        case ExpressionList(expressions=expressions):
            return expressions
        case Negate(operand=operand) | Degrees(operand=operand):
            return (operand,)
        case Binary(left=left, right=right) | Equation(left=left, right=right):
            return (left, right)
        case Call(args=args):
            return args
        case _:
            return ()


def walk(node: Tree) -> Iterator[Tree]:
    yield node
    for child in children(node):
        yield from walk(child)


def variables(node: Tree) -> set[str]:
    return {n.name for n in walk(node) if isinstance(n, Variable)}

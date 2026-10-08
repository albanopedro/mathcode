"""Vectors with exact numbers (Phase 10, ADR 0013).

The expression is evaluated by the same evaluator as matrices, so sums,
multiples and A·v follow one set of rules. Then the operation is applied:

- one vector: evaluate (the vector itself), norm ‖u‖, unit vector u/‖u‖;
- two vectors, separated by ";": dot product u·v, cross product u×v (3D) and
  the angle between them, exact in radians (degrees come in the presentation).
"""

from dataclasses import dataclass

import sympy as sp

from app.core.errors import ErrorCode, MathError
from app.core.notices import Notice
from app.math_engine.matrices import LinearEvaluator, VectorValue, check_size
from app.models.intents import VectorOperation, VectorParams
from app.parsing import ParseResult, parse
from app.parsing.ast import Equation, ExpressionList, Node, System

TWO_VECTORS: frozenset[VectorOperation] = frozenset({"dot", "cross", "angle"})
_NAMES = {
    "evaluate": "Calcular expressão",
    "norm": "A norma",
    "unit": "O vetor unitário",
    "dot": "O produto escalar",
    "cross": "O produto vetorial",
    "angle": "O ângulo",
}


@dataclass(frozen=True)
class VectorOutcome:
    parsed: ParseResult
    items: tuple[Node, ...]  # the expression of each vector, as typed
    operation: VectorOperation
    vectors: tuple[VectorValue, ...]  # u, or u and v
    result: sp.Expr | VectorValue  # a number (norm, dot, angle in radians) or a vector
    notices: tuple[Notice, ...]


def vectors(params: VectorParams) -> VectorOutcome:
    parsed = parse(params.expression)
    items = _items(parsed, params.operation)
    evaluator = LinearEvaluator()
    operands = tuple(_vector(evaluator, item) for item in items)
    result = _apply(params.operation, operands)
    check_size(result)
    notices = (*parsed.notices, *evaluator.builder.notices)
    return VectorOutcome(parsed, items, params.operation, operands, result, notices)


def _items(parsed: ParseResult, operation: VectorOperation) -> tuple[Node, ...]:
    tree = parsed.tree
    if isinstance(tree, Equation | System):
        raise MathError(
            ErrorCode.INVALID_INPUT_FOR_INTENT,
            "Escreva vetores entre colchetes, sem '=': [1, 2, 3] ou [1, 2]; [3, 4].",
        )
    items = tree.expressions if isinstance(tree, ExpressionList) else (tree,)
    wanted = 2 if operation in TWO_VECTORS else 1
    if len(items) != wanted:
        if wanted == 2:
            message = (
                f"{_NAMES[operation]} usa dois vetores, separados por ';', como em "
                "[1, 2, 3]; [4, 5, 6]."
            )
        else:
            message = f"{_NAMES[operation]} usa um vetor só, como em [3, 4]."
        if operation == "evaluate":
            message = (
                "Para dois vetores, escolha um cálculo (Produto escalar, Produto vetorial ou "
                "Ângulo). Para combiná-los, use + ou −: [1, 2] + [3, 4]."
            )
        raise MathError(ErrorCode.INVALID_INPUT_FOR_INTENT, message)
    return items


def _vector(evaluator: LinearEvaluator, item: Node) -> VectorValue:
    value = evaluator.value(item)
    if isinstance(value, VectorValue):
        return value
    if isinstance(value, sp.MatrixBase):
        raise MathError(
            ErrorCode.INVALID_INPUT_FOR_INTENT,
            "O resultado é uma matriz, não um vetor. Para matrizes, use a operação Matrizes.",
            item.position,
        )
    raise MathError(
        ErrorCode.INVALID_INPUT_FOR_INTENT,
        "Escreva o vetor entre colchetes: [1, 2, 3].",
        item.position,
    )


def _simplified(value: sp.Expr) -> sp.Expr:
    return value if value.is_Rational else sp.simplify(value)


def norm(vector: VectorValue) -> sp.Expr:
    return _simplified(sp.sqrt(sum(entry**2 for entry in vector.entries)))


def dot(u: VectorValue, v: VectorValue) -> sp.Expr:
    return _simplified(sum(a * b for a, b in zip(u.entries, v.entries, strict=True)))


def _apply(operation: VectorOperation, operands: tuple[VectorValue, ...]) -> sp.Expr | VectorValue:
    u = operands[0]
    if operation == "evaluate":
        return u
    if operation in ("norm", "unit"):
        length = norm(u)
        if operation == "norm":
            return length
        if length.is_zero:
            raise MathError(
                ErrorCode.DOMAIN_ERROR, "O vetor nulo não tem vetor unitário (a norma é 0)."
            )
        unit = sp.ImmutableMatrix([_simplified(entry / length) for entry in u.entries])
        return VectorValue(unit)

    v = operands[1]
    if u.size != v.size:
        raise MathError(
            ErrorCode.INVALID_INPUT_FOR_INTENT,
            f"Os vetores precisam ter o mesmo número de componentes: {u.size} e {v.size}.",
        )
    if operation == "dot":
        return dot(u, v)
    if operation == "cross":
        if u.size != 3:
            raise MathError(
                ErrorCode.INVALID_INPUT_FOR_INTENT,
                f"O produto vetorial só existe para vetores de 3 componentes; estes têm {u.size}.",
            )
        cross = u.column.cross(v.column)
        return VectorValue(sp.ImmutableMatrix([_simplified(entry) for entry in cross]))
    lengths = norm(u) * norm(v)
    if lengths.is_zero:
        raise MathError(
            ErrorCode.DOMAIN_ERROR, "O ângulo não é definido quando um dos vetores é nulo."
        )
    return _simplified(sp.acos(_simplified(dot(u, v) / lengths)))

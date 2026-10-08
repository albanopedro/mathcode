"""Matrices with exact numbers (Phase 10, ADR 0012).

The expression is evaluated from the parser's tree: matrix literals become
SymPy matrices of exact numbers; +, −, ×, ÷ by a number and integer powers
follow the rules of matrix algebra, and every incompatible size is explained.
Then the requested operation is applied to the resulting matrix A:
evaluate (A itself), determinant, inverse, transpose, trace or rank.
"""

from dataclasses import dataclass

import sympy as sp

from app.core.errors import ErrorCode, MathError
from app.core.notices import Notice
from app.models.intents import MatrixOperation, MatrixParams
from app.parsing import ParseResult, parse
from app.parsing.ast import (
    Binary,
    Equation,
    ExpressionList,
    Matrix,
    Negate,
    Node,
    System,
    Vector,
    has_brackets,
    variables,
)
from app.parsing.build import ExpressionBuilder, ensure_within_limits

MAX_MATRIX_POWER = 20


type Value = sp.MatrixBase | VectorValue | sp.Expr


@dataclass(frozen=True)
class MatrixOutcome:
    parsed: ParseResult
    tree: Node
    operation: MatrixOperation
    operand: sp.ImmutableMatrix | VectorValue  # A: the value (a vector only from A·v)
    result: Value  # a matrix (evaluate, inverse, transpose), A·v's vector or a number
    notices: tuple[Notice, ...]


def matrices(params: MatrixParams) -> MatrixOutcome:
    parsed = parse(params.expression)
    tree = parsed.tree
    if isinstance(tree, Equation | System | ExpressionList):
        raise MathError(
            ErrorCode.INVALID_INPUT_FOR_INTENT,
            "Escreva uma expressão com matrizes, sem '=' e sem ';' fora dos colchetes, como "
            "[[1, 2], [3, 4]] * 2.",
        )
    evaluator = LinearEvaluator()
    value = evaluator.value(tree)
    if isinstance(value, VectorValue) and params.operation == "evaluate":
        operand: sp.ImmutableMatrix | VectorValue = value  # A·v
        result: Value = value
    elif isinstance(value, VectorValue):
        raise MathError(
            ErrorCode.INVALID_INPUT_FOR_INTENT,
            "O resultado da expressão é um vetor; esse cálculo é de matrizes. Para vetores, "
            "use a operação Vetores.",
        )
    elif not isinstance(value, sp.MatrixBase):
        raise MathError(
            ErrorCode.INVALID_INPUT_FOR_INTENT,
            "A expressão não tem matriz. Escreva uma entre colchetes, uma linha por "
            "colchete: [[1, 2], [3, 4]].",
        )
    else:
        operand = sp.ImmutableMatrix(value)
        result = _apply(params.operation, operand)
    check_size(result)
    notices = (*parsed.notices, *evaluator.builder.notices)
    return MatrixOutcome(parsed, tree, params.operation, operand, result, notices)


def is_exact_rational(matrix: sp.MatrixBase) -> bool:
    return all(entry.is_Rational for entry in matrix)


def _simplified(value: sp.Expr) -> sp.Expr:
    return value if value.is_Rational else sp.simplify(value)


def _apply(operation: MatrixOperation, a: sp.ImmutableMatrix) -> Value:
    if operation == "evaluate":
        return a
    if operation == "transpose":
        return a.T
    if operation == "rank":
        return sp.Integer(a.rank(simplify=True))
    if not a.is_square:
        what = {"determinant": "O determinante", "inverse": "A inversa", "trace": "O traço"}
        raise MathError(
            ErrorCode.INVALID_INPUT_FOR_INTENT,
            f"{what[operation]} só existe para matrizes quadradas; esta é {_shape(a)}.",
        )
    if operation == "trace":
        return _simplified(a.trace())
    determinant = _simplified(a.det())
    if operation == "determinant":
        return determinant
    if determinant.is_zero:
        raise MathError(
            ErrorCode.DOMAIN_ERROR,
            "A matriz é singular (determinante 0), então não tem inversa.",
        )
    inverse = a.inv()
    return inverse if is_exact_rational(inverse) else inverse.applyfunc(sp.simplify)


def check_size(value: Value) -> None:
    if isinstance(value, VectorValue):
        entries = value.entries
    elif isinstance(value, sp.MatrixBase):
        entries = list(value)
    else:
        entries = [value]
    for entry in entries:
        ensure_within_limits(entry)


@dataclass(frozen=True)
class VectorValue:
    """A vector: kept as a column, so that A·v is the usual matrix product (ADR 0013)."""

    column: sp.ImmutableMatrix  # n×1

    @property
    def size(self) -> int:
        return self.column.rows

    @property
    def entries(self) -> list[sp.Expr]:
        return list(self.column)


class LinearEvaluator:
    """Evaluates an expression whose values are numbers, vectors and matrices."""

    def __init__(self) -> None:
        self.builder = ExpressionBuilder()

    def value(self, node: Node) -> Value:
        match node:
            case Matrix(rows=rows):
                return sp.Matrix([[self._number(entry) for entry in row] for row in rows])
            case Vector(entries=entries):
                column = sp.ImmutableMatrix([self._number(entry) for entry in entries])
                return VectorValue(column)
            case Negate(operand=operand):
                inner = self.value(operand)
                return VectorValue(-inner.column) if isinstance(inner, VectorValue) else -inner
            case Binary(op=op, left=left, right=right):
                return self._binary(node, op, self.value(left), self.value(right))
        if has_brackets(node):
            raise MathError(
                ErrorCode.INVALID_INPUT_FOR_INTENT,
                "Funções e graus não se aplicam a matrizes e vetores; use só +, −, *, / por "
                "número e ^.",
                node.position,
            )
        return self._number(node)

    def _number(self, node: Node) -> sp.Expr:
        if variables(node):
            raise MathError(
                ErrorCode.INVALID_INPUT_FOR_INTENT,
                "Os elementos de matrizes e vetores precisam ser números, sem variáveis.",
                node.position,
            )
        value = self.builder.build(node)
        if value.is_extended_real is False or value.has(sp.I):
            raise MathError(
                ErrorCode.DOMAIN_ERROR, "O elemento não é um número real.", node.position
            )
        return value

    def _binary(self, node: Binary, op: str, a: Value, b: Value) -> Value:
        kinds = (_kind(a), _kind(b))
        if kinds == ("number", "number"):
            return self.builder.build(node)  # a number: the usual rules (0^0, ÷ 0...)
        if op in "+-":
            return self._sum(node, op, a, b, kinds)
        if op == "*":
            return self._product(node, a, b, kinds)
        if op == "/":
            if kinds[1] != "number":
                raise MathError(
                    ErrorCode.INVALID_INPUT_FOR_INTENT,
                    "Não existe divisão por matriz nem por vetor. Para B·A⁻¹, use a operação "
                    "Inversa e depois multiplique.",
                    node.position,
                )
            if b.is_zero:
                raise MathError(ErrorCode.DIVISION_BY_ZERO, "Divisão por zero.", node.position)
            return VectorValue(a.column / b) if isinstance(a, VectorValue) else a / b
        return self._power(node, a, b)

    def _sum(self, node: Binary, op: str, a: Value, b: Value, kinds: tuple[str, str]) -> Value:
        if kinds not in (("matrix", "matrix"), ("vector", "vector")):
            raise MathError(
                ErrorCode.INVALID_INPUT_FOR_INTENT,
                "Só se soma (ou subtrai) matriz com matriz e vetor com vetor, do mesmo tamanho. "
                "Para somar um número a cada elemento, escreva uma matriz ou um vetor com ele.",
                node.position,
            )
        if isinstance(a, VectorValue) and isinstance(b, VectorValue):
            if a.size != b.size:
                raise MathError(
                    ErrorCode.INVALID_INPUT_FOR_INTENT,
                    f"Para somar ou subtrair, os vetores precisam ter o mesmo número de "
                    f"componentes: {a.size} e {b.size}.",
                    node.position,
                )
            return VectorValue(a.column + b.column if op == "+" else a.column - b.column)
        if a.shape != b.shape:
            raise MathError(
                ErrorCode.INVALID_INPUT_FOR_INTENT,
                f"Para somar ou subtrair, as matrizes precisam ter o mesmo tamanho: "
                f"{_shape(a)} e {_shape(b)}.",
                node.position,
            )
        return a + b if op == "+" else a - b

    def _product(self, node: Binary, a: Value, b: Value, kinds: tuple[str, str]) -> Value:
        match kinds:
            case ("vector", "vector"):
                raise MathError(
                    ErrorCode.INVALID_INPUT_FOR_INTENT,
                    "Entre dois vetores, * é ambíguo: use o cálculo Produto escalar ou Produto "
                    "vetorial, com os vetores separados por ';'.",
                    node.position,
                )
            case ("vector", "matrix"):
                raise MathError(
                    ErrorCode.INVALID_INPUT_FOR_INTENT,
                    "Para multiplicar matriz por vetor, escreva a matriz antes: A*v (o vetor é "
                    "uma coluna).",
                    node.position,
                )
            case ("matrix", "vector"):
                if a.cols != b.size:
                    raise MathError(
                        ErrorCode.INVALID_INPUT_FOR_INTENT,
                        f"Para multiplicar A ({_shape(a)}) por um vetor, ele precisa ter "
                        f"{a.cols} componentes (o número de colunas de A); este tem {b.size}.",
                        node.position,
                    )
                return VectorValue(sp.ImmutableMatrix(a * b.column))
            case ("matrix", "matrix"):
                if a.cols != b.rows:
                    raise MathError(
                        ErrorCode.INVALID_INPUT_FOR_INTENT,
                        f"Para multiplicar A ({_shape(a)}) por B ({_shape(b)}), o número de "
                        f"colunas de A ({a.cols}) precisa ser igual ao de linhas de B ({b.rows}).",
                        node.position,
                    )
                return a * b
        if isinstance(a, VectorValue):
            return VectorValue(a.column * b)
        if isinstance(b, VectorValue):
            return VectorValue(a * b.column)
        return a * b

    def _power(self, node: Binary, base: Value, exponent: Value) -> Value:
        if not isinstance(base, sp.MatrixBase) or _kind(exponent) != "number":
            raise MathError(
                ErrorCode.INVALID_INPUT_FOR_INTENT,
                "Na potência, a base é uma matriz e o expoente é um número inteiro, como A^2. "
                "Vetores não têm potência.",
                node.position,
            )
        if not base.is_square:
            raise MathError(
                ErrorCode.INVALID_INPUT_FOR_INTENT,
                f"Só matrizes quadradas têm potência; esta é {_shape(base)}.",
                node.position,
            )
        if not exponent.is_Integer or abs(exponent) > MAX_MATRIX_POWER:
            raise MathError(
                ErrorCode.INVALID_INPUT_FOR_INTENT,
                f"O expoente de uma matriz precisa ser um inteiro de −{MAX_MATRIX_POWER} a "
                f"{MAX_MATRIX_POWER}.",
                node.position,
            )
        if exponent < 0 and _simplified(base.det()).is_zero:
            raise MathError(
                ErrorCode.DOMAIN_ERROR,
                "Potência negativa de uma matriz singular (determinante 0) não existe.",
                node.position,
            )
        return base ** int(exponent)


def _kind(value: Value) -> str:
    if isinstance(value, VectorValue):
        return "vector"
    return "matrix" if isinstance(value, sp.MatrixBase) else "number"


def _shape(matrix: sp.MatrixBase) -> str:
    return f"{matrix.rows}×{matrix.cols}"

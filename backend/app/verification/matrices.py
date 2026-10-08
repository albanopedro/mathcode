"""Verification of matrix results (ADR 0012).

The expression is evaluated again from the parser's tree, without SymPy:

- exact mode: when every number is rational, with ``Fraction`` and matrix
  algebra written here (sum, product, integer power, Gauss–Jordan inverse);
- numeric mode: otherwise (√2, π...), with the independent mpmath evaluator at
  60 digits and mpmath matrices.

Then each operation is checked by another route: the determinant by Gaussian
elimination (SymPy uses Bareiss), the inverse by A·A⁻¹ = I and A⁻¹·A = I, the
transpose index by index, the trace from the diagonal, the rank by
elimination. Exact mode proves (``verified_symbolic``); numeric mode is
evidence within 30 significant digits (``verified_numeric``).
"""

from fractions import Fraction

import mpmath
import sympy as sp
from mpmath import mp, mpf

from app.math_engine.matrices import MatrixOutcome, VectorValue
from app.models.result import (
    CheckKind,
    ReasonCode,
    VerificationCheck,
    VerificationReport,
    VerificationStatus,
)
from app.parsing.ast import Binary, Matrix, Negate, Node, Vector
from app.verification.exact import exact_value
from app.verification.numeric import BASE_PRECISION, OutsideDomain, TooLarge, evaluate, to_mpf
from app.verification.reports import failure, passed, report, unverified

type Grid = list[list[Fraction]]
type Value = Grid | Fraction

TOLERANCE = mpf("1e-30")


class OutOfExactScope(Exception):
    pass


# -- exact matrix algebra (no SymPy) ----------------------------------------------------------


def _identity(n: int) -> Grid:
    return [[Fraction(int(i == j)) for j in range(n)] for i in range(n)]


def _product(a: Grid, b: Grid) -> Grid:
    return [
        [sum((a[i][k] * b[k][j] for k in range(len(b))), Fraction(0)) for j in range(len(b[0]))]
        for i in range(len(a))
    ]


def _eliminate(grid: Grid) -> tuple[Grid, int, int]:
    """Row echelon form by Gaussian elimination: (echelon, rank, sign of the swaps)."""
    rows = [row[:] for row in grid]
    rank, sign = 0, 1
    for col in range(len(rows[0]) if rows else 0):
        pivot = next((r for r in range(rank, len(rows)) if rows[r][col] != 0), None)
        if pivot is None:
            continue
        if pivot != rank:
            rows[rank], rows[pivot] = rows[pivot], rows[rank]
            sign = -sign
        for r in range(rank + 1, len(rows)):
            factor = rows[r][col] / rows[rank][col]
            if factor:
                rows[r] = [x - factor * y for x, y in zip(rows[r], rows[rank], strict=True)]
        rank += 1
    return rows, rank, sign


def _determinant(grid: Grid) -> Fraction:
    echelon, rank, sign = _eliminate(grid)
    if rank < len(grid):
        return Fraction(0)
    result = Fraction(sign)
    for i in range(len(grid)):
        result *= echelon[i][i]
    return result


def _inverse(grid: Grid) -> Grid:
    """Gauss–Jordan on [A | I]."""
    n = len(grid)
    augmented = [row[:] + identity for row, identity in zip(grid, _identity(n), strict=True)]
    for col in range(n):
        pivot = next((r for r in range(col, n) if augmented[r][col] != 0), None)
        if pivot is None:
            raise OutOfExactScope  # singular: the engine refuses it before this
        augmented[col], augmented[pivot] = augmented[pivot], augmented[col]
        lead = augmented[col][col]
        augmented[col] = [x / lead for x in augmented[col]]
        for r in range(n):
            if r != col and augmented[r][col] != 0:
                factor = augmented[r][col]
                augmented[r] = [
                    x - factor * y for x, y in zip(augmented[r], augmented[col], strict=True)
                ]
    return [row[n:] for row in augmented]


def _power(grid: Grid, exponent: int) -> Grid:
    base = _inverse(grid) if exponent < 0 else grid
    result = _identity(len(grid))
    for _ in range(abs(exponent)):
        result = _product(result, base)
    return result


def exact_linear(node: Node) -> Value:
    """The value of a matrix or vector expression with fractions (a vector is a column)."""
    match node:
        case Vector(entries=entries):
            values = [exact_value(entry) for entry in entries]
            if any(value is None for value in values):
                raise OutOfExactScope
            return [[value] for value in values if value is not None]
        case Matrix(rows=rows):
            entries = [[exact_value(entry) for entry in row] for row in rows]
            if any(entry is None for row in entries for entry in row):
                raise OutOfExactScope
            return [[entry for entry in row if entry is not None] for row in entries]
        case Negate(operand=operand):
            value = exact_linear(operand)
            return [[-x for x in row] for row in value] if isinstance(value, list) else -value
        case Binary(op=op, left=left, right=right):
            a, b = exact_linear(left), exact_linear(right)
            if isinstance(a, list) and isinstance(b, list):
                if op == "*":
                    return _product(a, b)
                if op not in "+-":
                    raise OutOfExactScope  # refused by the engine before this
                sign = 1 if op == "+" else -1
                return [
                    [x + sign * y for x, y in zip(ra, rb, strict=True)]
                    for ra, rb in zip(a, b, strict=True)
                ]
            if isinstance(a, list) and isinstance(b, Fraction):
                if op == "^":
                    return _power(a, int(b))
                if op not in "*/":
                    raise OutOfExactScope
                return [[x * b if op == "*" else x / b for x in row] for row in a]
            if isinstance(b, list) and isinstance(a, Fraction):
                if op != "*":
                    raise OutOfExactScope
                return [[a * x for x in row] for row in b]
    value = exact_value(node)
    if value is None:
        raise OutOfExactScope
    return value


def as_grid(matrix: sp.MatrixBase) -> Grid | None:
    """A SymPy matrix of rationals as fractions; None if an entry is not rational."""
    if not all(entry.is_Rational for entry in matrix):
        return None
    return [
        [Fraction(int(matrix[i, j].p), int(matrix[i, j].q)) for j in range(matrix.cols)]
        for i in range(matrix.rows)
    ]


# -- numeric mode (mpmath) ------------------------------------------------------------------


def numeric_linear(node: Node) -> mpmath.matrix | mpf:
    """The same with the independent mpmath evaluator (call it inside ``mp.workdps``)."""
    match node:
        case Vector(entries=entries):
            return mpmath.matrix([evaluate(entry).value for entry in entries])
        case Matrix(rows=rows):
            return mpmath.matrix([[evaluate(entry).value for entry in row] for row in rows])
        case Negate(operand=operand):
            return -numeric_linear(operand)
        case Binary(op=op, left=left, right=right):
            a, b = numeric_linear(left), numeric_linear(right)
            if op == "+":
                return a + b
            if op == "-":
                return a - b
            if op == "*":
                return a * b
            if op == "/":
                return a / b
            return a ** int(b)
    return evaluate(node).value


def close(expected: mpf, actual: mpf, scale: mpf) -> bool:
    return abs(expected - actual) <= TOLERANCE * max(1, scale)


def matrix_close(expected: mpmath.matrix, actual: sp.MatrixBase) -> bool:
    if (expected.rows, expected.cols) != actual.shape:
        return False
    scale = max(
        (abs(expected[i, j]) for i in range(expected.rows) for j in range(expected.cols)),
        default=mpf(0),
    )
    for i in range(expected.rows):
        for j in range(expected.cols):
            value = to_mpf(actual[i, j])
            if value is None or not close(expected[i, j], value, scale):
                return False
    return True


# -- the verifier ---------------------------------------------------------------------------------


def verify_matrices(outcome: MatrixOutcome) -> VerificationReport:
    try:
        operand = exact_linear(outcome.tree)
    except OutOfExactScope, ZeroDivisionError:
        return _verify_numerically(outcome)
    if not isinstance(operand, list):
        raise AssertionError("the engine only accepts expressions with a matrix")
    return _verify_exactly(outcome, operand)


def _as_matrix(operand: sp.MatrixBase | VectorValue) -> sp.MatrixBase:
    return operand.column if isinstance(operand, VectorValue) else operand


def _verify_exactly(outcome: MatrixOutcome, a: Grid) -> VerificationReport:
    if as_grid(_as_matrix(outcome.operand)) != a:
        return failure(
            CheckKind.COMPARISON,
            "Recalculando a expressão com frações exatas (sem o SymPy), a matriz não é a mesma.",
        )
    checks = [
        passed(
            CheckKind.COMPARISON,
            "A matriz da expressão, recalculada com frações exatas e álgebra de matrizes "
            "própria (sem o SymPy), é a mesma.",
        )
    ]
    result = outcome.result
    match outcome.operation:
        case "evaluate":
            pass
        case "determinant":
            own = _determinant(a)
            if sp.Rational(own.numerator, own.denominator) != result:
                return failure(
                    CheckKind.COMPARISON,
                    f"Por eliminação de Gauss, o determinante é {own}, e não {result}.",
                    *checks,
                )
            checks.append(
                passed(
                    CheckKind.COMPARISON,
                    "O determinante, recalculado por eliminação de Gauss com frações (um "
                    "algoritmo diferente do usado no cálculo), é o mesmo.",
                )
            )
        case "inverse":
            inverse = as_grid(result) if isinstance(result, sp.MatrixBase) else None
            identity = _identity(len(a))
            if (
                inverse is None
                or _product(a, inverse) != identity
                or _product(inverse, a) != identity
            ):
                return failure(
                    CheckKind.SYMBOLIC,
                    "Multiplicando A pela inversa, não se obtém a identidade.",
                    *checks,
                )
            checks.append(
                passed(
                    CheckKind.SYMBOLIC,
                    "A·A⁻¹ = I e A⁻¹·A = I, multiplicando com frações exatas.",
                )
            )
        case "transpose":
            transposed = as_grid(result) if isinstance(result, sp.MatrixBase) else None
            expected = [list(column) for column in zip(*a, strict=True)]
            if transposed != expected:
                return failure(
                    CheckKind.SYMBOLIC, "O resultado não troca linhas por colunas.", *checks
                )
            checks.append(
                passed(
                    CheckKind.SYMBOLIC,
                    "Cada elemento (i, j) do resultado é o elemento (j, i) da matriz.",
                )
            )
        case "trace":
            own_trace = sum((a[i][i] for i in range(len(a))), Fraction(0))
            if sp.Rational(own_trace.numerator, own_trace.denominator) != result:
                return failure(
                    CheckKind.COMPARISON,
                    f"A soma da diagonal é {own_trace}, e não {result}.",
                    *checks,
                )
            checks.append(
                passed(CheckKind.COMPARISON, "A soma da diagonal principal, refeita, é a mesma.")
            )
        case "rank":
            _, own_rank, _ = _eliminate(a)
            if own_rank != result:
                return failure(
                    CheckKind.COMPARISON,
                    f"Por eliminação de Gauss, o posto é {own_rank}, e não {result}.",
                    *checks,
                )
            checks.append(
                passed(
                    CheckKind.COMPARISON,
                    f"Por eliminação de Gauss com frações, a matriz tem {own_rank} linha(s) não "
                    "nula(s) na forma escalonada: o posto é o mesmo.",
                )
            )
    return report(VerificationStatus.VERIFIED_SYMBOLIC, checks)


def _verify_numerically(outcome: MatrixOutcome) -> VerificationReport:
    with mp.workdps(BASE_PRECISION):
        try:
            a = numeric_linear(outcome.tree)
        except OutsideDomain, TooLarge, ZeroDivisionError:
            return unverified(
                ReasonCode.INCONCLUSIVE,
                CheckKind.NUMERIC,
                "O avaliador independente não conseguiu recalcular a expressão.",
            )
        if not isinstance(a, mpmath.matrix) or not matrix_close(a, _as_matrix(outcome.operand)):
            return failure(
                CheckKind.NUMERIC,
                "Recalculando a expressão com o avaliador independente (mpmath), a matriz não "
                "é a mesma.",
            )
        checks: list[VerificationCheck] = [
            passed(
                CheckKind.NUMERIC,
                "A matriz da expressão, recalculada pelo avaliador independente (mpmath, 60 "
                "dígitos), coincide em 30 algarismos significativos.",
            )
        ]
        problem = _numeric_operation(outcome, a)
        if problem is not None:
            return failure(CheckKind.NUMERIC, problem, *checks)
    checks.append(
        passed(
            CheckKind.NUMERIC,
            "A operação, refeita com o mpmath (determinante por LU, A·A⁻¹ = I, transposição, "
            "diagonal ou escalonamento), confere com o resultado.",
        )
    )
    return report(VerificationStatus.VERIFIED_NUMERIC, checks)


def _numeric_operation(outcome: MatrixOutcome, a: mpmath.matrix) -> str | None:
    result = outcome.result
    number = None if isinstance(result, sp.MatrixBase | VectorValue) else to_mpf(result)
    scale = max((abs(a[i, j]) for i in range(a.rows) for j in range(a.cols)), default=mpf(0))
    match outcome.operation:
        case "determinant":
            value = number
            expected = mpmath.det(a)
            if value is None or not close(expected, value, scale**a.rows):
                return "O determinante pelo mpmath (decomposição LU) é diferente."
        case "inverse":
            if not isinstance(result, sp.MatrixBase):
                return "A inversa não é uma matriz."
            values = [
                [to_mpf(result[i, j]) for j in range(result.cols)] for i in range(result.rows)
            ]
            if any(value is None for row in values for value in row):
                return "A inversa tem um elemento que não é um número real."
            inverse = mpmath.matrix(values)
            identity = mpmath.eye(a.rows)
            for product in (a * inverse, inverse * a):
                for i in range(a.rows):
                    for j in range(a.cols):
                        if not close(identity[i, j], product[i, j], scale):
                            return "Multiplicando A pela inversa, não se obtém a identidade."
        case "transpose":
            if not isinstance(result, sp.MatrixBase) or not matrix_close(a.T, result):
                return "O resultado não troca linhas por colunas."
        case "trace":
            expected = sum((a[i, i] for i in range(a.rows)), mpf(0))
            if number is None or not close(expected, number, scale):
                return "A soma da diagonal é diferente."
        case "rank":
            if number is None or int(number) != _numeric_rank(a, scale):
                return "O posto pelo escalonamento numérico é diferente."
    return None


def _numeric_rank(a: mpmath.matrix, scale: mpf) -> int:
    rows = [[a[i, j] for j in range(a.cols)] for i in range(a.rows)]
    rank = 0
    for col in range(a.cols):
        pivot = max(range(rank, len(rows)), key=lambda r: abs(rows[r][col]), default=None)
        if pivot is None or abs(rows[pivot][col]) <= TOLERANCE * max(1, scale):
            continue
        rows[rank], rows[pivot] = rows[pivot], rows[rank]
        for r in range(rank + 1, len(rows)):
            factor = rows[r][col] / rows[rank][col]
            rows[r] = [x - factor * y for x, y in zip(rows[r], rows[rank], strict=True)]
        rank += 1
    return rank

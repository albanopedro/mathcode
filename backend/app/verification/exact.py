"""Exact rational arithmetic on the parser's AST, with Python's ``Fraction`` (ADR 0010).

A second, independent way to compute a calculation made only of rational
numbers, + − × ÷, integer powers and counting (n!, C(n, k), A(n, k), by their
definitions: ADR 0015): no SymPy, no rounding. Anything else (constants, other
functions, roots, degrees, variables) is out of scope: None.
"""

import math
from fractions import Fraction

from app.core.limits import MAX_RESULT_DIGITS
from app.parsing.ast import Binary, Call, Negate, Node, Number

# Larger arguments only appear in results the pipeline already refuses (ADR 0015).
_MAX_FACTORS = 10_000


class _OutOfScope(Exception):
    pass


def exact_value(node: Node) -> Fraction | None:
    """The exact value of a rational calculation, or None if it is not one."""
    try:
        return _value(node)
    except _OutOfScope, ZeroDivisionError:
        return None


def _value(node: Node) -> Fraction:
    match node:
        case Number(value=value):
            return Fraction(value)
        case Negate(operand=operand):
            return -_value(operand)
        case Binary(op="^", left=left, right=right):
            return _power(_value(left), _value(right))
        case Binary(op=op, left=left, right=right):
            a, b = _value(left), _value(right)
            if op == "+":
                return a + b
            if op == "-":
                return a - b
            if op == "*":
                return a * b
            return a / b
        case Call(name="factorial" | "C" | "A" as name, args=args):
            return Fraction(_count(name, [_natural(_value(arg)) for arg in args]))
    raise _OutOfScope


def _natural(value: Fraction) -> int:
    if value.denominator != 1 or value < 0:
        raise _OutOfScope  # an error in the pipeline (ADR 0015)
    return value.numerator


def _count(name: str, numbers: list[int]) -> int:
    """By the definitions: products of consecutive integers, one factor at a time."""
    if name == "factorial":
        (n,) = numbers
        return _falling(n, n)
    n, k = numbers
    if k > n:
        return 0
    if name == "A":
        return _falling(n, k)
    # C(n, k) = C(n, k − 1)·(n − k + 1)/k: every partial result is an integer.
    smaller = min(k, n - k)
    if smaller > _MAX_FACTORS:
        raise _OutOfScope
    result = 1
    for i in range(1, smaller + 1):
        result = result * (n - i + 1) // i
    return result


def _falling(n: int, k: int) -> int:
    """n·(n − 1)···(n − k + 1)."""
    if k > _MAX_FACTORS:
        raise _OutOfScope
    result = 1
    for factor in range(n - k + 1, n + 1):
        result *= factor
    return result


def _power(base: Fraction, exponent: Fraction) -> Fraction:
    if exponent.denominator != 1:
        raise _OutOfScope  # a root: irrational in general
    n = exponent.numerator
    if base == 0 and n <= 0:
        raise _OutOfScope  # 0^0 and division by zero: errors in the pipeline (ADR 0005)
    if base not in (0, 1, -1):
        digits = abs(n) * math.log10(max(abs(base.numerator), base.denominator))
        if digits > 2 * MAX_RESULT_DIGITS:
            raise _OutOfScope  # the pipeline already refuses results this large
    return base**n

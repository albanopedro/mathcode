"""Exact rational arithmetic on the parser's AST, with Python's ``Fraction`` (ADR 0010).

A second, independent way to compute a calculation made only of rational
numbers, + − × ÷ and integer powers: no SymPy, no rounding. Anything else
(constants, functions, roots, degrees, variables) is out of scope: None.
"""

import math
from fractions import Fraction

from app.core.limits import MAX_RESULT_DIGITS
from app.parsing.ast import Binary, Negate, Node, Number


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
    raise _OutOfScope


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

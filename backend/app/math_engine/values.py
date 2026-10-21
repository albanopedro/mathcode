"""Value helpers shared by the engine and the verification.

Small conversions that were written more than once: the same expression, the
same fraction, in different modules. They are here so that the convention
lives in one place.
"""

from fractions import Fraction

import sympy as sp


def simplified(value: sp.Expr) -> sp.Expr:
    """The expression simplified, unless it is already a rational number."""
    return value if value.is_Rational else sp.simplify(value)


def to_rational(value: Fraction) -> sp.Rational:
    """An exact fraction as a SymPy rational."""
    return sp.Rational(value.numerator, value.denominator)


def to_fraction(value: sp.Rational) -> Fraction:
    """A SymPy rational as an exact Python fraction."""
    return Fraction(int(value.p), int(value.q))

"""Polynomial helpers shared by equations, systems and division.

The shape of an expression is decided from the AST, before SymPy simplifies:
in "x/x = 1" the variable disappears during construction, but the equation
still has the variable in a denominator.
"""

from enum import StrEnum

import sympy as sp

from app.core.errors import ErrorCode, MathError
from app.parsing.ast import Binary, Call, Degrees, Negate, Number, Tree, variables, walk


class Shape(StrEnum):
    POLYNOMIAL = "polynomial"
    RATIONAL = "rational"  # polynomial except for the variable in denominators
    OTHER = "other"  # functions, exponents or roots of the variable


def shape(tree: Tree, name: str) -> tuple[Shape, str | None]:
    """How ``name`` appears in ``tree``, with the reason when it is not polynomial."""
    result = Shape.POLYNOMIAL
    for node in walk(tree):
        match node:
            case Call(name=function) if name in variables(node):
                return Shape.OTHER, f"a variável aparece dentro de {function}(...)"
            case Degrees() if name in variables(node):
                return Shape.OTHER, "a variável aparece num ângulo em graus"
            case Binary(op="^", right=right) if name in variables(right):
                return Shape.OTHER, "a variável aparece num expoente"
            case Binary(op="^", left=left, right=right) if name in variables(left):
                exponent = _integer_literal(right)
                if exponent is None:
                    return Shape.OTHER, "a variável está elevada a um expoente não inteiro"
                if exponent < 0:
                    result = Shape.RATIONAL
            case Binary(op="/", right=right) if name in variables(right):
                result = Shape.RATIONAL
    reason = "a variável aparece num denominador" if result is Shape.RATIONAL else None
    return result, reason


def require_polynomial(tree: Tree, name: str, context: str) -> None:
    found, reason = shape(tree, name)
    if found is not Shape.POLYNOMIAL:
        raise MathError(
            ErrorCode.UNSUPPORTED_FEATURE,
            f"{context} só aceita polinômios, e aqui {reason}.",
        )


def _integer_literal(node: Tree) -> int | None:
    match node:
        case Number(value=value) if value.isdigit():
            return int(value)
        case Negate(operand=Number(value=value)) if value.isdigit():
            return -int(value)
    return None


def has_rational_coefficients(poly: sp.Poly) -> bool:
    """Sturm-based root counting needs coefficients in ZZ or QQ."""
    return poly.domain.is_ZZ or poly.domain.is_QQ


def real_roots_with_multiplicity(poly: sp.Poly) -> list[tuple[sp.Expr, int]]:
    """Distinct real roots in increasing order, each with its multiplicity.

    Uses ``real_roots``, which returns exact roots: rationals, quadratic surds,
    or ``CRootOf`` when no simple real radical form exists (e.g. three real roots
    of a cubic, where Cardano's formula needs complex numbers).
    """
    counted: dict[sp.Expr, int] = {}
    for root in sp.real_roots(poly):
        counted[root] = counted.get(root, 0) + 1
    return list(counted.items())


def count_distinct_real_roots(poly: sp.Poly) -> int:
    """Independent count by Sturm sequences (a different algorithm than real_roots)."""
    return int(poly.count_roots())

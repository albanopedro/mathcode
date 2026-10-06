"""Rewriting expressions (simplify, factor, expand) and polynomial division.

Equations live in ``equations.py`` and systems in ``systems.py``.
"""

from collections.abc import Callable
from dataclasses import dataclass

import sympy as sp

from app.core.errors import ErrorCode, MathError
from app.core.notices import Notice, NoticeCode
from app.formatting.expressions import plain
from app.math_engine.inputs import require_expression
from app.math_engine.polynomials import require_polynomial
from app.models.intents import (
    ExpandParams,
    FactorParams,
    IntentName,
    PolynomialDivisionParams,
    SimplifyParams,
)
from app.parsing import ParseResult, parse
from app.parsing.ast import Binary, Node, variables
from app.parsing.build import ExpressionBuilder, ensure_within_limits, symbol

# -- rewrites: simplify, factor, expand ------------------------------------------------


@dataclass(frozen=True)
class RewriteOutcome:
    """An expression rewritten into an equivalent form."""

    operation: IntentName
    parsed: ParseResult
    tree: Node
    original: sp.Expr
    result: sp.Expr
    changed: bool  # False when the expression was already in the requested form
    notices: tuple[Notice, ...]


def simplify(params: SimplifyParams) -> RewriteOutcome:
    parsed = parse(params.expression)
    return _rewrite(IntentName.SIMPLIFY, parsed, require_expression(parsed), sp.simplify)


def expand(params: ExpandParams) -> RewriteOutcome:
    parsed = parse(params.expression)
    return _rewrite(IntentName.EXPAND, parsed, require_expression(parsed), sp.expand)


def _rewrite(
    operation: IntentName,
    parsed: ParseResult,
    tree: Node,
    transform: Callable[[sp.Expr], sp.Expr],
) -> RewriteOutcome:
    builder = ExpressionBuilder()
    original = builder.build(tree)
    result = transform(original)
    ensure_within_limits(result)
    notices = parsed.notices + tuple(builder.notices) + _domain_notices(builder, result)
    return RewriteOutcome(operation, parsed, tree, original, result, result != original, notices)


def _domain_notices(builder: ExpressionBuilder, result: sp.Expr) -> tuple[Notice, ...]:
    """Points where the original is undefined (a denominator is zero) but the result is not.

    Only denominators with a single variable whose zeros SymPy can list are
    checked; other domain restrictions (sqrt, log) are not detected yet.
    """
    notices: list[Notice] = []
    for denominator in builder.denominators:
        if len(denominator.free_symbols) != 1:
            continue
        (var,) = denominator.free_symbols
        zeros = sp.solveset(denominator, var, domain=sp.S.Reals)
        if not isinstance(zeros, sp.FiniteSet):
            continue
        for zero in zeros:
            if result.subs(var, zero).is_finite:
                notices.append(
                    Notice(
                        NoticeCode.DOMAIN_CHANGED,
                        f"A expressão original não é definida para {var} = {plain(zero)}; "
                        f"o resultado só equivale a ela para {var} ≠ {plain(zero)}.",
                    )
                )
    return tuple(notices)


# -- factor ---------------------------------------------------------------------------


@dataclass(frozen=True)
class PrimeFactorization:
    """Factoring a number: an integer written as a product of primes."""

    parsed: ParseResult
    tree: Node
    number: int
    factors: tuple[tuple[int, int], ...]  # (prime, exponent), increasing primes
    notices: tuple[Notice, ...]


def factor(params: FactorParams) -> RewriteOutcome | PrimeFactorization:
    """Polynomials and rational expressions over ℚ; integers into primes."""
    parsed = parse(params.expression)
    tree = require_expression(parsed)
    if variables(tree):
        return _rewrite(IntentName.FACTOR, parsed, tree, sp.factor)

    builder = ExpressionBuilder()
    value = builder.build(tree)
    if not value.is_Integer:
        raise MathError(
            ErrorCode.INVALID_INPUT_FOR_INTENT,
            "Só números inteiros e expressões com variáveis podem ser fatorados; "
            f"{plain(value)} não é inteiro.",
        )
    number = int(value)
    if abs(number) < 2:
        raise MathError(
            ErrorCode.INVALID_INPUT_FOR_INTENT,
            f"{number} não tem fatoração em primos.",
        )
    factors = tuple(sorted(sp.factorint(abs(number)).items()))
    return PrimeFactorization(
        parsed, tree, number, factors, parsed.notices + tuple(builder.notices)
    )


# -- polynomial division ------------------------------------------------------------------


@dataclass(frozen=True)
class DivisionOutcome:
    parsed: ParseResult
    dividend_tree: Node
    divisor_tree: Node
    variable: sp.Symbol
    dividend: sp.Expr
    divisor: sp.Expr
    quotient: sp.Expr
    remainder: sp.Expr
    notices: tuple[Notice, ...]


def divide(params: PolynomialDivisionParams) -> DivisionOutcome:
    """Quotient and remainder of A / B: A = B·Q + R, with deg R < deg B."""
    parsed = parse(params.division)
    tree = require_expression(parsed)
    if not (isinstance(tree, Binary) and tree.op == "/"):
        raise MathError(
            ErrorCode.INVALID_INPUT_FOR_INTENT,
            "Escreva a divisão como A / B, por exemplo (x^3 - 1)/(x - 1).",
        )
    names = variables(tree)
    if not names:
        raise MathError(
            ErrorCode.INVALID_INPUT_FOR_INTENT,
            "A divisão não tem variável; para dividir números, use o cálculo comum.",
        )
    if len(names) > 1:
        raise MathError(
            ErrorCode.UNSUPPORTED_FEATURE,
            f"Divisão de polinômios com mais de uma variável ({', '.join(sorted(names))}) "
            "ainda não é suportada.",
        )
    (name,) = names
    require_polynomial(tree.left, name, "A divisão de polinômios")
    require_polynomial(tree.right, name, "A divisão de polinômios")

    # Each side is built on its own: building A/B would let SymPy cancel factors.
    builder = ExpressionBuilder()
    dividend = sp.expand(builder.build(tree.left))
    divisor = sp.expand(builder.build(tree.right))
    if divisor == 0:
        raise MathError(ErrorCode.DIVISION_BY_ZERO, "Divisão por zero.", tree.position)
    var = symbol(name)
    quotient, remainder = sp.div(dividend, divisor, var)
    return DivisionOutcome(
        parsed=parsed,
        dividend_tree=tree.left,
        divisor_tree=tree.right,
        variable=var,
        dividend=dividend,
        divisor=divisor,
        quotient=sp.expand(quotient),
        remainder=sp.expand(remainder),
        notices=parsed.notices + tuple(builder.notices),
    )

"""A second differentiator, written with the textbook rules (ADR 0010).

It walks the expression tree and applies the sum, product, power and chain
rules and a table of derivatives of the functions the builder produces. It
never calls SymPy's ``diff``, so comparing both results is a comparison of
two methods. Anything outside the table (for example ``sign``, which appears
in derivatives of ``abs``) is out of scope: None.
"""

from collections.abc import Callable

import sympy as sp

type Rule = Callable[[sp.Expr], sp.Expr]

# f'(u) for each function f; the chain rule multiplies by u'.
_TABLE: dict[type, Rule] = {
    sp.sin: sp.cos,
    sp.cos: lambda u: -sp.sin(u),
    sp.tan: lambda u: 1 + sp.tan(u) ** 2,
    sp.asin: lambda u: 1 / sp.sqrt(1 - u**2),
    sp.acos: lambda u: -1 / sp.sqrt(1 - u**2),
    sp.atan: lambda u: 1 / (1 + u**2),
    sp.exp: sp.exp,
    sp.log: lambda u: 1 / u,
    sp.Abs: sp.sign,  # d|u|/du = sign(u), for u != 0 (real domain)
}


class _OutOfScope(Exception):
    pass


def differentiate(expr: sp.Expr, var: sp.Symbol, order: int = 1) -> sp.Expr | None:
    """The ``order``-th derivative by the textbook rules, or None if out of scope."""
    try:
        for _ in range(order):
            expr = _d(expr, var)
    except _OutOfScope:
        return None
    return expr


def _d(expr: sp.Expr, var: sp.Symbol) -> sp.Expr:
    if not expr.has(var):
        return sp.Integer(0)
    if expr == var:
        return sp.Integer(1)
    if expr.is_Add:
        return sp.Add(*(_d(term, var) for term in expr.args))
    if expr.is_Mul:
        factors = expr.args
        return sp.Add(
            *(
                sp.Mul(*factors[:i], _d(factor, var), *factors[i + 1 :])
                for i, factor in enumerate(factors)
            )
        )
    if expr.is_Pow:
        base, exponent = expr.args
        if not exponent.has(var):
            return exponent * base ** (exponent - 1) * _d(base, var)
        if not base.has(var):
            return expr * sp.log(base) * _d(exponent, var)
        # u^v = e^(v·ln u): (u^v)' = u^v·(v'·ln u + v·u'/u)
        return expr * (_d(exponent, var) * sp.log(base) + exponent * _d(base, var) / base)
    rule = _TABLE.get(type(expr))
    if rule is None or len(expr.args) != 1:
        raise _OutOfScope
    inner = expr.args[0]
    return rule(inner) * _d(inner, var)

"""A definite integral by the fundamental theorem of calculus (ADR 0010).

For a polynomial or rational integrand with rational coefficients and rational
bounds, ∫ₐᵇ f = F(b) − F(a) holds when F' = f and F is smooth on [a, b]. Both
conditions are proved here, not assumed:

- F' = f: the antiderivative is differentiated and the difference reduces to 0
  (differentiating is a different algorithm from integrating);
- smoothness: every denominator, every ``ln|u|`` argument and every ``atan``
  denominator of F is a polynomial with no real root in [a, b] (Sturm).

Anything else (other functions, irrational coefficients, infinite bounds) is
out of scope; the definite integral is then checked by quadrature only.
"""

from dataclasses import dataclass

import sympy as sp

from app.formatting.expressions import plain
from app.verification.symbolic import reduces_to_zero


@dataclass(frozen=True)
class NewtonLeibniz:
    value: sp.Expr | None  # F(b) − F(a), when every condition was proved
    note: str  # what was proved, or why the theorem could not be used


def newton_leibniz(
    integrand: sp.Expr, var: sp.Symbol, lower: sp.Expr, upper: sp.Expr
) -> NewtonLeibniz | None:
    """F(b) − F(a) with every condition proved; None when the integrand is out of scope."""
    if not (lower.is_Rational and upper.is_Rational) or integrand.free_symbols - {var}:
        return None
    numerator, denominator = sp.fraction(sp.cancel(integrand))
    if not (_rational_poly(numerator, var) and _rational_poly(denominator, var)):
        return None

    if _has_root(denominator, var, lower, upper):
        return NewtonLeibniz(None, "a função tem um polo no intervalo")
    raw = sp.integrate(integrand, var)
    if raw.has(sp.Integral, sp.RootSum):
        return NewtonLeibniz(None, "a primitiva não tem uma forma que permita a conferência")
    if reduces_to_zero(sp.diff(raw, var) - integrand) is None:
        return NewtonLeibniz(None, "não foi provado que a derivada da primitiva é o integrando")
    antiderivative = raw.replace(sp.log, lambda u: sp.log(sp.Abs(u)))
    obstacle = _smoothness_obstacle(antiderivative, var, lower, upper)
    if obstacle is not None:
        return NewtonLeibniz(None, obstacle)
    value = antiderivative.subs(var, upper) - antiderivative.subs(var, lower)
    return NewtonLeibniz(
        value,
        f"a primitiva F = {plain(antiderivative)} é suave em [{plain(lower)}, {plain(upper)}] "
        "e F' é o integrando",
    )


def _rational_poly(expr: sp.Expr, var: sp.Symbol) -> bool:
    try:
        return sp.Poly(expr, var).domain in (sp.ZZ, sp.QQ)
    except sp.PolynomialError:
        return False


def _has_root(expr: sp.Expr, var: sp.Symbol, lower: sp.Expr, upper: sp.Expr) -> bool:
    poly = sp.Poly(expr, var)
    if poly.degree() <= 0:
        return False
    low, high = sorted((lower, upper))
    return poly.count_roots(low, high) > 0


def _smoothness_obstacle(
    antiderivative: sp.Expr, var: sp.Symbol, lower: sp.Expr, upper: sp.Expr
) -> str | None:
    """None if F is smooth on [lower, upper]; otherwise why that was not proved."""
    must_not_vanish: list[sp.Expr] = []
    for node in sp.preorder_traversal(antiderivative):
        if not node.has(var):
            continue
        if node.is_Pow:
            base, exponent = node.args
            if not exponent.is_Integer:
                return "a primitiva tem uma potência não inteira"
            if exponent.is_negative:
                must_not_vanish.append(base)
        elif isinstance(node, sp.log | sp.Abs):
            argument = node.args[0]
            if isinstance(argument, sp.Abs):
                continue  # ln|u|: the Abs node itself is checked next
            top, bottom = sp.fraction(sp.together(argument))
            must_not_vanish += [top, bottom]
        elif isinstance(node, sp.atan):
            must_not_vanish.append(sp.fraction(sp.together(node.args[0]))[1])
        elif not (node.is_Add or node.is_Mul or node.is_Symbol or node.is_Number):
            return "a primitiva usa uma função fora do alcance desta conferência"
    for expr in must_not_vanish:
        if not _rational_poly(expr, var):
            return "a primitiva tem uma forma fora do alcance desta conferência"
        if _has_root(expr, var, lower, upper):
            return "a primitiva não é suave em todo o intervalo"
    return None

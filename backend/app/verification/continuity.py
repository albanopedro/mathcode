"""Proving that a function is continuous at a point (ADR 0010).

Every function of the vocabulary is continuous on the interior of its real
domain. So, if at the point every denominator is nonzero, every square root
and logarithm has a positive argument, ``tan`` is away from its poles, ``asin``
and ``acos`` are inside (−1, 1) and every power with a variable exponent has a
positive base, the function is continuous there, and its limit is its value.
Each condition is decided exactly (SymPy at the point); if one cannot be
decided, continuity is not claimed.
"""

import sympy as sp

from app.parsing.ast import Binary, Call, Degrees, Negate, Node, variables
from app.parsing.build import ExpressionBuilder, symbol


def continuity_obstacle(tree: Node, name: str, point: sp.Expr) -> str | None:
    """None if ``tree`` is proved continuous at ``name = point``; otherwise what prevents it."""
    return _Walker(name, point).check(tree)


class _Walker:
    def __init__(self, name: str, point: sp.Expr) -> None:
        self._name = name
        self._subs = {symbol(name): point}

    def _at_point(self, node: Node) -> sp.Expr:
        return ExpressionBuilder().build(node).subs(self._subs)

    def check(self, node: Node) -> str | None:
        match node:
            case Negate(operand=operand) | Degrees(operand=operand):
                return self.check(operand)
            case Binary(op="/", left=left, right=right):
                return self.check(left) or self.check(right) or self._nonzero(right)
            case Binary(op="^", left=left, right=right):
                return self.check(left) or self.check(right) or self._power(left, right)
            case Binary(left=left, right=right):
                return self.check(left) or self.check(right)
            case Call(args=args):
                for arg in args:
                    if (problem := self.check(arg)) is not None:
                        return problem
                return self._call(node)
        return None  # numbers, constants and variables are continuous

    def _nonzero(self, node: Node) -> str | None:
        value = self._at_point(node)
        if value.is_zero is False:
            return None
        if value.is_zero:
            return "um denominador se anula no ponto"
        return "não foi possível decidir se um denominador se anula no ponto"

    def _positive(self, node: Node, what: str) -> str | None:
        value = self._at_point(node)
        if value.is_positive:
            return None
        if value.is_zero:
            return f"{what} vale 0 no ponto (borda do domínio)"
        return f"não foi possível provar que {what} é positivo no ponto"

    def _power(self, base: Node, exponent: Node) -> str | None:
        if not variables(exponent) & {self._name}:
            power = ExpressionBuilder().build(exponent)
            if power.is_integer:
                # x^n is continuous everywhere for n >= 0, and where x != 0 for n < 0.
                return None if power.is_nonnegative else self._nonzero(base)
        return self._positive(base, "a base de uma potência")

    def _call(self, node: Call) -> str | None:
        argument = node.args[0]
        match node.name:
            case "sqrt":
                return self._positive(argument, "o argumento de uma raiz quadrada")
            case "ln":
                return self._positive(argument, "o argumento de um logaritmo")
            case "log":
                problem = self._positive(argument, "o argumento de um logaritmo")
                if problem is None and len(node.args) == 2:
                    base = self._at_point(node.args[1])
                    if not (base.is_positive and (base - 1).is_zero is False):
                        return "não foi possível provar que a base do logaritmo é válida no ponto"
                return problem
            case "tan":
                cosine = sp.cos(self._at_point(argument))
                if cosine.is_zero is False:
                    return None
                return "a tangente tem um polo no ponto"
            case "asin" | "acos":
                inside = 1 - sp.Abs(self._at_point(argument))
                if inside.is_positive:
                    return None
                return f"o argumento de {node.name} está na borda do domínio no ponto"
        return None  # abs, sin, cos, atan, exp: continuous everywhere

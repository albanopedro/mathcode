"""AST -> SymPy, one explicit constructor per node.

No text is ever handed to SymPy: ``sympify`` and ``parse_expr`` use ``eval``
(ADR 0002). This is also where the conventions of ADR 0005 are applied.
"""

import math
from fractions import Fraction

import sympy as sp

from app.core.errors import ErrorCode, MathError
from app.core.limits import MAX_RESULT_DIGITS, MAX_SYMBOLIC_EXPONENT
from app.core.notices import Notice, NoticeCode
from app.parsing.ast import (
    Binary,
    Call,
    Constant,
    Degrees,
    Matrix,
    Negate,
    Node,
    Number,
    Point,
    Variable,
    Vector,
    walk,
)
from app.parsing.vocabulary import FACTORIAL, TRIGONOMETRIC

_UNDEFINED = (sp.zoo, sp.nan, sp.oo, -sp.oo)
_LOG10_2 = math.log10(2)
_LN_10 = math.log(10)

_SIMPLE_FUNCTIONS = {
    "abs": sp.Abs,
    "sin": sp.sin,
    "cos": sp.cos,
    "tan": sp.tan,
    "atan": sp.atan,
    "exp": sp.exp,
}


def symbol(name: str) -> sp.Symbol:
    """Every variable is real: the default domain is ℝ (ADR 0005)."""
    return sp.Symbol(name, real=True)


def digits(value: sp.Rational) -> int:
    """Approximate number of decimal digits of the larger of numerator and denominator."""
    bits = max(abs(int(value.p)).bit_length(), int(value.q).bit_length())
    return math.ceil(bits * _LOG10_2)


def ensure_within_limits(expr: sp.Expr, position: int | None = None) -> None:
    if expr.is_Rational and digits(expr) > MAX_RESULT_DIGITS:
        raise MathError(
            ErrorCode.LIMIT_EXCEEDED,
            f"O resultado teria mais de {MAX_RESULT_DIGITS} dígitos.",
            position,
        )


class ExpressionBuilder:
    """Builds SymPy expressions and records what SymPy would otherwise forget.

    SymPy simplifies while constructing (``x/x`` becomes ``1``), so the
    denominators are recorded here, before that happens, to detect a
    simplification that changes the domain.
    """

    def __init__(self) -> None:
        self.notices: list[Notice] = []
        self.denominators: list[sp.Expr] = []

    def build(self, node: Node) -> sp.Expr:
        expr = self._build(node)
        if expr.has(*_UNDEFINED):
            raise MathError(
                ErrorCode.DOMAIN_ERROR, "A expressão não é definida aqui.", node.position
            )
        ensure_within_limits(expr, node.position)
        return expr

    def _build(self, node: Node) -> sp.Expr:
        match node:
            case Number(value=value):
                fraction = Fraction(value)
                return sp.Rational(fraction.numerator, fraction.denominator)
            case Variable(name=name):
                return symbol(name)
            case Constant(name="pi"):
                return sp.pi
            case Constant(name="e"):
                return sp.E
            case Negate(operand=operand):
                return -self.build(operand)
            case Degrees(operand=operand):
                return self.build(operand) * sp.pi / 180
            case Binary():
                return self._binary(node)
            case Call():
                return self._call(node)
            case Point():
                raise MathError(
                    ErrorCode.INVALID_INPUT_FOR_INTENT,
                    "Pontos, como (1, 2), só entram na operação Geometria ou em frases como "
                    "'distância entre (1, 2) e (4, 6)'.",
                    node.position,
                )
            case Matrix() | Vector():
                raise MathError(
                    ErrorCode.INVALID_INPUT_FOR_INTENT,
                    "Matrizes e vetores só entram nas operações Matrizes e Vetores, em "
                    "expressões com colchetes no Automático ou em frases como 'determinante de "
                    "[[1, 2], [3, 4]]' e 'norma de [3, 4]'.",
                    node.position,
                )
        raise AssertionError(f"unknown node: {node!r}")

    def _binary(self, node: Binary) -> sp.Expr:
        left = self.build(node.left)
        right = self.build(node.right)
        match node.op:
            case "+":
                return left + right
            case "-":
                return left - right
            case "*":
                return left * right
            case "/":
                if right.is_zero:
                    raise MathError(ErrorCode.DIVISION_BY_ZERO, "Divisão por zero.", node.position)
                if right.free_symbols:
                    self.denominators.append(right)
                return left / right
            case "^":
                return self._power(node, left, right)
        raise AssertionError(f"unknown operator: {node.op}")

    def _power(self, node: Binary, base: sp.Expr, exponent: sp.Expr) -> sp.Expr:
        if base.is_zero and exponent.is_zero:
            raise MathError(ErrorCode.DOMAIN_ERROR, "0^0 é uma indeterminação.", node.position)
        if base.is_zero and exponent.is_negative:
            raise MathError(
                ErrorCode.DIVISION_BY_ZERO,
                "Zero elevado a expoente negativo é uma divisão por zero.",
                node.position,
            )

        if base.free_symbols and exponent.is_number:
            if exponent.is_Integer and abs(exponent) > MAX_SYMBOLIC_EXPONENT:
                raise MathError(
                    ErrorCode.LIMIT_EXCEEDED,
                    f"Expoentes acima de {MAX_SYMBOLIC_EXPONENT} em expressões com variáveis "
                    "não são aceitos.",
                    node.position,
                )
            if exponent.is_negative:
                self.denominators.append(base)

        if base.is_number and exponent.is_Rational:
            self._check_power_size(node, base, exponent)
            if base.is_negative and not exponent.is_integer:
                if exponent.q % 2 == 0:
                    raise MathError(
                        ErrorCode.DOMAIN_ERROR,
                        "Raiz de índice par de número negativo não é real (o domínio é ℝ).",
                        node.position,
                    )
                self.notices.append(
                    Notice(
                        NoticeCode.REAL_ROOT,
                        "A raiz de índice ímpar de um número negativo foi calculada como a "
                        "raiz real (por exemplo, (-8)^(1/3) = -2).",
                    )
                )
                return sp.Integer(-1) ** exponent.p * (-base) ** exponent
        elif base.is_number and base.is_negative and exponent.is_number:
            if exponent.is_integer is not True:
                raise MathError(
                    ErrorCode.DOMAIN_ERROR,
                    "Número negativo elevado a expoente irracional não é real (o domínio é ℝ).",
                    node.position,
                )
        return base**exponent

    def _check_power_size(self, node: Binary, base: sp.Expr, exponent: sp.Rational) -> None:
        if exponent.is_zero or base in (sp.Integer(0), sp.Integer(1), sp.Integer(-1)):
            return
        estimate = sp.N(abs(exponent) * abs(sp.log(abs(base), 10)), 15)
        if estimate > MAX_RESULT_DIGITS:
            raise MathError(
                ErrorCode.LIMIT_EXCEEDED,
                f"O resultado teria mais de {MAX_RESULT_DIGITS} dígitos.",
                node.position,
            )

    def _call(self, node: Call) -> sp.Expr:
        args = [self.build(arg) for arg in node.args]
        argument = args[0]
        name = node.name

        if name in TRIGONOMETRIC and _is_plain_number(node.args[0]):
            self.notices.append(
                Notice(
                    NoticeCode.ANGLE_IN_RADIANS,
                    "Ângulos são lidos em radianos. Para graus, use o símbolo °, como em sin(30°).",
                )
            )

        match name:
            case "factorial" | "C" | "A":
                return self._counting(node, args)
            case "sqrt":
                if argument.is_number and argument.is_negative:
                    raise MathError(
                        ErrorCode.DOMAIN_ERROR,
                        "Raiz quadrada de número negativo não é real (o domínio é ℝ).",
                        node.position,
                    )
                return sp.sqrt(argument)
            case "asin" | "acos":
                if argument.is_number and (sp.Abs(argument) - 1).is_positive:
                    raise MathError(
                        ErrorCode.DOMAIN_ERROR,
                        f"{name} só é definida para valores entre -1 e 1.",
                        node.position,
                    )
                return sp.asin(argument) if name == "asin" else sp.acos(argument)
            case "ln":
                self._check_log_argument(node, argument)
                return sp.log(argument)
            case "log":
                self._check_log_argument(node, argument)
                if len(args) == 2:
                    base = args[1]
                    if base.is_number and (base.is_positive is False or base == 1):
                        raise MathError(
                            ErrorCode.DOMAIN_ERROR,
                            "A base do logaritmo precisa ser positiva e diferente de 1.",
                            node.position,
                        )
                    return sp.log(argument, base)
                self.notices.append(
                    Notice(
                        NoticeCode.LOG_BASE_10,
                        "log(x) é o logaritmo na base 10. Para o logaritmo natural, use ln(x).",
                    )
                )
                return sp.log(argument, 10)
            case _:
                return _SIMPLE_FUNCTIONS[name](argument)

    def _counting(self, node: Call, args: list[sp.Expr]) -> sp.Expr:
        """n!, C(n, k) and A(n, k): natural numbers only (ADR 0015)."""
        what = "O fatorial" if node.name == FACTORIAL else f"{node.name}(n, k)"
        numbers = [_natural(what, arg, value) for arg, value in zip(node.args, args, strict=True)]
        if node.name == FACTORIAL:
            (n,) = numbers
            _check_count_digits(log10_falling(n, n), node)
            return sp.factorial(n)
        n, k = numbers
        if k > n:
            choose = "escolher" if node.name == "C" else "ordenar"
            self.notices.append(
                Notice(
                    NoticeCode.COUNT_IS_ZERO,
                    f"Em {node.name}({n}, {k}), k = {k} é maior que n = {n}: não há como "
                    f"{choose} {k} de {n}, e o resultado é 0. A ordem é {node.name}(n, k).",
                )
            )
            return sp.Integer(0)
        if node.name == "A":
            _check_count_digits(log10_falling(n, k), node)
            return sp.ff(n, k)
        smaller = min(k, n - k)
        _check_count_digits(log10_falling(n, smaller) - log10_falling(smaller, smaller), node)
        return sp.binomial(n, k)

    @staticmethod
    def _check_log_argument(node: Call, argument: sp.Expr) -> None:
        if argument.is_number and argument.is_positive is False:
            raise MathError(
                ErrorCode.DOMAIN_ERROR,
                "O logaritmo só é definido para números positivos.",
                node.position,
            )


def _natural(what: str, node: Node, value: sp.Expr) -> int:
    if any(isinstance(child, Variable) for child in walk(node)):
        raise MathError(
            ErrorCode.UNSUPPORTED_FEATURE,
            f"{what} só aceita números, sem variáveis, como em 5!, C(10, 3) e A(6, 2).",
            node.position,
        )
    if value.is_integer is not True or value.is_negative:
        raise MathError(
            ErrorCode.DOMAIN_ERROR,
            f"{what} só é definido para inteiros não negativos (0, 1, 2, ...).",
            node.position,
        )
    return int(value)


def log10_falling(n: int, k: int) -> float:
    """Decimal digits of n·(n − 1)···(n − k + 1), which is A(n, k); n! when k = n."""
    if k == 0:
        return 0.0
    if n < 10**15:
        return (math.lgamma(n + 1) - math.lgamma(n - k + 1)) / _LN_10
    return k * math.log10(n)  # every factor is close to n


def _check_count_digits(log10: float, node: Call) -> None:
    if log10 > MAX_RESULT_DIGITS:
        raise MathError(
            ErrorCode.LIMIT_EXCEEDED,
            f"O resultado teria mais de {MAX_RESULT_DIGITS} dígitos.",
            node.position,
        )


def _is_plain_number(node: Node) -> bool:
    """True for an angle written without pi, ° or variables, such as sin(30)."""
    for child in walk(node):
        if isinstance(child, Variable | Degrees) or (
            isinstance(child, Constant) and child.name == "pi"
        ):
            return False
    return True

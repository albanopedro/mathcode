"""Independent numeric evaluation of the parser's AST (ADR 0003).

This evaluator reads the AST directly with mpmath and shares no code with the
SymPy builder, so a mistake in one is unlikely to be repeated in the other. It
applies the same conventions (ADR 0005) on its own.

Precision adapts to the input: it is raised until it exceeds the size of the
largest intermediate value by ``BASE_PRECISION`` digits, so cancellations such
as ``10^3999 + 1 - 10^3999`` are still exact. Each evaluation reports its own
error bound, which lets comparisons be strict (30 significant digits) without
false alarms.
"""

import hashlib
import math
import random
from collections.abc import Iterator, Mapping, Sequence
from dataclasses import dataclass
from fractions import Fraction

import mpmath
import sympy as sp
from mpmath import mp, mpf

from app.core.limits import MAX_RESULT_DIGITS
from app.parsing.ast import Binary, Call, Constant, Degrees, Negate, Node, Number, Variable

BASE_PRECISION = 60  # digits beyond the largest intermediate value
GUARD_DIGITS = 10  # margin between the working precision and the reported error bound
MAX_PRECISION = 2 * MAX_RESULT_DIGITS + BASE_PRECISION
RELATIVE_TOLERANCE = mpf("1e-30")

_LOG10_2 = math.log10(2)

# Variable name -> exact decimal value, e.g. {"x": "-3.141593"}.
type Point = Mapping[str, str]


class OutsideDomain(Exception):
    """The expression has no real value at this point."""


class TooLarge(Exception):
    """Intermediate values are too large to evaluate with a meaningful error bound."""


@dataclass(frozen=True)
class Evaluation:
    value: mpf
    error_bound: mpf  # absolute


def evaluate(node: Node, point: Point | None = None, digits: int = BASE_PRECISION) -> Evaluation:
    """Value at ``point`` with at least ``digits`` digits beyond the largest intermediate value."""
    point = point or {}
    precision = digits
    while True:
        evaluator = _Evaluator(point)
        value: mpf | None = None
        with mp.workdps(precision):
            try:
                value = evaluator.run(node)
            except OutsideDomain:
                # Possibly a false zero caused by too little precision: retry if
                # larger values were seen, otherwise it is genuine.
                if precision >= digits + evaluator.largest_digits:
                    raise
        needed = digits + evaluator.largest_digits
        if value is not None and precision >= needed:
            exponent = evaluator.largest_digits - precision + GUARD_DIGITS
            return Evaluation(value, mpf(10) ** exponent)
        if needed > MAX_PRECISION + digits - BASE_PRECISION:
            raise TooLarge
        precision = needed


def agrees(expected: Evaluation, actual: mpf, other_bound: mpf | None = None) -> bool:
    """True if ``actual`` matches ``expected`` within 30 significant digits or the error bounds."""
    with mp.workdps(BASE_PRECISION):
        difference = abs(expected.value - actual)
        scale = max(abs(expected.value), abs(actual))
        allowed = expected.error_bound + (other_bound or 0)
        return difference <= max(RELATIVE_TOLERANCE * scale, allowed)


def to_mpf(expr: sp.Expr, point: Mapping[sp.Symbol, str] | None = None) -> mpf | None:
    """Value of a SymPy result at a point, or None if it is not a finite real number.

    SymPy's ``evalf`` is adaptive: the 50 digits returned are significant digits
    of the result itself, even after cancellation.
    """
    subs = {s: rational(v) for s, v in (point or {}).items()}
    value = expr.evalf(50, subs=subs)
    if not value.is_Number or value.is_real is not True or not value.is_finite:
        return None
    with mp.workdps(BASE_PRECISION):
        return mpf(str(value))


def decimal(expr: sp.Expr) -> str:
    """A SymPy number as an exact decimal string with enough digits to be a test point."""
    return str(sp.N(expr, BASE_PRECISION + GUARD_DIGITS))


def sample_points(key: str, names: Sequence[str]) -> Iterator[dict[str, str]]:
    """Endless pseudo-random points in [-10, 10], always the same for the same key."""
    seed = int.from_bytes(hashlib.sha256(key.encode()).digest()[:8])
    # Not security-related: reproducible test points for verification.
    rng = random.Random(seed)  # noqa: S311
    while True:
        yield {name: f"{rng.uniform(-10, 10):.6f}" for name in names}


def rational(value: str) -> sp.Rational:
    """An exact decimal string as a SymPy rational (via Fraction: no text reaches SymPy)."""
    fraction = Fraction(value)
    return sp.Rational(fraction.numerator, fraction.denominator)


class _Evaluator:
    def __init__(self, point: Point) -> None:
        self._point = point
        self.largest_digits = 0  # decimal digits of the largest intermediate value

    def run(self, node: Node) -> mpf:
        value = self._eval(node)
        if not isinstance(value, mpf) or not mpmath.isfinite(value):
            raise OutsideDomain
        return value

    def _eval(self, node: Node) -> mpf:
        value = self._compute(node)
        if isinstance(value, mpf) and mpmath.isfinite(value) and value != 0:
            digits = math.ceil(mpmath.mag(value) * _LOG10_2)
            self.largest_digits = max(self.largest_digits, digits)
        return value

    def _compute(self, node: Node) -> mpf:
        match node:
            case Number(value=value):
                return mpf(value)
            case Variable(name=name):
                return mpf(self._point[name])
            case Constant(name="pi"):
                return +mp.pi
            case Constant(name="e"):
                return +mp.e
            case Negate(operand=operand):
                return -self._eval(operand)
            case Degrees(operand=operand):
                return self._eval(operand) * mp.pi / 180
            case Binary(op="^"):
                return self._power(node)
            case Binary(op=op, left=left, right=right):
                a, b = self._eval(left), self._eval(right)
                if op == "+":
                    return a + b
                if op == "-":
                    return a - b
                if op == "*":
                    return a * b
                if b == 0:
                    raise OutsideDomain
                return a / b
            case Call():
                return self._call(node)
        raise AssertionError(f"unknown node: {node!r}")

    def _power(self, node: Binary) -> mpf:
        base = self._eval(node.left)
        exponent = self._eval(node.right)
        if base == 0:
            if exponent <= 0:
                raise OutsideDomain  # 0^0 and 0^negative
            return mpf(0)
        if base > 0:
            return mp.power(base, exponent)

        # Negative base: only integer exponents and odd roots are real.
        exact = _exact_rational(node.right)
        if exact is None:
            if mpmath.isint(exponent):
                return mp.power(base, exponent)
            raise OutsideDomain
        if exact.denominator == 1:
            return mp.power(base, int(exact))
        if exact.denominator % 2 == 0:
            raise OutsideDomain
        magnitude = mp.power(-base, mpf(exact.numerator) / exact.denominator)
        return magnitude if exact.numerator % 2 == 0 else -magnitude

    def _call(self, node: Call) -> mpf:
        args = [self._eval(arg) for arg in node.args]
        x = args[0]
        match node.name:
            case "factorial" | "C" | "A":
                n, *rest = [_natural(arg) for arg in args]
                if node.name == "factorial":
                    return mp.factorial(n)
                (k,) = rest
                if k > n:
                    return mpf(0)
                return mp.binomial(n, k) if node.name == "C" else mp.ff(n, k)
            case "sqrt":
                if x < 0:
                    raise OutsideDomain
                return mp.sqrt(x)
            case "abs":
                return abs(x)
            case "sin":
                return mp.sin(x)
            case "cos":
                return mp.cos(x)
            case "tan":
                return mp.tan(x)
            case "sec" | "csc" | "cot":
                denominator = mp.cos(x) if node.name == "sec" else mp.sin(x)
                if denominator == 0:
                    raise OutsideDomain
                return (1 if node.name != "cot" else mp.cos(x)) / denominator
            case "asin" | "acos":
                if abs(x) > 1:
                    raise OutsideDomain
                return mp.asin(x) if node.name == "asin" else mp.acos(x)
            case "atan":
                return mp.atan(x)
            case "exp":
                return mp.exp(x)
            case "ln":
                if x <= 0:
                    raise OutsideDomain
                return mp.log(x)
            case "log":
                base = args[1] if len(args) == 2 else mpf(10)
                if x <= 0 or base <= 0 or base == 1:
                    raise OutsideDomain
                return mp.log(x, base)
        raise AssertionError(f"unknown function: {node.name}")


def _natural(value: mpf) -> mpf:
    """An argument of n!, C or A: 0.1·30 is 3 up to rounding, so it is rounded (ADR 0015)."""
    nearest = mpmath.nint(value)
    if nearest < 0 or abs(value - nearest) > mpf(10) ** (-(mp.dps // 2)):
        raise OutsideDomain
    return nearest


def _exact_rational(node: Node) -> Fraction | None:
    """Exact value of an exponent made only of numbers, such as 1/3 or -2/6."""
    match node:
        case Number(value=value):
            return Fraction(value)
        case Negate(operand=operand):
            inner = _exact_rational(operand)
            return None if inner is None else -inner
        case Binary(op=op, left=left, right=right):
            a, b = _exact_rational(left), _exact_rational(right)
            if a is None or b is None:
                return None
            if op == "+":
                return a + b
            if op == "-":
                return a - b
            if op == "*":
                return a * b
            if op == "/":
                return None if b == 0 else a / b
            if b.denominator == 1 and abs(b) <= 64 and not (a == 0 and b <= 0):
                return a ** int(b)
    return None

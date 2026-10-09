"""Critical points, local maxima and minima, and the vertex of a parabola (Phase 12, ADR 0021).

f'(x) = 0 is solved by the equation engine (``math_engine/equations.py``), so
the critical points are exact and, for polynomials and rational functions,
proved complete by Sturm. Each point is classified by the first derivative
test: the sign of f' just before and just after it (the neighbours are the
other critical points and the poles of f', so the sign cannot change in
between). That also classifies points where f'' = 0, like x = 0 in x⁴.

Out of scope, with an explanation: periodic critical points (sin(x)), points
where f' does not exist (|x| at 0) and functions of more than one variable.
"""

from dataclasses import dataclass
from typing import Literal

import mpmath
import sympy as sp
from mpmath import mp, mpf

from app.core.errors import ErrorCode, MathError
from app.core.notices import Notice, NoticeCode
from app.formatting.expressions import parser_text
from app.math_engine.equations import EquationOutcome, SolutionKind, solve_equation
from app.math_engine.inputs import require_expression
from app.models.intents import ExtremaParams, SolveEquationParams
from app.parsing import ParseResult, parse
from app.parsing.ast import Node, variables
from app.parsing.build import ExpressionBuilder, ensure_within_limits, symbol
from app.verification.numeric import BASE_PRECISION, decimal, to_mpf

type PointKind = Literal["max", "min", "none", "unknown"]

MAX_CRITICAL_POINTS = 20
# The test points sit at most this far from the critical point.
MAX_TEST_DISTANCE = mpf(1)
# Halvings of the test distance when f' does not exist there (near the edge of the domain).
DOMAIN_RETRIES = 30
# Notices of f'(x) = 0 that would only confuse: it is not the user's equation.
_EQUATION_ONLY = {NoticeCode.COMPLEX_SOLUTIONS_OMITTED, NoticeCode.INTERVAL_IGNORED}


@dataclass(frozen=True)
class CriticalPoint:
    x: sp.Expr
    y: sp.Expr  # f(x)
    kind: PointKind
    # Where f' was tested on each side (exact decimal strings), for the verification.
    left: str
    right: str


@dataclass(frozen=True)
class ExtremaOutcome:
    parsed: ParseResult
    tree: Node
    variable: sp.Symbol
    function: sp.Expr
    derivative: sp.Expr
    # f'(x) = 0, solved by the equation engine and verified like any equation;
    # None when f' is a nonzero constant (a line), which has no critical point.
    equation: EquationOutcome | None
    points: tuple[CriticalPoint, ...]  # increasing x
    # f is a polynomial of degree 2: its only critical point is the vertex.
    quadratic: bool
    notices: tuple[Notice, ...]


def extrema(params: ExtremaParams) -> ExtremaOutcome:
    parsed = parse(params.expression)
    tree = require_expression(parsed)
    name = _variable(tree, params.variable)
    var = symbol(name)
    builder = ExpressionBuilder()
    function = builder.build(tree)
    notices = [*parsed.notices, *builder.notices]

    derivative = sp.diff(function, var)
    ensure_within_limits(derivative)
    if derivative.has(sp.sign):
        raise MathError(
            ErrorCode.UNSUPPORTED_FEATURE,
            "A função tem módulo, e no ponto onde o módulo se anula ela não é derivável: lá "
            "pode haver um extremo que f'(x) = 0 não encontra. Extremos de funções com módulo "
            "ainda não são suportados.",
        )
    if sp.expand(derivative) == 0:
        raise MathError(
            ErrorCode.INVALID_INPUT_FOR_INTENT,
            "A função é constante: f'(x) = 0 em todo ponto, e não há máximo nem mínimo local "
            "estrito.",
        )

    if var not in derivative.free_symbols:  # a line: f' is a nonzero constant
        points: tuple[CriticalPoint, ...] = ()
        return ExtremaOutcome(
            parsed, tree, var, function, derivative, None, points, False, tuple(notices)
        )
    equation = _solve_critical(derivative, name)
    if equation.kind is SolutionKind.PERIODIC:
        raise MathError(
            ErrorCode.UNSUPPORTED_FEATURE,
            "Os pontos críticos desta função se repetem periodicamente (infinitos pontos); "
            "extremos de funções periódicas ainda não são suportados.",
        )
    if equation.kind is SolutionKind.ALL_REALS:
        raise MathError(
            ErrorCode.INVALID_INPUT_FOR_INTENT,
            "A derivada se anula em todo ponto: a função é constante, e não há máximo nem "
            "mínimo local estrito.",
        )
    if len(equation.solutions) > MAX_CRITICAL_POINTS:
        raise MathError(
            ErrorCode.LIMIT_EXCEEDED,
            f"A função tem mais de {MAX_CRITICAL_POINTS} pontos críticos.",
        )
    notices.extend(n for n in equation.notices if n.code not in _EQUATION_ONLY)
    if not function.is_rational_function(var):
        notices.append(
            Notice(
                NoticeCode.NOT_DIFFERENTIABLE_POINTS,
                "Só os pontos onde f'(x) = 0 foram considerados; pontos onde a derivada não "
                "existe, ou extremos nas bordas do domínio, não fazem parte da resposta.",
            )
        )

    points = _classify(function, derivative, var, equation)
    quadratic = function.is_polynomial(var) and sp.Poly(function, var).degree() == 2
    return ExtremaOutcome(
        parsed, tree, var, function, derivative, equation, points, quadratic, tuple(notices)
    )


def _variable(tree: Node, requested: str | None) -> str:
    names = variables(tree)
    if requested is not None:
        others = names - {requested}
        if others:
            raise MathError(
                ErrorCode.UNSUPPORTED_FEATURE,
                f"Extremos de funções com outras variáveis ({', '.join(sorted(others))}) ainda "
                "não são suportados.",
            )
        return requested
    if not names:
        raise MathError(
            ErrorCode.INVALID_INPUT_FOR_INTENT,
            "Escreva uma função com uma variável, como x^2 - 4x + 3: um número não tem extremos.",
        )
    if len(names) > 1:
        raise MathError(
            ErrorCode.UNSUPPORTED_FEATURE,
            f"A função tem mais de uma variável ({', '.join(sorted(names))}); extremos de "
            "funções de várias variáveis ainda não são suportados.",
        )
    return next(iter(names))


def _solve_critical(derivative: sp.Expr, name: str) -> EquationOutcome:
    """f'(x) = 0 by the equation engine, from text the safe parser reads back exactly."""
    try:
        text = f"{parser_text(derivative)} = 0"
        return solve_equation(SolveEquationParams(equation=text, variable=name))
    except (MathError, ValueError) as exc:
        detail = f" ({exc.message})" if isinstance(exc, MathError) else ""
        raise MathError(
            ErrorCode.UNSUPPORTED_FEATURE,
            f"Não foi possível resolver f'(x) = 0 para esta função{detail}.",
        ) from None


def _classify(
    function: sp.Expr, derivative: sp.Expr, var: sp.Symbol, equation: EquationOutcome
) -> tuple[CriticalPoint, ...]:
    """The first derivative test: the sign of f' on each side of each critical point."""
    with mp.workdps(BASE_PRECISION):
        positions = [mpf(decimal(x)) for x in equation.solutions]
        # The sign of f' can only change at a critical point or where f' does not exist.
        walls = sorted([*positions, *(mpf(decimal(x)) for x in equation.excluded)])

    points: list[CriticalPoint] = []
    for x, position in zip(equation.solutions, positions, strict=True):
        with mp.workdps(BASE_PRECISION):
            below = [w for w in walls if w < position]
            above = [w for w in walls if w > position]
            left = min(MAX_TEST_DISTANCE, (position - below[-1]) / 2 if below else 1)
            right = min(MAX_TEST_DISTANCE, (above[0] - position) / 2 if above else 1)
        left_sign, left_text = _side(derivative, var, position, -left)
        right_sign, right_text = _side(derivative, var, position, right)
        y = _value_at(function, var, x)
        points.append(CriticalPoint(x, y, _kind(left_sign, right_sign), left_text, right_text))
    return tuple(points)


def _side(derivative: sp.Expr, var: sp.Symbol, position: mpf, step: mpf) -> tuple[int | None, str]:
    """The sign of f' at ``position + step``; closer, if f' does not exist there (a domain edge)."""
    for _ in range(DOMAIN_RETRIES):
        with mp.workdps(BASE_PRECISION):
            at = mpmath.nstr(position + step, BASE_PRECISION, strip_zeros=False)
        sign = _sign(derivative, var, at)
        if sign is not None:
            return sign, at
        step /= 2
    return None, at


def _value_at(function: sp.Expr, var: sp.Symbol, x: sp.Expr) -> sp.Expr:
    value = function.subs(var, x)
    # radsimp rationalizes denominators; on CRootOf it could take minutes.
    value = sp.expand(value) if value.has(sp.CRootOf) else sp.radsimp(sp.expand(value))
    ensure_within_limits(value)
    return value


def _sign(derivative: sp.Expr, var: sp.Symbol, at: str) -> int | None:
    value = to_mpf(derivative, {var: at})
    if value is None or value == 0:
        return None
    return 1 if value > 0 else -1


def _kind(left: int | None, right: int | None) -> PointKind:
    if left is None or right is None:
        return "unknown"
    if left > 0 > right:
        return "max"
    if left < 0 < right:
        return "min"
    return "none"

"""Derivatives, integrals and limits (Phase 6).

Conventions for the real domain (ADR 0005), which SymPy does not apply by
itself:

- an antiderivative with ``log(u)`` becomes ``log(|u|)``: SymPy gives
  ∫1/x dx = log(x), valid only for x > 0, while ln|x| is valid on the whole
  domain of 1/x (d/dx ln|u| = u'/u for every u ≠ 0);
- a limit is taken over the points where the function is real. SymPy computes
  lim √x (x → 0) from the left with complex numbers; here only the right side
  exists, and the result says so.
"""

from dataclasses import dataclass
from enum import StrEnum
from typing import Literal

import sympy as sp

from app.core.errors import ErrorCode, MathError
from app.core.notices import Notice, NoticeCode
from app.formatting.expressions import plain
from app.math_engine.inputs import require_expression
from app.models.intents import DerivativeParams, IntegralParams, LimitParams
from app.parsing import ParseResult, parse
from app.parsing.ast import Node, variables
from app.parsing.build import ExpressionBuilder, ensure_within_limits, symbol

type Side = Literal["both", "left", "right"]

_PLUS_INFINITY = {"inf", "+inf", "∞", "+∞", "oo", "+oo", "infinito", "+infinito"}
_MINUS_INFINITY = {"-inf", "-∞", "-oo", "-infinito"}
_SIDE_WORDS = {"left": "esquerda", "right": "direita"}


# -- shared helpers ------------------------------------------------------------------------


def _resolve_variable(tree: Node, requested: str | None) -> str:
    if requested is not None:
        return requested
    names = variables(tree)
    if len(names) > 1:
        raise MathError(
            ErrorCode.AMBIGUOUS_INPUT,
            f"A expressão tem mais de uma variável ({', '.join(sorted(names))}); "
            "informe em relação a qual.",
        )
    return next(iter(names), "x")


def _only_variable(tree: Node, name: str, what: str) -> None:
    others = variables(tree) - {name}
    if others:
        raise MathError(
            ErrorCode.UNSUPPORTED_FEATURE,
            f"{what} com outras variáveis ({', '.join(sorted(others))}) ainda não são suportados.",
        )


def parse_value(text: str, label: str) -> tuple[sp.Expr, tuple[Notice, ...]]:
    """A bound or a limit point: a number, an expression like pi/2, or ±infinity."""
    word = text.strip().lower().replace(" ", "")
    if word in _PLUS_INFINITY:
        return sp.oo, ()
    if word in _MINUS_INFINITY:
        return -sp.oo, ()
    try:
        parsed = parse(text)
        tree = require_expression(parsed)
        if variables(tree):
            raise MathError(ErrorCode.INVALID_INPUT_FOR_INTENT, "não pode ter variáveis.")
        builder = ExpressionBuilder()
        value = builder.build(tree)
    except MathError as exc:
        # The position would point into this field, not into the main input.
        raise MathError(exc.code, f"No {label}: {exc.message}") from None
    if not value.is_extended_real or value.has(sp.I):
        raise MathError(ErrorCode.DOMAIN_ERROR, f"O {label} precisa ser um número real.")
    return value, parsed.notices + tuple(builder.notices)


def _prepare(
    text: str, requested: str | None
) -> tuple[ParseResult, Node, sp.Symbol, sp.Expr, list[Notice]]:
    parsed = parse(text)
    tree = require_expression(parsed)
    var = symbol(_resolve_variable(tree, requested))
    builder = ExpressionBuilder()
    expr = builder.build(tree)
    return parsed, tree, var, expr, list(parsed.notices) + builder.notices


def show_value(value: sp.Expr) -> str:
    if value == sp.oo:
        return "∞"
    if value == -sp.oo:
        return "-∞"
    return plain(value)


# -- derivative --------------------------------------------------------------------------------


@dataclass(frozen=True)
class DerivativeOutcome:
    parsed: ParseResult
    tree: Node
    variable: sp.Symbol
    order: int
    function: sp.Expr
    result: sp.Expr
    notices: tuple[Notice, ...]


def derivative(params: DerivativeParams) -> DerivativeOutcome:
    parsed, tree, var, function, notices = _prepare(params.expression, params.variable)
    result = sp.diff(function, var, params.order)
    ensure_within_limits(result)
    if result.has(sp.sign):
        notices.append(
            Notice(
                NoticeCode.NOT_DIFFERENTIABLE_POINTS,
                "A derivada usa sign(u), que vale 0 onde u = 0; nesses pontos a função "
                "original (com módulo) não é derivável.",
            )
        )
    return DerivativeOutcome(parsed, tree, var, params.order, function, result, tuple(notices))


# -- integral ----------------------------------------------------------------------------------


@dataclass(frozen=True)
class IntegralOutcome:
    parsed: ParseResult
    tree: Node
    variable: sp.Symbol
    integrand: sp.Expr
    # Indefinite: the antiderivative shown (with ln|u|) and SymPy's own.
    antiderivative: sp.Expr | None
    raw_antiderivative: sp.Expr | None
    # Definite: the bounds (possibly ±oo) and the value (±oo when divergent).
    lower: sp.Expr | None
    upper: sp.Expr | None
    value: sp.Expr | None
    notices: tuple[Notice, ...]

    @property
    def definite(self) -> bool:
        return self.lower is not None

    @property
    def converges(self) -> bool:
        return self.value is not None and self.value not in (sp.oo, -sp.oo)


def integral(params: IntegralParams) -> IntegralOutcome:
    parsed, tree, var, integrand, notices = _prepare(params.expression, params.variable)

    if params.lower is None or params.upper is None:
        raw = sp.integrate(integrand, var)
        if raw.has(sp.Integral):
            raise MathError(
                ErrorCode.UNSUPPORTED_FEATURE,
                "Não foi encontrada uma primitiva em forma fechada para esta função.",
            )
        antiderivative = raw.replace(sp.log, lambda u: sp.log(sp.Abs(u)))
        if antiderivative != raw:
            notices.append(
                Notice(
                    NoticeCode.ABSOLUTE_VALUE_IN_LOG,
                    "No domínio real, ln(u) foi escrito como ln|u|: assim a primitiva vale "
                    "também onde u < 0 (a derivada de ln|u| é u'/u).",
                )
            )
        ensure_within_limits(antiderivative)
        return IntegralOutcome(
            parsed, tree, var, integrand, antiderivative, raw, None, None, None, tuple(notices)
        )

    _only_variable(tree, var.name, "Integrais definidas")
    lower, lower_notices = parse_value(params.lower, "limite inferior")
    upper, upper_notices = parse_value(params.upper, "limite superior")
    notices += [*lower_notices, *upper_notices]

    value = sp.integrate(integrand, (var, lower, upper))
    if value.has(sp.Integral):
        raise MathError(
            ErrorCode.UNSUPPORTED_FEATURE, "Não foi possível calcular esta integral de forma exata."
        )
    if value.has(sp.nan, sp.zoo, sp.AccumBounds):
        raise MathError(
            ErrorCode.DOMAIN_ERROR,
            "A integral não converge nesse intervalo (a função oscila ou tem uma singularidade "
            "não integrável).",
        )
    if value not in (sp.oo, -sp.oo):
        if value.has(sp.I) or value.is_extended_real is False:
            raise MathError(
                ErrorCode.DOMAIN_ERROR,
                "A função não é real em todo o intervalo de integração (o domínio é ℝ).",
            )
        ensure_within_limits(value)
    return IntegralOutcome(
        parsed, tree, var, integrand, None, None, lower, upper, value, tuple(notices)
    )


# -- limit --------------------------------------------------------------------------------------


class LimitKind(StrEnum):
    FINITE = "finite"
    INFINITE = "infinite"
    NONEXISTENT = "nonexistent"


@dataclass(frozen=True)
class LimitOutcome:
    parsed: ParseResult
    tree: Node
    variable: sp.Symbol
    point: sp.Expr  # a real number or ±oo
    requested_side: Side
    side: Side  # the side actually used (one side when the other is outside ℝ)
    kind: LimitKind
    value: sp.Expr | None  # the limit, finite or ±oo
    left: sp.Expr | None  # one-sided limits, when they differ
    right: sp.Expr | None
    oscillates: bool
    notices: tuple[Notice, ...]


def limit(params: LimitParams) -> LimitOutcome:
    parsed, tree, var, function, notices = _prepare(params.expression, params.variable)
    _only_variable(tree, var.name, "Limites")
    point, point_notices = parse_value(params.point, "ponto")
    notices += point_notices

    def finish(
        kind: LimitKind,
        side: Side,
        value: sp.Expr | None = None,
        left: sp.Expr | None = None,
        right: sp.Expr | None = None,
        oscillates: bool = False,
    ) -> LimitOutcome:
        return LimitOutcome(
            parsed,
            tree,
            var,
            point,
            params.side,
            side,
            kind,
            value,
            left,
            right,
            oscillates,
            tuple(notices),
        )

    if point in (sp.oo, -sp.oo):
        direction: Side = "left" if point == sp.oo else "right"
        if not _side_in_domain(function, var, point, direction):
            extreme = "grandes" if point == sp.oo else "negativos"
            raise MathError(
                ErrorCode.DOMAIN_ERROR,
                f"A função não é real para valores muito {extreme} de {var.name} (o domínio é ℝ).",
            )
        kind, value, oscillates = _classify(sp.limit(function, var, point))
        return finish(kind, params.side, value, oscillates=oscillates)

    wanted: list[Side] = ["left", "right"] if params.side == "both" else [params.side]
    available = [s for s in wanted if _side_in_domain(function, var, point, s)]
    shown_point = plain(point)
    if not available:
        where = "perto de" if params.side == "both" else f"à {_SIDE_WORDS[params.side]} de"
        raise MathError(
            ErrorCode.DOMAIN_ERROR,
            f"A função não é real {where} {var.name} = {shown_point} (o domínio é ℝ).",
        )
    if len(available) < len(wanted):
        only = available[0]
        notices.append(
            Notice(
                NoticeCode.ONE_SIDED_DOMAIN,
                f"No domínio real, a função só existe à {_SIDE_WORDS[only]} de "
                f"{var.name} = {shown_point}; o limite é o lateral por esse lado.",
            )
        )

    if len(available) == 1:
        side = available[0]
        kind, value, oscillates = _classify(_one_sided(function, var, point, side))
        return finish(kind, side, value, oscillates=oscillates)

    left_kind, left, left_osc = _classify(_one_sided(function, var, point, "left"))
    _, right, right_osc = _classify(_one_sided(function, var, point, "right"))
    if left_osc or right_osc:
        return finish(LimitKind.NONEXISTENT, "both", oscillates=True)
    if left == right and left is not None:
        return finish(left_kind, "both", left)
    return finish(LimitKind.NONEXISTENT, "both", left=left, right=right)


def _one_sided(function: sp.Expr, var: sp.Symbol, point: sp.Expr, side: Side) -> sp.Expr:
    return sp.limit(function, var, point, dir="-" if side == "left" else "+")


def _classify(value: sp.Expr) -> tuple[LimitKind, sp.Expr | None, bool]:
    """(kind, value, oscillates) of a limit computed by SymPy."""
    if value.has(sp.Limit):
        raise MathError(
            ErrorCode.UNSUPPORTED_FEATURE, "Não foi possível calcular este limite de forma exata."
        )
    if isinstance(value, sp.AccumBounds):
        return LimitKind.NONEXISTENT, None, True
    if value in (sp.oo, -sp.oo):
        return LimitKind.INFINITE, value, False
    if value.has(sp.zoo, sp.nan):
        return LimitKind.NONEXISTENT, None, False
    if value.has(sp.I) or value.is_extended_real is False:
        raise MathError(ErrorCode.DOMAIN_ERROR, "O limite não é um número real (o domínio é ℝ).")
    return LimitKind.FINITE, value, False


def _side_in_domain(function: sp.Expr, var: sp.Symbol, point: sp.Expr, side: Side) -> bool:
    """Is the function real just to this side of the point? (Probed at three points.)"""
    if point == sp.oo:
        probes = [sp.Integer(10) ** k for k in (4, 8, 12)]
    elif point == -sp.oo:
        probes = [-(sp.Integer(10) ** k) for k in (4, 8, 12)]
    else:
        sign = -1 if side == "left" else 1
        probes = [point + sign * sp.Rational(1, 10**k) for k in (4, 8, 12)]
    real = 0
    for probe in probes:
        # Floating point on purpose: substituting the exact 10^12 into (1 + 1/x)^x
        # would make SymPy build a rational with trillions of digits.
        value = function.evalf(30, subs={var: sp.N(probe, 40)})
        if value.is_Number and value.is_extended_real and value.is_finite:
            real += 1
    return real >= 2

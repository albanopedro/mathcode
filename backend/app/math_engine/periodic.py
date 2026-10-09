"""Infinitely many periodic solutions, as in sin(x) = 1/2 (Phase 10, ADR 0016).

``solveset`` describes them as images of the integers, such as
``ImageSet(Lambda(n, 2nπ + π/6), Integers)``. Here each image becomes a
``Family`` (offset + k·period, with the offset in [0, period)); families that
together form a shorter period are merged (2kπ and π + 2kπ are kπ), and the
solutions inside an interval are listed.
"""

import math
from dataclasses import dataclass

import sympy as sp

from app.formatting.expressions import plain

# Families in one answer, and solutions listed in an interval.
MAX_FAMILIES = 24
MAX_LISTED = 100

_TOLERANCE = sp.Float("1e-40")


@dataclass(frozen=True)
class Family:
    """offset + k·period for every integer k; offset in [0, period), period > 0."""

    offset: sp.Expr
    period: sp.Expr

    def at(self, k: int) -> sp.Expr:
        return self.offset + k * self.period


@dataclass(frozen=True)
class Interval:
    """Where the solutions are listed: [lower, upper] or, with ``closed`` False, [lower, upper)."""

    lower: sp.Expr
    upper: sp.Expr
    closed: bool
    given: bool  # typed by the user; otherwise the default [0, 2π)


DEFAULT_INTERVAL = Interval(sp.Integer(0), 2 * sp.pi, closed=False, given=False)


def describe(family: Family, k: sp.Symbol) -> str:
    """'pi/6 + 2*pi*k': the family in the syntax of the input."""
    term = plain(family.period * k)
    return term if family.offset == 0 else f"{plain(family.offset)} + {term}"


def same(a: sp.Expr, b: sp.Expr) -> bool:
    """Equal numbers, compared with 50 digits (both are exact closed forms)."""
    return bool(abs(sp.N(a - b, 50)) < _TOLERANCE)


def normalize(offset: sp.Expr, period: sp.Expr) -> sp.Expr:
    """The representative of offset + k·period in [0, period)."""
    turns = sp.floor(sp.N(offset / period, 50))
    shifted = offset - int(turns) * period
    if same(shifted, period):  # rounding at the edge: offset is a multiple of the period
        shifted -= period
    return shifted


def families_of(result: sp.Set) -> tuple[list[Family], list[sp.Expr]] | None:
    """The families and the isolated solutions of a ``solveset`` result, or None.

    None when the result has another shape (a ConditionSet, an image that is not
    linear in the integer...): the equation is then not solved here.
    """
    parts = result.args if isinstance(result, sp.Union) else (result,)
    families: list[Family] = []
    isolated: list[sp.Expr] = []
    for part in parts:
        if isinstance(part, sp.ImageSet):
            family = _family(part)
            if family is None:
                return None
            families.append(family)
        elif isinstance(part, sp.FiniteSet) and all(_real_number(v) for v in part):
            isolated.extend(part)
        else:
            return None
    if not families or len(families) > MAX_FAMILIES:
        return None
    merged = merge(families)
    alone = [value for value in isolated if not any(contains(f, value) for f in merged)]
    return merged, sorted(set(alone), key=lambda v: float(sp.N(v, 30)))


def _real_number(value: sp.Expr) -> bool:
    return bool(value.is_number and value.is_extended_real)


def _family(image: sp.ImageSet) -> Family | None:
    if tuple(image.base_sets) != (sp.S.Integers,):
        return None
    (n,) = image.lamda.variables
    expr = sp.expand(image.lamda.expr)
    try:
        poly = sp.Poly(expr, n)
    except sp.PolynomialError:
        return None
    if poly.degree() != 1:
        return None
    period = poly.coeff_monomial(n)
    offset = expr.subs(n, 0)
    if not (_real_number(period) and _real_number(offset)) or period.is_zero:
        return None
    period = abs(period)
    return Family(normalize(offset, period), period)


def contains(family: Family, value: sp.Expr) -> bool:
    """Whether ``value`` is offset + k·period for some integer k."""
    k = sp.N((value - family.offset) / family.period, 50)
    return bool(abs(k - round(k)) < _TOLERANCE)


def merge(families: list[Family]) -> list[Family]:
    """Joins families that form a shorter period, then sorts them by offset."""
    current = _unique(families)
    while (merged := _merge_once(current)) is not None:
        current = merged
    return sorted(current, key=lambda f: (float(sp.N(f.period, 30)), float(sp.N(f.offset, 30))))


def _unique(families: list[Family]) -> list[Family]:
    unique: list[Family] = []
    for family in families:
        if not any(same(f.period, family.period) and same(f.offset, family.offset) for f in unique):
            unique.append(family)
    return unique


def _merge_once(families: list[Family]) -> list[Family] | None:
    """2kπ, π/2 + 2kπ, π + 2kπ and 3π/2 + 2kπ are kπ/2: m equally spaced offsets."""
    for family in families:
        group = [f for f in families if same(f.period, family.period)]
        for m in range(len(group), 1, -1):
            step = family.period / m
            members: list[Family] = []
            for j in range(m):
                target = normalize(family.offset + j * step, family.period)
                match = next((f for f in group if same(f.offset, target)), None)
                if match is None:
                    break
                members.append(match)
            else:
                rest = [f for f in families if f not in members]
                return _unique([*rest, Family(normalize(family.offset, step), step)])
    return None


def listed(
    families: list[Family], isolated: list[sp.Expr], interval: Interval
) -> tuple[list[sp.Expr], int]:
    """The solutions inside the interval, in increasing order (at most ``MAX_LISTED``),
    and how many there are in all."""
    found: list[sp.Expr] = []
    total = 0
    for family in families:
        first = int(sp.ceiling(sp.N((interval.lower - family.offset) / family.period, 50)))
        last = int(sp.floor(sp.N((interval.upper - family.offset) / family.period, 50)))
        # Rounding at the edges: the bounds are checked again below.
        for k in range(first - 1, min(last + 1, first - 1 + MAX_LISTED + 2) + 1):
            value = family.at(k)
            if _inside(value, interval):
                found.append(value)
        total += max(0, _count(family, interval))
    for value in isolated:
        if _inside(value, interval) and not any(same(value, v) for v in found):
            found.append(value)
            total += 1
    found.sort(key=lambda v: float(sp.N(v, 30)))
    return found[:MAX_LISTED], total


def _inside(value: sp.Expr, interval: Interval) -> bool:
    if sp.N(value - interval.lower, 50) < -_TOLERANCE:
        return False
    above = sp.N(value - interval.upper, 50)
    if interval.closed:
        return bool(above <= _TOLERANCE)
    return bool(above < -_TOLERANCE)


def _count(family: Family, interval: Interval) -> int:
    first = math.ceil(float(sp.N((interval.lower - family.offset) / family.period, 50)) - 1e-12)
    last = math.floor(float(sp.N((interval.upper - family.offset) / family.period, 50)) + 1e-12)
    count = last - first + 1
    if not interval.closed and same(family.at(last), interval.upper):
        count -= 1
    return count

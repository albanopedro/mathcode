"""Equations in one variable (Phase 5): polynomial, rational and others.

How the equation is solved depends on its shape (``polynomials.shape``):

- polynomial: exact real roots with multiplicity (``real_roots``);
- rational: real roots of the numerator, minus the zeros of the denominators;
- other (roots, logs, exponentials...): SymPy's ``solveset`` over ℝ, whose
  completeness cannot be proved here, so verification says "partial".

Trigonometric equations have infinitely many solutions in periodic families
(``math_engine/periodic.py``, ADR 0016): the answer is the general solution,
plus the solutions inside an interval, [0, 2π) unless one is given.
"""

from collections.abc import Iterable
from dataclasses import dataclass, replace
from enum import StrEnum

import sympy as sp

from app.core.errors import ErrorCode, MathError
from app.core.notices import Notice, NoticeCode
from app.math_engine.calculus import parse_value
from app.math_engine.inputs import require_equation
from app.math_engine.periodic import (
    DEFAULT_INTERVAL,
    MAX_LISTED,
    Family,
    Interval,
    families_of,
    listed,
)
from app.math_engine.polynomials import (
    Shape,
    has_rational_coefficients,
    real_roots_with_multiplicity,
    shape,
)
from app.models.intents import SolveEquationParams
from app.parsing import ParseResult, parse
from app.parsing.ast import Equation, variables
from app.parsing.build import ExpressionBuilder, symbol


class SolutionKind(StrEnum):
    FINITE = "finite"
    NONE = "none"
    ALL_REALS = "all_reals"
    PERIODIC = "periodic"  # families offset + k·period (ADR 0016)


@dataclass(frozen=True)
class EquationOutcome:
    parsed: ParseResult
    equation: Equation
    variable: sp.Symbol
    left: sp.Expr
    right: sp.Expr
    shape: Shape
    kind: SolutionKind
    solutions: tuple[sp.Expr, ...]  # distinct, increasing
    multiplicities: tuple[int, ...]  # parallel to solutions; empty when unknown
    excluded: tuple[sp.Expr, ...]  # outside the domain: zeros of denominators
    rejected: tuple[sp.Expr, ...]  # roots of the numerator that are excluded
    # Polynomial whose real roots are all the candidates, when it has rational
    # coefficients: verification counts its roots independently (Sturm).
    candidates: sp.Poly | None
    notices: tuple[Notice, ...]
    # Periodic solutions: the general solution is ``families`` plus ``isolated``;
    # ``solutions`` are then the ones inside ``interval`` (``listed_total`` in all).
    families: tuple[Family, ...] = ()
    isolated: tuple[sp.Expr, ...] = ()
    interval: Interval | None = None
    listed_total: int = 0
    rejected_families: tuple[Family, ...] = ()  # outside the domain of the equation


def solve_equation(params: SolveEquationParams) -> EquationOutcome:
    parsed = parse(params.equation)
    equation = require_equation(parsed)
    name = _single_variable(equation, params.variable)
    var = symbol(name)

    builder = ExpressionBuilder()
    left = builder.build(equation.left)
    right = builder.build(equation.right)
    found, _ = shape(equation, name)

    solver = _Solver(parsed, equation, var, left, right, found, builder)
    solver.interval = _interval(params, solver.notices)
    match found:
        case Shape.POLYNOMIAL:
            outcome = solver.polynomial()
        case Shape.RATIONAL:
            outcome = solver.rational()
        case Shape.OTHER:
            outcome = solver.general()
    if solver.interval is not None and outcome.kind is not SolutionKind.PERIODIC:
        ignored = Notice(
            NoticeCode.INTERVAL_IGNORED,
            "O intervalo vale para equações com infinitas soluções periódicas; esta não "
            "tem, e todas as soluções aparecem.",
        )
        outcome = replace(outcome, notices=(*outcome.notices, ignored))
    return outcome


def _interval(params: SolveEquationParams, notices: list[Notice]) -> Interval | None:
    """The interval typed by the user, if any; checked only when the solutions are periodic."""
    if params.lower is None or params.upper is None:
        return None
    lower, lower_notices = parse_value(params.lower, "início do intervalo")
    upper, upper_notices = parse_value(params.upper, "fim do intervalo")
    notices.extend((*lower_notices, *upper_notices))
    if not (lower.is_finite and upper.is_finite):
        raise MathError(
            ErrorCode.INVALID_INPUT_FOR_INTENT,
            "O intervalo das soluções precisa ser limitado, como de 0 a 2pi.",
        )
    if (upper - lower).is_positive is not True:
        raise MathError(
            ErrorCode.INVALID_INPUT_FOR_INTENT,
            "O fim do intervalo precisa ser maior que o início.",
        )
    return Interval(lower, upper, closed=True, given=True)


def _single_variable(equation: Equation, requested: str | None) -> str:
    names = variables(equation)
    if not names:
        raise MathError(
            ErrorCode.INVALID_INPUT_FOR_INTENT, "A equação não tem variável para resolver."
        )
    if requested is not None and requested not in names:
        raise MathError(
            ErrorCode.INVALID_INPUT_FOR_INTENT,
            f"A variável '{requested}' não aparece na equação.",
        )
    if len(names) > 1:
        raise MathError(
            ErrorCode.UNSUPPORTED_FEATURE,
            f"A equação tem mais de uma variável ({', '.join(sorted(names))}). "
            "Para um sistema, separe as equações com ';'.",
        )
    (name,) = names
    return name


class _Solver:
    def __init__(
        self,
        parsed: ParseResult,
        equation: Equation,
        var: sp.Symbol,
        left: sp.Expr,
        right: sp.Expr,
        found: Shape,
        builder: ExpressionBuilder,
    ) -> None:
        self.parsed = parsed
        self.equation = equation
        self.var = var
        self.left = left
        self.right = right
        self.shape = found
        self.denominators = [d for d in builder.denominators if var in d.free_symbols]
        self.notices = list(parsed.notices) + builder.notices
        self.interval: Interval | None = None

    # -- the three shapes -------------------------------------------------------

    def polynomial(self) -> EquationOutcome:
        poly = sp.Poly(sp.expand(self.left - self.right), self.var)
        if poly.is_zero:
            return self._outcome(SolutionKind.ALL_REALS)
        if poly.degree() == 0:
            return self._outcome(SolutionKind.NONE)

        if not has_rational_coefficients(poly):
            return self._finite(self._solveset(poly.as_expr()), multiplicities=())

        roots = real_roots_with_multiplicity(poly)
        real_count = sum(multiplicity for _, multiplicity in roots)
        if real_count < poly.degree():
            missing = poly.degree() - real_count
            self.notices.append(
                Notice(
                    NoticeCode.COMPLEX_SOLUTIONS_OMITTED,
                    f"A equação também tem {missing} solução(ões) complexa(s), "
                    "omitida(s) porque o domínio é ℝ.",
                )
            )
        return self._finite(
            [root for root, _ in roots],
            multiplicities=tuple(multiplicity for _, multiplicity in roots),
            candidates=poly,
        )

    def rational(self) -> EquationOutcome:
        numerator, _ = sp.fraction(sp.together(self.left - self.right))
        poly = sp.Poly(sp.expand(numerator), self.var)
        excluded = self._denominator_zeros()
        if poly.is_zero:
            return self._outcome(SolutionKind.ALL_REALS, excluded=excluded)
        if poly.degree() == 0:
            return self._outcome(SolutionKind.NONE, excluded=excluded)

        if has_rational_coefficients(poly):
            roots = [root for root, _ in real_roots_with_multiplicity(poly)]
            candidates: sp.Poly | None = poly
        else:
            roots = self._solveset(poly.as_expr())
            candidates = None
        rejected = [root for root in roots if self._is_excluded(root)]
        kept = [root for root in roots if root not in rejected]
        return self._finite(
            kept, multiplicities=(), candidates=candidates, excluded=excluded, rejected=rejected
        )

    def general(self) -> EquationOutcome:
        result = sp.solveset(self.left - self.right, self.var, domain=sp.S.Reals)
        if result == sp.S.Reals:
            return self._outcome(SolutionKind.ALL_REALS)
        if result is sp.S.EmptySet:
            return self._outcome(SolutionKind.NONE)
        if isinstance(result, sp.FiniteSet) and all(_is_real_number(r) for r in result):
            return self._finite(_sorted(result), multiplicities=())
        periodic = families_of(result) if result.has(sp.ImageSet) else None
        if periodic is None:
            raise MathError(
                ErrorCode.UNSUPPORTED_FEATURE,
                "Não foi possível resolver esta equação de forma exata.",
            )
        return self._periodic(*periodic)

    def _periodic(self, families: list[Family], isolated: list[sp.Expr]) -> EquationOutcome:
        # solveset may simplify the domain away: cos(x)·tan(x) = 1 "has" x = π/2 + 2kπ,
        # where tan is not defined. Such families are discarded.
        kept = [f for f in families if not any(self._undefined(f.at(k)) for k in (0, 1))]
        rejected = tuple(f for f in families if f not in kept)
        isolated = [value for value in isolated if not self._undefined(value)]
        if not kept:
            outcome = self._finite(isolated, multiplicities=())
            return replace(outcome, rejected_families=rejected)
        interval = self.interval or DEFAULT_INTERVAL
        solutions, total = listed(kept, isolated, interval)
        if total > MAX_LISTED:
            self.notices.append(
                Notice(
                    NoticeCode.SOLUTIONS_TRUNCATED,
                    f"Há {total} soluções no intervalo; aparecem as {MAX_LISTED} primeiras.",
                )
            )
        return replace(
            self._outcome(SolutionKind.PERIODIC, solutions=tuple(solutions)),
            families=tuple(kept),
            isolated=tuple(isolated),
            interval=interval,
            listed_total=total,
            rejected_families=rejected,
        )

    def _undefined(self, value: sp.Expr) -> bool:
        if self._is_excluded(value):
            return True
        for side in (self.left, self.right):
            at = side.subs(self.var, value)
            if at.has(sp.zoo, sp.nan, sp.oo, -sp.oo) or at.is_extended_real is False:
                return True
        return False

    # -- helpers ----------------------------------------------------------------------

    def _finite(
        self,
        solutions: list[sp.Expr],
        *,
        multiplicities: tuple[int, ...],
        candidates: sp.Poly | None = None,
        excluded: tuple[sp.Expr, ...] = (),
        rejected: list[sp.Expr] | None = None,
    ) -> EquationOutcome:
        if not solutions:
            return self._outcome(
                SolutionKind.NONE,
                candidates=candidates,
                excluded=excluded,
                rejected=tuple(rejected or ()),
            )
        if any(isinstance(s, sp.CRootOf) for s in solutions):
            self.notices.append(
                Notice(
                    NoticeCode.ROOTS_SHOWN_APPROXIMATELY,
                    "Algumas raízes não têm forma exata simples com radicais reais: aparecem "
                    "aproximadas, mas foram calculadas e verificadas de forma exata.",
                )
            )
        return self._outcome(
            SolutionKind.FINITE,
            solutions=tuple(solutions),
            multiplicities=multiplicities,
            candidates=candidates,
            excluded=excluded,
            rejected=tuple(rejected or ()),
        )

    def _outcome(
        self,
        kind: SolutionKind,
        *,
        solutions: tuple[sp.Expr, ...] = (),
        multiplicities: tuple[int, ...] = (),
        candidates: sp.Poly | None = None,
        excluded: tuple[sp.Expr, ...] = (),
        rejected: tuple[sp.Expr, ...] = (),
    ) -> EquationOutcome:
        return EquationOutcome(
            parsed=self.parsed,
            equation=self.equation,
            variable=self.var,
            left=self.left,
            right=self.right,
            shape=self.shape,
            kind=kind,
            solutions=solutions,
            multiplicities=multiplicities,
            excluded=excluded,
            rejected=rejected,
            candidates=candidates,
            notices=tuple(self.notices),
        )

    def _solveset(self, expr: sp.Expr) -> list[sp.Expr]:
        result = sp.solveset(expr, self.var, domain=sp.S.Reals)
        if result is sp.S.EmptySet:
            return []
        if isinstance(result, sp.FiniteSet) and all(_is_real_number(r) for r in result):
            return _sorted(result)
        raise MathError(
            ErrorCode.UNSUPPORTED_FEATURE, "Não foi possível resolver esta equação de forma exata."
        )

    def _denominator_zeros(self) -> tuple[sp.Expr, ...]:
        zeros: set[sp.Expr] = set()
        for denominator in self.denominators:
            zeros.update(self._solveset(denominator))
        return tuple(_sorted(zeros))

    def _is_excluded(self, root: sp.Expr) -> bool:
        return any(_vanishes(d.subs(self.var, root)) for d in self.denominators)


def _vanishes(expr: sp.Expr) -> bool:
    if sp.simplify(expr) == 0:
        return True
    return bool(abs(sp.N(expr, 60)) < sp.Float("1e-50"))


def _is_real_number(value: sp.Expr) -> bool:
    if not value.is_number:
        return False
    if value.is_real is not None:
        return bool(value.is_real)
    return bool(abs(sp.im(sp.N(value, 50))) < sp.Float("1e-40"))


def _sorted(values: Iterable[sp.Expr]) -> list[sp.Expr]:
    return sorted(values, key=lambda value: float(sp.N(value, 30)))

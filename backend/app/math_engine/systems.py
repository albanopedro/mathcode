"""Linear systems (Phase 5). Nonlinear systems are a registered suggestion."""

from dataclasses import dataclass
from enum import StrEnum

import sympy as sp

from app.core.errors import ErrorCode, MathError
from app.core.limits import MAX_SYSTEM_EQUATIONS
from app.core.notices import Notice
from app.math_engine.inputs import require_system
from app.math_engine.polynomials import Shape, shape
from app.models.intents import SolveSystemParams
from app.parsing import ParseResult, parse
from app.parsing.ast import System, variables
from app.parsing.build import ExpressionBuilder, symbol


class SystemKind(StrEnum):
    UNIQUE = "unique"
    INFINITE = "infinite"
    NONE = "none"


@dataclass(frozen=True)
class SystemOutcome:
    parsed: ParseResult
    system: System
    variables: tuple[sp.Symbol, ...]
    differences: tuple[sp.Expr, ...]  # left - right of each equation, expanded
    kind: SystemKind
    # Value of each variable, in the order of ``variables``. In an infinite
    # solution set, it is written in terms of the free variables.
    solution: tuple[sp.Expr, ...] | None
    free: tuple[sp.Symbol, ...]
    notices: tuple[Notice, ...]


def solve_system(params: SolveSystemParams) -> SystemOutcome:
    parsed = parse(params.system)
    system = require_system(parsed)
    names = sorted(variables(system))
    if not names:
        raise MathError(ErrorCode.INVALID_INPUT_FOR_INTENT, "O sistema não tem variáveis.")
    if len(names) > MAX_SYSTEM_EQUATIONS:
        raise MathError(
            ErrorCode.LIMIT_EXCEEDED,
            f"O sistema tem mais de {MAX_SYSTEM_EQUATIONS} variáveis.",
        )
    for equation in system.equations:
        for name in names:
            found, reason = shape(equation, name)
            if found is not Shape.POLYNOMIAL:
                raise _not_linear(reason or "")

    builder = ExpressionBuilder()
    unknowns = tuple(symbol(name) for name in names)
    differences = tuple(
        sp.expand(builder.build(eq.left) - builder.build(eq.right)) for eq in system.equations
    )
    for difference in differences:
        if difference != 0 and sp.Poly(difference, *unknowns).total_degree() > 1:
            raise _not_linear("há termos de grau 2 ou maior, como x*y ou x^2")

    result = sp.linsolve(list(differences), list(unknowns))
    notices = parsed.notices + tuple(builder.notices)
    if result is sp.S.EmptySet:
        return SystemOutcome(
            parsed, system, unknowns, differences, SystemKind.NONE, None, (), notices
        )

    (solution,) = result
    used = set().union(*(value.free_symbols for value in solution))
    free = tuple(var for var in unknowns if var in used)
    kind = SystemKind.INFINITE if free else SystemKind.UNIQUE
    return SystemOutcome(
        parsed, system, unknowns, differences, kind, tuple(solution), free, notices
    )


def _not_linear(reason: str) -> MathError:
    return MathError(
        ErrorCode.UNSUPPORTED_FEATURE,
        f"Por enquanto só sistemas lineares são resolvidos, e aqui {reason}.",
    )

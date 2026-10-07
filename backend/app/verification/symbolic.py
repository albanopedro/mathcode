"""Exact checks shared by the verifiers (ADR 0010).

``reduces_to_zero`` tries increasingly expensive rewrites and says which one
proved the difference is 0. ``compare_constants`` compares a result with a
value obtained by another method and has three answers: proved equal, proved
different (numerically, by more than 30 significant digits), or undecided.
Undecided is never reported as a failure.
"""

from collections.abc import Callable
from dataclasses import dataclass

import sympy as sp

from app.verification.deadline import StepTimeout, time_limit
from app.verification.numeric import Evaluation, agrees, to_mpf
from app.verification.reports import show

# Cheapest first. ``simplify`` can take minutes (e.g. on algebraic numbers), so
# it gets a time limit of its own: running out of it means "not proved".
SIMPLIFY_SECONDS = 1.0
_REWRITES: tuple[tuple[str, Callable[[sp.Expr], sp.Expr]], ...] = (
    ("expandindo", sp.expand),
    ("juntando as frações", lambda expr: sp.cancel(sp.together(expr))),
)


def reduces_to_zero(expr: sp.Expr) -> str | None:
    """How ``expr`` was shown to be 0 ("expandindo"...), or None if it was not."""
    if expr == 0:
        return "diretamente"
    for how, rewrite in _REWRITES:
        if rewrite(expr) == 0:
            return how
    try:
        with time_limit(SIMPLIFY_SECONDS, step=True):
            simplified = sp.simplify(expr)
    except StepTimeout:
        return None
    return "simplificando" if simplified == 0 else None


@dataclass(frozen=True)
class Verdict:
    equal: bool | None  # True: proved equal; False: proved different; None: undecided
    detail: str = ""  # how equality was proved, or the other method's value


def compare_constants(claimed: sp.Expr, independent: sp.Expr) -> Verdict:
    """Compare a result with the same quantity obtained by another method."""
    infinite = (sp.oo, -sp.oo)
    if claimed in infinite or independent in infinite:
        if claimed == independent:
            return Verdict(True, "diretamente")
        return Verdict(False, str(independent))
    how = reduces_to_zero(claimed - independent)
    if how is not None:
        return Verdict(True, how)
    value, other = to_mpf(claimed), to_mpf(independent)
    if value is not None and other is not None and not agrees(Evaluation(other, 0), value):
        return Verdict(False, show(other))
    return Verdict(None)

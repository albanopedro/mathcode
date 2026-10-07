"""Verification of derivatives, integrals and limits (ADR 0003).

All numeric checks use the independent AST evaluator, never SymPy:

- derivative: high-precision finite differences (``mpmath.diff``);
- indefinite integral: differentiate the antiderivative (a different algorithm
  from integrating) and compare with the integrand, exactly and at points;
- definite integral: tanh-sinh quadrature (``mpmath.quad``);
- limit: evaluate while approaching the point. This is evidence, not proof,
  so the best status is ``partial``.
"""

from collections.abc import Callable

import mpmath
import sympy as sp
from mpmath import mp, mpf

from app.math_engine.calculus import (
    DerivativeOutcome,
    IntegralOutcome,
    LimitKind,
    LimitOutcome,
    show_value,
)
from app.models.result import VerificationReport, VerificationStatus
from app.parsing.ast import Node, variables
from app.parsing.build import symbol
from app.verification.algebra import REQUIRED_POINTS, describe, points, try_evaluate
from app.verification.numeric import OutsideDomain, TooLarge, agrees, decimal, evaluate, to_mpf
from app.verification.reports import report, show

DIFF_PRECISION = 80  # digits for finite differences
DERIVATIVE_TOLERANCE = mpf("1e-8")  # relative: finite differences of order 10 keep ~10 digits
QUAD_PRECISION = 30
QUAD_TOLERANCE = mpf("1e-10")


def _function_of(tree: Node, name: str, others: dict[str, str]) -> Callable[[mpf], mpf]:
    def f(t: mpf) -> mpf:
        return evaluate(tree, {**others, name: mpmath.nstr(t, DIFF_PRECISION + 10)}).value

    return f


# -- derivative ---------------------------------------------------------------------------------


def numeric_derivative(tree: Node, name: str, point: dict[str, str], order: int) -> mpf:
    others = {k: v for k, v in point.items() if k != name}
    with mp.workdps(DIFF_PRECISION):
        step = mpf(10) ** (-(60 // (order + 2)))
        return mpmath.diff(_function_of(tree, name, others), mpf(point[name]), order, h=step)


def verify_derivative(outcome: DerivativeOutcome) -> VerificationReport:
    name = outcome.variable.name
    names = sorted(variables(outcome.tree) | {name})
    agreeing = 0
    for point in points(outcome.parsed.canonical, names):
        try:
            numeric = numeric_derivative(outcome.tree, name, point, outcome.order)
        except OutsideDomain, TooLarge, ZeroDivisionError:
            continue
        exact = to_mpf(outcome.result, {symbol(n): v for n, v in point.items()})
        if exact is None:
            continue
        with mp.workdps(DIFF_PRECISION):
            error = abs(numeric - exact)
            allowed = DERIVATIVE_TOLERANCE * max(1, abs(exact))
        if error > allowed:
            return report(
                VerificationStatus.FAILED,
                "finite_differences",
                [
                    f"Em {describe(point)}, a derivada numérica vale {show(numeric)}, "
                    f"mas o resultado vale {show(exact)}."
                ],
            )
        agreeing += 1
        if agreeing == REQUIRED_POINTS:
            break

    if agreeing < REQUIRED_POINTS:
        return report(
            VerificationStatus.UNVERIFIED,
            "finite_differences",
            [f"Só {agreeing} ponto(s) do domínio foram encontrados para comparar."],
        )
    return report(
        VerificationStatus.VERIFIED_NUMERIC,
        "finite_differences",
        [
            f"A derivada numérica (diferenças finitas com {DIFF_PRECISION} dígitos, calculada "
            f"sobre a expressão original por um avaliador independente) coincide com o "
            f"resultado em {agreeing} pontos sorteados, com erro relativo menor que 10⁻⁸."
        ],
    )


# -- integral -----------------------------------------------------------------------------------


def verify_integral(outcome: IntegralOutcome) -> VerificationReport:
    if outcome.definite:
        return _verify_definite(outcome)
    return _verify_indefinite(outcome)


def _verify_indefinite(outcome: IntegralOutcome) -> VerificationReport:
    var = outcome.variable
    antiderivative, raw = outcome.antiderivative, outcome.raw_antiderivative
    if antiderivative is None or raw is None:
        raise AssertionError("an indefinite integral has an antiderivative")
    derivative = sp.diff(antiderivative, var)

    names = sorted(variables(outcome.tree) | {var.name})
    agreeing = 0
    for point in points(outcome.parsed.canonical, names):
        expected = try_evaluate(outcome.tree, point)
        if expected is None:
            continue  # the integrand is not defined here
        subs = {symbol(n): v for n, v in point.items()}
        # The antiderivative itself must exist wherever the integrand does: log(x)
        # has the right derivative, 1/x, but is not real for x < 0.
        if to_mpf(antiderivative, subs) is None:
            return report(
                VerificationStatus.FAILED,
                "differentiation",
                [
                    f"Em {describe(point)}, o integrando é definido, mas a primitiva não tem "
                    "valor real."
                ],
            )
        actual = to_mpf(derivative, subs)
        if actual is None or not agrees(expected, actual):
            got = "não tem valor real" if actual is None else f"vale {show(actual)}"
            return report(
                VerificationStatus.FAILED,
                "differentiation",
                [
                    f"Em {describe(point)}, o integrando vale {show(expected.value)}, mas a "
                    f"derivada da primitiva {got}."
                ],
            )
        agreeing += 1
        if agreeing == REQUIRED_POINTS:
            break

    if agreeing < REQUIRED_POINTS:
        return report(
            VerificationStatus.UNVERIFIED,
            "differentiation",
            [f"Só {agreeing} ponto(s) do domínio foram encontrados para comparar."],
        )

    numeric = (
        f"O avaliador independente confirma: a derivada da primitiva é igual ao integrando "
        f"em {agreeing} pontos sorteados."
    )
    if sp.simplify(derivative - outcome.integrand) == 0:
        checks = ["Derivando a primitiva, obtém-se exatamente o integrando.", numeric]
        return report(VerificationStatus.VERIFIED_SYMBOLIC, "differentiation", checks)
    if raw != antiderivative and sp.simplify(sp.diff(raw, var) - outcome.integrand) == 0:
        checks = [
            "Derivando a primitiva com ln(u), obtém-se exatamente o integrando; trocar ln(u) "
            "por ln|u| não muda a derivada (d/dx ln|u| = u'/u).",
            numeric,
        ]
        return report(VerificationStatus.VERIFIED_SYMBOLIC, "differentiation", checks)
    return report(VerificationStatus.VERIFIED_NUMERIC, "differentiation", [numeric])


def _bound(value: sp.Expr) -> mpf:
    if value == sp.oo:
        return mpmath.inf
    if value == -sp.oo:
        return -mpmath.inf
    return mpf(decimal(value))


def _verify_definite(outcome: IntegralOutcome) -> VerificationReport:
    if outcome.value is None or outcome.lower is None or outcome.upper is None:
        raise AssertionError("a definite integral has bounds and a value")
    if not outcome.converges:
        return report(
            VerificationStatus.UNVERIFIED,
            "quadrature",
            ["A divergência da integral não é conferida numericamente."],
        )

    exact = to_mpf(outcome.value)
    if exact is None:
        return report(
            VerificationStatus.FAILED, "quadrature", ["O resultado não é um número real."]
        )

    f = _function_of(outcome.tree, outcome.variable.name, {})
    try:
        with mp.workdps(QUAD_PRECISION):
            numeric, estimate = mpmath.quad(
                f, [_bound(outcome.lower), _bound(outcome.upper)], error=True
            )
    except OutsideDomain, TooLarge, ZeroDivisionError:
        return report(
            VerificationStatus.UNVERIFIED,
            "quadrature",
            [
                "O avaliador independente não conseguiu integrar numericamente: a função não "
                "é definida em algum ponto do intervalo."
            ],
        )

    with mp.workdps(QUAD_PRECISION):
        error = abs(numeric - exact)
        allowed = QUAD_TOLERANCE * max(1, abs(exact))
        conclusive = estimate < allowed
    if error <= allowed:
        return report(
            VerificationStatus.VERIFIED_NUMERIC,
            "quadrature",
            [
                f"A integração numérica independente (tanh-sinh, mpmath) dá {show(numeric)}, "
                "igual ao resultado com erro relativo menor que 10⁻¹⁰."
            ],
        )
    if not conclusive:
        return report(
            VerificationStatus.UNVERIFIED,
            "quadrature",
            [
                f"A integração numérica deu {show(numeric)}, mas com estimativa de erro "
                f"{show(estimate)}: inconclusiva."
            ],
        )
    return report(
        VerificationStatus.FAILED,
        "quadrature",
        [f"A integração numérica independente dá {show(numeric)}, e não {show(exact)}."],
    )


# -- limit ----------------------------------------------------------------------------------------

_CLOSE = mpf("1e-6")  # relative error at the closest point that counts as "approaching"
_STABLE = mpf("1e-9")  # two last values this close: the sequence has settled
_LARGE = mpf("1e6")


def _approach_points(point: sp.Expr, side: str) -> list[tuple[str, str]]:
    """(exact decimal value, readable description) of the points that approach ``point``."""
    if point in (sp.oo, -sp.oo):
        sign = "" if point == sp.oo else "-"
        return [(f"{sign}1e{k}", f"{sign}10^{k}") for k in (3, 6, 12, 24)]
    # Down to 10^-24: slow limits such as sqrt(x) -> 0 are still 10^-6 away at 10^-12.
    sign = -1 if side == "left" else 1
    symbol_ = "-" if side == "left" else "+"
    with mp.workdps(90):
        center = mpf(decimal(point))
        return [
            (
                mpmath.nstr(center + sign * mpf(10) ** -k, 85),
                f"{show_value(point)} {symbol_} 10^-{k}",
            )
            for k in (3, 6, 12, 24)
        ]


def _evidence(values: list[mpf], claimed: sp.Expr) -> str:
    """'consistent', 'contradicts' or 'inconclusive' for one side."""
    if len(values) < 2:
        return "inconclusive"
    last, previous = values[-1], values[-2]
    if claimed in (sp.oo, -sp.oo):
        sign = 1 if claimed == sp.oo else -1
        if sign * last > _LARGE and sign * last > sign * previous:
            return "consistent"
        settled = abs(last - previous) <= _STABLE * max(1, abs(last))
        return "contradicts" if settled and abs(last) < 1000 else "inconclusive"
    target = to_mpf(claimed)
    if target is None:
        return "inconclusive"
    with mp.workdps(60):
        scale = max(1, abs(target))
        if abs(last - target) <= _CLOSE * scale:
            return "consistent"
        settled = abs(last - previous) <= _STABLE * scale
        return (
            "contradicts"
            if settled and abs(last - target) > 1000 * _CLOSE * scale
            else "inconclusive"
        )


def verify_limit(outcome: LimitOutcome) -> VerificationReport:
    if outcome.oscillates:
        return report(
            VerificationStatus.UNVERIFIED,
            "approach",
            ["Oscilações não são conferidas numericamente."],
        )
    name = outcome.variable.name
    infinite = outcome.point in (sp.oo, -sp.oo)
    sides = (
        ["both"] if infinite else (["left", "right"] if outcome.side == "both" else [outcome.side])
    )

    checks: list[str] = []
    verdicts: list[str] = []
    for side in sides:
        if outcome.kind is LimitKind.NONEXISTENT:
            claimed = outcome.left if side == "left" else outcome.right
        else:
            claimed = outcome.value
        if claimed is None:
            verdicts.append("inconclusive")
            continue
        values: list[mpf] = []
        closest = ""
        for text, label in _approach_points(outcome.point, side):
            evaluation = try_evaluate(outcome.tree, {name: text})
            if evaluation is not None:
                values.append(evaluation.value)
                closest = label
        verdict = _evidence(values, claimed)
        verdicts.append(verdict)
        where = {"left": " pela esquerda", "right": " pela direita", "both": ""}[side]
        if values:
            checks.append(
                f"Aproximando-se{where} ({name} = {closest}), a função vale "
                f"{show(values[-1])}; o limite indicado é {show_value(claimed)}."
            )

    if "contradicts" in verdicts:
        return report(VerificationStatus.FAILED, "approach", checks)
    if all(v == "consistent" for v in verdicts):
        checks.append("É evidência numérica, não prova: por isso a verificação é parcial.")
        return report(VerificationStatus.PARTIAL, "approach", checks)
    checks.append("A aproximação numérica foi inconclusiva.")
    return report(VerificationStatus.UNVERIFIED, "approach", checks)

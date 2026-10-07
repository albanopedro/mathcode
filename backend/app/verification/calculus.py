"""Verification of derivatives, integrals and limits (ADR 0003, ADR 0010).

Numeric checks use the independent AST evaluator, never SymPy:

- derivative: high-precision finite differences (``mpmath.diff``);
- indefinite integral: differentiate the antiderivative (a different algorithm
  from integrating) and compare with the integrand, exactly and at points;
- definite integral: tanh-sinh quadrature (``mpmath.quad``);
- limit: evaluate while approaching the point (evidence, not proof).

Comparisons of methods, each with a time limit of its own:

- derivative: a second differentiator, with the textbook rules;
- definite integral: Newton–Leibniz, for polynomials and rational functions;
- limit: continuity at the point, which proves the limit is the value there.
"""

import logging
from collections.abc import Callable

import mpmath
import sympy as sp
from mpmath import mp, mpf

from app.formatting.expressions import plain
from app.math_engine.calculus import (
    DerivativeOutcome,
    IntegralOutcome,
    LimitKind,
    LimitOutcome,
    show_value,
)
from app.models.result import (
    CheckKind,
    CheckOutcome,
    ReasonCode,
    VerificationCheck,
    VerificationReport,
    VerificationStatus,
)
from app.parsing.ast import Node, variables
from app.parsing.build import ExpressionBuilder, symbol
from app.verification.algebra import REQUIRED_POINTS, describe, points, try_evaluate
from app.verification.continuity import continuity_obstacle
from app.verification.deadline import StepTimeout, time_limit
from app.verification.differentiate import differentiate
from app.verification.newton_leibniz import newton_leibniz
from app.verification.numeric import (
    BASE_PRECISION,
    OutsideDomain,
    TooLarge,
    agrees,
    decimal,
    evaluate,
    to_mpf,
)
from app.verification.reports import (
    failed,
    failure,
    inconclusive,
    passed,
    report,
    show,
    unverified,
)
from app.verification.symbolic import compare_constants, reduces_to_zero

logger = logging.getLogger(__name__)

# Finite differences of order n divide by h^n: with h = 10^-k they lose n·k digits,
# so the precision grows with the order (ADR 0010). Order 10: 180 digits, h = 10^-14.
DIFF_PRECISION = 80  # digits for a first derivative, plus DIFF_DIGITS_PER_ORDER per order
DIFF_DIGITS_PER_ORDER = 10
DIFF_KEPT_DIGITS = 40  # digits left after the division by h^n
DERIVATIVE_TOLERANCE = mpf("1e-8")  # relative: finite differences of order 10 keep ~10 digits
QUAD_PRECISION = 30
QUAD_TOLERANCE = mpf("1e-10")
COMPARISON_SECONDS = 1.5  # each comparison of methods; past it, it is inconclusive

_TOO_SLOW = "A comparação com um segundo método não terminou a tempo."


def _function_of(
    tree: Node, name: str, others: dict[str, str], digits: int = DIFF_PRECISION
) -> Callable[[mpf], mpf]:
    def f(t: mpf) -> mpf:
        return evaluate(tree, {**others, name: mpmath.nstr(t, digits + 10)}, digits).value

    return f


# -- derivative ---------------------------------------------------------------------------------


def numeric_derivative(tree: Node, name: str, point: dict[str, str], order: int) -> mpf:
    others = {k: v for k, v in point.items() if k != name}
    digits = DIFF_PRECISION + DIFF_DIGITS_PER_ORDER * order
    with mp.workdps(digits):
        step = mpf(10) ** (-((digits - DIFF_KEPT_DIGITS) // order))
        f = _function_of(tree, name, others, digits)
        return mpmath.diff(f, mpf(point[name]), order, h=step)


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
        with mp.workdps(BASE_PRECISION):
            error = abs(numeric - exact)
            allowed = DERIVATIVE_TOLERANCE * max(1, abs(exact))
        if error > allowed:
            return failure(
                CheckKind.NUMERIC,
                f"Em {describe(point)}, a derivada numérica vale {show(numeric)}, "
                f"mas o resultado vale {show(exact)}.",
            )
        agreeing += 1
        if agreeing == REQUIRED_POINTS:
            break

    if agreeing < REQUIRED_POINTS:
        numeric_check = inconclusive(
            CheckKind.NUMERIC, f"Só {agreeing} ponto(s) do domínio foram encontrados para comparar."
        )
    else:
        numeric_check = passed(
            CheckKind.NUMERIC,
            "A derivada numérica (diferenças finitas com "
            f"{DIFF_PRECISION + DIFF_DIGITS_PER_ORDER * outcome.order} dígitos, calculada "
            "sobre a expressão original por um avaliador independente) coincide com o "
            f"resultado em {agreeing} pontos sorteados, com erro relativo menor que 10⁻⁸.",
        )
    comparison = _compare_derivatives(outcome)
    checks = [numeric_check, comparison]
    if comparison.outcome is CheckOutcome.PASSED:
        return report(VerificationStatus.VERIFIED_SYMBOLIC, checks)
    if numeric_check.outcome is CheckOutcome.PASSED:
        return report(VerificationStatus.VERIFIED_NUMERIC, checks)
    return report(VerificationStatus.UNVERIFIED, checks, ReasonCode.FEW_POINTS)


def _compare_derivatives(outcome: DerivativeOutcome) -> VerificationCheck:
    try:
        with time_limit(COMPARISON_SECONDS, step=True):
            ours = differentiate(outcome.function, outcome.variable, outcome.order)
            how = None if ours is None else reduces_to_zero(ours - outcome.result)
    except StepTimeout:
        return inconclusive(CheckKind.COMPARISON, _TOO_SLOW)
    if ours is None:
        return inconclusive(
            CheckKind.COMPARISON,
            "A expressão usa uma função fora da tabela do segundo derivador (como sign).",
        )
    if how is None:
        logger.warning("the two differentiators disagree on %s", outcome.function)
        return inconclusive(
            CheckKind.COMPARISON,
            "Um segundo derivador (regras de soma, produto e cadeia) chegou a uma forma que "
            "não foi possível igualar à do resultado.",
        )
    return passed(
        CheckKind.COMPARISON,
        "Um segundo derivador, escrito com as regras de soma, produto, potência e cadeia (sem "
        f"o diff do SymPy), chega ao mesmo resultado: a diferença se reduz a 0 ({how}).",
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
            return failure(
                CheckKind.DOMAIN,
                f"Em {describe(point)}, o integrando é definido, mas a primitiva não tem "
                "valor real.",
            )
        actual = to_mpf(derivative, subs)
        if actual is None or not agrees(expected, actual):
            got = "não tem valor real" if actual is None else f"vale {show(actual)}"
            return failure(
                CheckKind.NUMERIC,
                f"Em {describe(point)}, o integrando vale {show(expected.value)}, mas a "
                f"derivada da primitiva {got}.",
            )
        agreeing += 1
        if agreeing == REQUIRED_POINTS:
            break

    if agreeing < REQUIRED_POINTS:
        return unverified(
            ReasonCode.FEW_POINTS,
            CheckKind.NUMERIC,
            f"Só {agreeing} ponto(s) do domínio foram encontrados para comparar.",
        )

    domain = passed(
        CheckKind.DOMAIN, "A primitiva é real em todos os pontos em que o integrando é definido."
    )
    numeric = passed(
        CheckKind.NUMERIC,
        "O avaliador independente confirma: a derivada da primitiva é igual ao integrando "
        f"em {agreeing} pontos sorteados.",
    )
    how = reduces_to_zero(derivative - outcome.integrand)
    if how is not None:
        symbolic = passed(
            CheckKind.SYMBOLIC,
            f"Derivando a primitiva, obtém-se exatamente o integrando ({how}).",
        )
        return report(VerificationStatus.VERIFIED_SYMBOLIC, [symbolic, domain, numeric])
    if raw != antiderivative and reduces_to_zero(sp.diff(raw, var) - outcome.integrand):
        symbolic = passed(
            CheckKind.SYMBOLIC,
            "Derivando a primitiva com ln(u), obtém-se exatamente o integrando; trocar ln(u) "
            "por ln|u| não muda a derivada (d/dx ln|u| = u'/u).",
        )
        return report(VerificationStatus.VERIFIED_SYMBOLIC, [symbolic, domain, numeric])
    return report(VerificationStatus.VERIFIED_NUMERIC, [domain, numeric])


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
        return unverified(
            ReasonCode.NO_STRATEGY,
            CheckKind.NUMERIC,
            "A divergência da integral não é conferida numericamente.",
        )

    exact = to_mpf(outcome.value)
    if exact is None:
        return failure(CheckKind.NUMERIC, "O resultado não é um número real.")

    quadrature = _quadrature(outcome, exact)
    if quadrature.outcome is CheckOutcome.FAILED:
        return report(VerificationStatus.FAILED, [quadrature])
    comparison = _compare_newton_leibniz(outcome)
    checks = [quadrature] if comparison is None else [quadrature, comparison]
    if comparison is not None and comparison.outcome is CheckOutcome.FAILED:
        return report(VerificationStatus.FAILED, checks)
    if comparison is not None and comparison.outcome is CheckOutcome.PASSED:
        return report(VerificationStatus.VERIFIED_SYMBOLIC, checks)
    if quadrature.outcome is CheckOutcome.PASSED:
        return report(VerificationStatus.VERIFIED_NUMERIC, checks)
    return report(VerificationStatus.UNVERIFIED, checks, ReasonCode.INCONCLUSIVE)


def _quadrature(outcome: IntegralOutcome, exact: mpf) -> VerificationCheck:
    if outcome.lower is None or outcome.upper is None:
        raise AssertionError("a definite integral has bounds")
    f = _function_of(outcome.tree, outcome.variable.name, {})
    try:
        with mp.workdps(QUAD_PRECISION):
            numeric, estimate = mpmath.quad(
                f, [_bound(outcome.lower), _bound(outcome.upper)], error=True
            )
    except OutsideDomain, TooLarge, ZeroDivisionError:
        return inconclusive(
            CheckKind.NUMERIC,
            "O avaliador independente não conseguiu integrar numericamente: a função não é "
            "definida em algum ponto do intervalo.",
        )

    with mp.workdps(QUAD_PRECISION):
        error = abs(numeric - exact)
        allowed = QUAD_TOLERANCE * max(1, abs(exact))
        conclusive = estimate < allowed
    if error <= allowed:
        return passed(
            CheckKind.NUMERIC,
            f"A integração numérica independente (tanh-sinh, mpmath) dá {show(numeric)}, igual "
            "ao resultado com erro relativo menor que 10⁻¹⁰.",
        )
    if not conclusive:
        return inconclusive(
            CheckKind.NUMERIC,
            f"A integração numérica deu {show(numeric)}, mas com estimativa de erro "
            f"{show(estimate)}: inconclusiva.",
        )
    return failed(
        CheckKind.NUMERIC,
        f"A integração numérica independente dá {show(numeric)}, e não {show(exact)}.",
    )


def _compare_newton_leibniz(outcome: IntegralOutcome) -> VerificationCheck | None:
    """None when the integrand is out of this comparison's scope."""
    if outcome.value is None or outcome.lower is None or outcome.upper is None:
        raise AssertionError("a definite integral has bounds and a value")
    try:
        with time_limit(COMPARISON_SECONDS, step=True):
            found = newton_leibniz(
                outcome.integrand, outcome.variable, outcome.lower, outcome.upper
            )
            verdict = None
            if found is not None and found.value is not None:
                verdict = compare_constants(outcome.value, found.value)
    except StepTimeout:
        return inconclusive(CheckKind.COMPARISON, _TOO_SLOW)
    if found is None:
        return None
    if found.value is None or verdict is None:
        return inconclusive(
            CheckKind.COMPARISON, f"Newton–Leibniz (F(b) − F(a)) não se aplica: {found.note}."
        )
    if verdict.equal is False:
        return failed(
            CheckKind.COMPARISON,
            f"Por Newton–Leibniz, {found.note}, a integral vale {verdict.detail}.",
        )
    if verdict.equal is None:
        return inconclusive(
            CheckKind.COMPARISON,
            f"Por Newton–Leibniz, a integral vale {plain(found.value)}, mas não foi possível "
            "igualar esse valor ao resultado.",
        )
    return passed(
        CheckKind.COMPARISON,
        f"Por Newton–Leibniz, F(b) − F(a) = {plain(found.value)}, igual ao resultado "
        f"({verdict.detail}); {found.note}.",
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
    continuity = _compare_continuity(outcome)
    if continuity is not None and continuity.outcome is CheckOutcome.FAILED:
        return report(VerificationStatus.FAILED, [continuity])
    proved = continuity is not None and continuity.outcome is CheckOutcome.PASSED

    if outcome.oscillates:
        return unverified(
            ReasonCode.NO_STRATEGY,
            CheckKind.NUMERIC,
            "Oscilações não são conferidas numericamente.",
        )
    name = outcome.variable.name
    infinite = outcome.point in (sp.oo, -sp.oo)
    sides = (
        ["both"] if infinite else (["left", "right"] if outcome.side == "both" else [outcome.side])
    )

    checks: list[VerificationCheck] = []
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
            message = (
                f"Aproximando-se{where} ({name} = {closest}), a função vale "
                f"{show(values[-1])}; o limite indicado é {show_value(claimed)}."
            )
            if verdict == "consistent":
                checks.append(passed(CheckKind.NUMERIC, message))
            elif verdict == "contradicts":
                checks.append(failed(CheckKind.NUMERIC, message))
            else:
                checks.append(inconclusive(CheckKind.NUMERIC, message))

    if "contradicts" in verdicts:
        return report(VerificationStatus.FAILED, checks)
    if proved and continuity is not None:
        return report(VerificationStatus.VERIFIED_SYMBOLIC, [continuity, *checks])
    if continuity is not None:
        checks.append(continuity)
    if verdicts and all(v == "consistent" for v in verdicts):
        checks.append(
            inconclusive(
                CheckKind.NUMERIC,
                "É evidência numérica, não prova: por isso a verificação é parcial.",
            )
        )
        return report(VerificationStatus.PARTIAL, checks, ReasonCode.NUMERIC_EVIDENCE_ONLY)
    checks.append(inconclusive(CheckKind.NUMERIC, "A aproximação numérica foi inconclusiva."))
    return report(VerificationStatus.UNVERIFIED, checks, ReasonCode.INCONCLUSIVE)


def _compare_continuity(outcome: LimitOutcome) -> VerificationCheck | None:
    """Continuity at the point proves the limit is f(point). None at ±∞."""
    if outcome.point in (sp.oo, -sp.oo):
        return None
    name, shown = outcome.variable.name, show_value(outcome.point)
    try:
        with time_limit(COMPARISON_SECONDS, step=True):
            obstacle = continuity_obstacle(outcome.tree, name, outcome.point)
            verdict = None
            if obstacle is None:
                at_point = (
                    ExpressionBuilder().build(outcome.tree).subs(outcome.variable, outcome.point)
                )
                if outcome.kind is not LimitKind.NONEXISTENT and outcome.value is not None:
                    verdict = compare_constants(outcome.value, at_point)
    except StepTimeout:
        return inconclusive(CheckKind.COMPARISON, _TOO_SLOW)
    if obstacle is not None:
        return inconclusive(
            CheckKind.COMPARISON,
            f"Não dá para usar a continuidade em {name} = {shown}: {obstacle}.",
        )
    if outcome.oscillates or outcome.kind is LimitKind.NONEXISTENT or verdict is None:
        return failed(
            CheckKind.COMPARISON,
            f"A função é contínua em {name} = {shown}, então o limite existe e vale "
            f"{plain(at_point)}.",
        )
    if verdict.equal is False:
        return failed(
            CheckKind.COMPARISON,
            f"A função é contínua em {name} = {shown}, então o limite é o valor "
            f"nesse ponto, {verdict.detail}.",
        )
    if verdict.equal is None:
        return inconclusive(
            CheckKind.COMPARISON,
            f"A função é contínua em {name} = {shown} e vale {plain(at_point)} ali, mas não foi "
            "possível igualar esse valor ao limite calculado.",
        )
    return passed(
        CheckKind.COMPARISON,
        f"A função é contínua em {name} = {shown} (nenhum denominador se anula e todas as "
        "funções estão no interior do domínio), então o limite é o valor no ponto: "
        f"{plain(at_point)}, igual ao resultado ({verdict.detail}).",
    )

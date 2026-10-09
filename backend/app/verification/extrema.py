"""Verification of critical points, maxima, minima and the vertex (ADR 0021).

- **derivative:** a second differentiator (``differentiate.py``, the textbook
  rules, no SymPy ``diff``) must give the same f' as the equation that was
  solved;
- **critical points:** f'(x) = 0 is verified like any equation (substitution,
  and completeness by Sturm for polynomials and rational functions);
- **values:** f(x₀) is recomputed by the independent evaluator on the
  original expression;
- **classification:** compared with f at the test points on each side. f is
  monotone between a critical point and its test points (no other critical
  point or pole in between), so a maximum must be above both;
- **vertex:** for a parabola, x = −b/(2a) and the sign of a, by the formula.
"""

import sympy as sp
from mpmath import mp, mpf

from app.formatting.expressions import parser_text, plain
from app.math_engine.equations import SolutionKind
from app.math_engine.extrema import CriticalPoint, ExtremaOutcome
from app.models.result import (
    CheckKind,
    CheckOutcome,
    ReasonCode,
    VerificationCheck,
    VerificationReport,
    VerificationStatus,
)
from app.verification.algebra import points as sample
from app.verification.algebra import try_evaluate
from app.verification.differentiate import differentiate
from app.verification.equations import verify_equation
from app.verification.numeric import BASE_PRECISION, Evaluation, agrees, decimal, to_mpf
from app.verification.reports import failure, inconclusive, passed, report, show
from app.verification.symbolic import reduces_to_zero

# Values of f near a critical point differ little: subtract them with room to spare.
COMPARISON_PRECISION = 2 * BASE_PRECISION
REQUIRED_POINTS = 6

_KIND_WORDS = {"max": "máximo local", "min": "mínimo local", "none": "nem máximo nem mínimo"}


def verify_extrema(outcome: ExtremaOutcome) -> VerificationReport:
    checks: list[VerificationCheck] = []
    numeric_only = False

    derivative = _derivative_check(outcome)
    if derivative.outcome is CheckOutcome.FAILED:
        return failure(derivative.kind, derivative.message)
    checks.append(derivative)

    incomplete = False  # completeness of f'(x) = 0 not proved
    if outcome.equation is None:
        checks.append(
            passed(
                CheckKind.SYMBOLIC,
                f"f'({outcome.variable.name}) = {parser_text(outcome.derivative)} é constante e "
                "diferente de zero: não há pontos críticos.",
            )
        )
    else:
        equation = verify_equation(outcome.equation)
        for check in equation.checks:
            prefixed = check.model_copy(update={"message": f"Em f'(x) = 0: {check.message}"})
            if check.outcome is CheckOutcome.FAILED:
                return failure(check.kind, prefixed.message, *checks)
            checks.append(prefixed)
        numeric_only = equation.status is VerificationStatus.VERIFIED_NUMERIC
        incomplete = equation.reason is ReasonCode.COMPLETENESS_NOT_PROVED

    name = outcome.variable.name
    for point in outcome.points:
        shown = f"{name} = {plain(point.x)}"
        value = try_evaluate(outcome.tree, {name: decimal(point.x)})
        if value is None:
            return failure(CheckKind.DOMAIN, f"A função não tem valor real em {shown}.", *checks)
        claimed = to_mpf(point.y)
        if claimed is None or not agrees(value, claimed):
            return failure(
                CheckKind.NUMERIC,
                f"Em {shown}, o avaliador independente obteve f = {show(value.value)}, "
                f"diferente de {plain(point.y)}.",
                *checks,
            )
        classification = _classification(outcome, point, value)
        if classification.outcome is CheckOutcome.FAILED:
            return failure(classification.kind, classification.message, *checks)
        checks.append(classification)
    if outcome.points:
        count = len(outcome.points)
        which = "no ponto crítico" if count == 1 else f"em cada um dos {count} pontos críticos"
        checks.append(
            passed(
                CheckKind.NUMERIC,
                f"O valor de f {which} foi recalculado pelo avaliador independente "
                "na expressão original, e coincide em 30 algarismos.",
            )
        )

    if outcome.quadratic:
        vertex = _vertex_check(outcome)
        if vertex.outcome is CheckOutcome.FAILED:
            return failure(vertex.kind, vertex.message, *checks)
        checks.append(vertex)

    outcomes = {check.outcome for check in checks}
    if CheckOutcome.INCONCLUSIVE in outcomes:
        reason = ReasonCode.COMPLETENESS_NOT_PROVED if incomplete else ReasonCode.INCONCLUSIVE
        return report(VerificationStatus.PARTIAL, checks, reason)
    if numeric_only or derivative.kind is CheckKind.NUMERIC:
        return report(VerificationStatus.VERIFIED_NUMERIC, checks)
    return report(VerificationStatus.VERIFIED_SYMBOLIC, checks)


def _derivative_check(outcome: ExtremaOutcome) -> VerificationCheck:
    """The equation solved must be f' computed by another differentiator."""
    var = outcome.variable
    if outcome.equation is None:
        solved = outcome.derivative
    else:
        solved = outcome.equation.left - outcome.equation.right
    own = differentiate(outcome.function, var)
    if own is None:
        return inconclusive(
            CheckKind.COMPARISON,
            "O segundo derivador (regras de derivação) não cobre esta função; a derivada "
            "não foi conferida por outro método.",
        )
    if reduces_to_zero(own - solved) is not None:
        return passed(
            CheckKind.COMPARISON,
            f"Um segundo derivador (regras de derivação, sem o SymPy) obtém a mesma derivada "
            f"f'({var.name}) = {parser_text(own)}.",
        )
    # Not proved equal: compare at points; a difference is a failure.
    agreeing = 0
    for point in sample(f"extrema:{outcome.parsed.canonical}", [var.name]):
        at = {var: point[var.name]}
        expected, actual = to_mpf(own, at), to_mpf(solved, at)
        if expected is None or actual is None:
            continue
        if not agrees(Evaluation(expected, 0), actual):
            return VerificationCheck(
                kind=CheckKind.COMPARISON,
                outcome=CheckOutcome.FAILED,
                message=f"Em {var.name} = {point[var.name]}, o segundo derivador dá "
                f"{show(expected)}, mas a derivada resolvida dá {show(actual)}.",
            )
        agreeing += 1
        if agreeing == REQUIRED_POINTS:
            return passed(
                CheckKind.NUMERIC,
                f"A derivada de um segundo derivador coincide com a derivada resolvida em "
                f"{REQUIRED_POINTS} pontos sorteados (a igualdade exata não foi decidida).",
            )
    return inconclusive(
        CheckKind.COMPARISON, "A derivada não pôde ser comparada com a de um segundo derivador."
    )


def _classification(
    outcome: ExtremaOutcome, point: CriticalPoint, at_point: Evaluation
) -> VerificationCheck:
    name = outcome.variable.name
    shown = f"{name} = {plain(point.x)}"
    if point.kind == "unknown":
        return inconclusive(
            CheckKind.NUMERIC,
            f"O ponto crítico {shown} não pôde ser classificado: a derivada não existe perto "
            "dele, de um dos lados.",
        )
    left = try_evaluate(outcome.tree, {name: point.left})
    right = try_evaluate(outcome.tree, {name: point.right})
    if left is None or right is None:
        return inconclusive(
            CheckKind.NUMERIC, f"Não foi possível avaliar f dos dois lados de {shown}."
        )
    with mp.workdps(COMPARISON_PRECISION):
        sides = [_compare(side, at_point) for side in (left, right)]
    if None in sides:
        return inconclusive(
            CheckKind.NUMERIC,
            f"Perto de {shown}, os valores de f são iguais demais para comparar com segurança.",
        )
    expected = {"max": [-1, -1], "min": [1, 1]}.get(point.kind)
    consistent = sides == expected if expected else sides[0] != sides[1]
    word = _KIND_WORDS[point.kind]
    if not consistent:
        return VerificationCheck(
            kind=CheckKind.NUMERIC,
            outcome=CheckOutcome.FAILED,
            message=f"Em {shown} a resposta diz {word}, mas f vale {show(left.value)} à "
            f"esquerda e {show(right.value)} à direita, contra {show(at_point.value)} no ponto.",
        )
    return passed(
        CheckKind.NUMERIC,
        f"{shown} é {word}: comparando f no ponto com f em {name} = {_short(point.left)} e "
        f"{name} = {_short(point.right)} (sem outro ponto crítico no meio), pelo avaliador "
        "independente.",
    )


def _compare(side: Evaluation, at_point: Evaluation) -> int | None:
    """+1 if f is higher at the side than at the point, -1 if lower, None if too close to tell."""
    difference = side.value - at_point.value
    if abs(difference) <= side.error_bound + at_point.error_bound:
        return None
    return 1 if difference > 0 else -1


def _short(value: str) -> str:
    with mp.workdps(BASE_PRECISION):
        return show(mpf(value))


def _vertex_check(outcome: ExtremaOutcome) -> VerificationCheck:
    var = outcome.variable
    poly = sp.Poly(outcome.function, var)
    a, b = poly.coeff_monomial(var**2), poly.coeff_monomial(var)
    formula = -b / (2 * a)
    equation = outcome.equation
    if equation is None or equation.kind is not SolutionKind.FINITE or len(outcome.points) != 1:
        return VerificationCheck(
            kind=CheckKind.COMPARISON,
            outcome=CheckOutcome.FAILED,
            message="Uma parábola tem exatamente um vértice, mas a resposta não tem um só ponto.",
        )
    point = outcome.points[0]
    expected_kind = "min" if a > 0 else "max"
    if reduces_to_zero(point.x - formula) is None or point.kind != expected_kind:
        return VerificationCheck(
            kind=CheckKind.COMPARISON,
            outcome=CheckOutcome.FAILED,
            message=f"Pela fórmula do vértice, x = −b/(2a) = {plain(formula)} e o vértice é "
            f"{_KIND_WORDS[expected_kind]}, diferente da resposta.",
        )
    concavity = "para cima" if a > 0 else "para baixo"
    return passed(
        CheckKind.COMPARISON,
        f"Pela fórmula do vértice, {var.name} = −b/(2a) = {plain(formula)}, o mesmo ponto; "
        f"a = {plain(a)} {'>' if a > 0 else '<'} 0, então a parábola tem a concavidade "
        f"{concavity} e o vértice é {_KIND_WORDS[expected_kind]}.",
    )

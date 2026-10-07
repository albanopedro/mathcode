"""Verification of a graph's relevant points (ADR 0008).

The samples are drawn by the independent evaluator itself, so there is no
separate "result" to check there. What the graph claims is in its points:

- each root must make the function vanish (independent evaluator);
- exact roots come from the equation engine, whose own verification says
  whether the root set is complete (Sturm) or not;
- roots found by sign changes may miss roots where the graph only touches the
  axis, so they are at most ``partial``;
- the y-intercept must match the function at 0.
"""

from mpmath import mp, mpf

from app.math_engine.graphing import GraphOutcome, GraphPoint, y_scale
from app.models.result import (
    CheckKind,
    CheckOutcome,
    ReasonCode,
    VerificationCheck,
    VerificationReport,
    VerificationStatus,
)
from app.parsing.ast import Node
from app.verification.equations import verify_equation
from app.verification.numeric import OutsideDomain, TooLarge, agrees, evaluate, to_mpf
from app.verification.reports import failure, inconclusive, passed, report, show

_ROOT_TOLERANCE = mpf("1e-15")  # relative to the function's scale on the graph


def verify_graph(outcome: GraphOutcome) -> VerificationReport:
    if not outcome.points:
        return report(
            VerificationStatus.NOT_APPLICABLE,
            [
                passed(
                    CheckKind.NUMERIC,
                    "Os pontos do gráfico foram calculados pelo avaliador independente; não há "
                    "raízes nem intercepto a conferir nesta faixa.",
                )
            ],
        )

    checks: list[VerificationCheck] = []
    partial = False
    for index, function in enumerate(outcome.functions):
        label = f"y = {function.label}"
        points = [p for p in outcome.points if p.function == index]
        scale = y_scale(*outcome.y_range)
        for point in points:
            problem = _check_point(outcome, function.tree, point, scale)
            if problem is not None:
                return failure(CheckKind.NUMERIC, f"{label}: {problem}", *checks)

        roots = [p for p in points if p.kind == "root"]
        if points:
            checks.append(
                passed(
                    CheckKind.NUMERIC,
                    f"{label}: o avaliador independente confirma os {len(points)} ponto(s) "
                    f"destacados ({len(roots)} raiz(es)).",
                )
            )
        if function.equation is not None:
            equation = verify_equation(function.equation)
            if equation.status is VerificationStatus.FAILED:
                return report(
                    VerificationStatus.FAILED,
                    [
                        *checks,
                        *(
                            check.model_copy(update={"message": f"{label}: {check.message}"})
                            for check in equation.checks
                        ),
                    ],
                )
            complete = any(
                check.kind is CheckKind.COMPLETENESS and check.outcome is CheckOutcome.PASSED
                for check in equation.checks
            )
            if complete:
                checks.append(
                    passed(
                        CheckKind.COMPLETENESS,
                        f"{label}: as raízes vêm da resolução exata de f(x) = 0, que provou não "
                        "haver outras.",
                    )
                )
            else:
                partial = True
                checks.append(
                    inconclusive(
                        CheckKind.COMPLETENESS,
                        f"{label}: as raízes vêm da resolução exata de f(x) = 0, mas não foi "
                        "provado que são todas.",
                    )
                )
        elif function.numeric_roots:
            partial = True
            checks.append(
                inconclusive(
                    CheckKind.COMPLETENESS,
                    f"{label}: as raízes foram encontradas pela mudança de sinal; raízes em que "
                    "o gráfico só toca o eixo podem faltar.",
                )
            )

    if partial:
        return report(VerificationStatus.PARTIAL, checks, ReasonCode.COMPLETENESS_NOT_PROVED)
    return report(VerificationStatus.VERIFIED_NUMERIC, checks)


def _check_point(outcome: GraphOutcome, tree: Node, point: GraphPoint, scale: float) -> str | None:
    """None when the point is right, otherwise what is wrong."""
    name = outcome.variable.name
    try:
        value = evaluate(tree, {name: point.x_decimal})
    except OutsideDomain, TooLarge:
        return f"a função não é definida em {name} = {point.x_value}."

    if point.kind == "root":
        with mp.workdps(30):
            allowed = max(_ROOT_TOLERANCE * max(1, mpf(scale)), value.error_bound)
            if abs(value.value) > allowed:
                return f"em {name} = {point.x_value}, a função vale {show(value.value)}, não 0."
        return None

    expected = to_mpf(point.y) if point.y is not None else None
    if expected is None or not agrees(value, expected):
        return f"o intercepto em y vale {show(value.value)}, não {point.y_value}."
    return None

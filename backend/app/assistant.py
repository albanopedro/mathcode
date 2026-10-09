"""The math assistant (Phase 12, ADR 0021): runs an execution plan and sums it up.

Each step is an ordinary request (intent + text + options), calculated and
verified by the pool like any other, in parallel. A step that fails keeps its
error and does not stop the others. The combined result says how the whole was
verified: the weakest verification among the steps that were calculated.

This module runs in the API process and imports neither SymPy nor mpmath.
"""

import asyncio

from app.core.errors import ErrorCode
from app.core.workers import WorkerPool
from app.interpreter.planner import ExecutionPlan
from app.models.intents import IntentName
from app.models.result import (
    Interpretation,
    MathResult,
    PlanStepResult,
    ResultError,
    ResultValue,
    VerificationReport,
    VerificationStatus,
)

ASSISTANT_HELP = (
    'O assistente entende pedidos com vários cálculos de uma função, como "raízes, vértice '
    'e gráfico de x^2 - 4x + 3", e o estudo completo, como "estude a função x^3 - 3x".'
)

# From the strongest to the weakest; "not applicable" (a graph with nothing to
# check) counts only when no step has anything else.
_STRENGTH = (
    VerificationStatus.VERIFIED_SYMBOLIC,
    VerificationStatus.VERIFIED_NUMERIC,
    VerificationStatus.PARTIAL,
    VerificationStatus.UNVERIFIED,
)


async def run_plan(
    text: str, plan: ExecutionPlan, pool: WorkerPool, interpretation: Interpretation
) -> MathResult:
    results = await asyncio.gather(
        *(pool.calculate(step.input, step.intent, step.options or None) for step in plan.steps)
    )
    return compose(text, plan, list(results), interpretation)


def compose(
    text: str, plan: ExecutionPlan, results: list[MathResult], interpretation: Interpretation
) -> MathResult:
    steps = [
        PlanStepResult(
            title=step.title,
            intent=step.intent,
            input=step.input,
            options=dict(step.options),
            result=result,
        )
        for step, result in zip(plan.steps, results, strict=True)
    ]
    done = [step for step in steps if step.result.success]
    details = {
        "function": plan.function,
        "steps": len(steps),
        "calculated": len(done),
    }
    if not done:
        first = steps[0].result.error
        return MathResult(
            success=False,
            intent=IntentName.ASSISTANT,
            input=text,
            details=details,
            error=ResultError(
                code=first.code if first is not None else ErrorCode.INTERNAL_ERROR,
                message="Nenhum dos passos pôde ser calculado; veja o motivo em cada um.",
            ),
            interpretation=interpretation,
            plan=steps,
        )
    summary = "; ".join(
        f"{step.title}: {step.result.result.plain}" for step in done if step.result.result
    )
    counted = f"{len(done)} de {len(steps)} passos calculados"
    return MathResult(
        success=True,
        intent=IntentName.ASSISTANT,
        input=text,
        result=ResultValue(plain=summary, latex=rf"\text{{{counted}}}"),
        details=details,
        verification=summarize(done),
        interpretation=interpretation,
        plan=steps,
    )


def summarize(done: list[PlanStepResult]) -> VerificationReport:
    """Every check of every step (named by the step), under the weakest status."""
    reports = [(step.title, step.result.verification) for step in done]
    checks = [
        check.model_copy(update={"message": f"{title}: {check.message}"})
        for title, report in reports
        if report is not None
        for check in report.checks
    ]
    graded = [(t, r) for t, r in reports if r is not None and r.status in _STRENGTH]
    if not graded:  # e.g. only graphs: their own message says why
        first = next(r for _, r in reports if r is not None)
        return VerificationReport(
            status=VerificationStatus.NOT_APPLICABLE, checks=checks, message=first.message
        )
    status = max((r.status for _, r in graded), key=_STRENGTH.index)
    weakest = [(t, r) for t, r in graded if r.status is status]
    message = _message(status, weakest, every=len(graded) == len(reports))
    return VerificationReport(
        status=status, checks=checks, message=message, reason=weakest[0][1].reason
    )


def _message(
    status: VerificationStatus, weakest: list[tuple[str, VerificationReport]], *, every: bool
) -> str:
    titles = ", ".join(title for title, _ in weakest)
    match status:
        case VerificationStatus.VERIFIED_SYMBOLIC:
            if every:
                return "Todos os passos foram verificados simbolicamente."
            return "Todos os passos com um resultado a conferir foram verificados simbolicamente."
        case VerificationStatus.VERIFIED_NUMERIC:
            return f"Passos verificados; conferido numericamente em: {titles}."
        case VerificationStatus.PARTIAL:
            return f"Verificação parcial em: {titles}. Veja como cada passo foi verificado."
        case _:
            return f"Não foi possível verificar: {titles}."

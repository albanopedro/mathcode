"""Runs the AI step in the API process, before the calculation (ADR 0004).

The AI call is I/O (seconds), not math: it stays out of the worker pool, whose
timeout is for calculations. At most ``CONCURRENCY`` calls run at once.
"""

import asyncio

from app.ai.base import AIError, AIProvider, IntentCandidate
from app.assistant import run_plan
from app.core.errors import ErrorCode
from app.core.workers import WorkerPool
from app.interpreter.planner import ExecutionPlan, PlanStep
from app.models.intents import IntentName
from app.models.result import Interpretation, MathResult, ResultError

CONCURRENCY = 2
# A provider enforces its own timeout; this one only catches a provider that does not.
GRACE = 5.0


class AIService:
    def __init__(self, provider: AIProvider | None, timeout: float) -> None:
        self.provider = provider
        self.timeout = timeout
        self._slots = asyncio.Semaphore(CONCURRENCY)

    async def interpret(self, text: str) -> IntentCandidate:
        if self.provider is None:
            raise AIError("no provider")
        async with self._slots:
            try:
                return await asyncio.wait_for(
                    asyncio.to_thread(self.provider.interpret, text), self.timeout + GRACE
                )
            except TimeoutError as error:
                raise AIError(f"A IA levou mais de {self.timeout:g} s para responder.") from error

    async def calculate(self, text: str, pool: WorkerPool) -> MathResult:
        """Interpret ``text`` with the AI, then calculate it like any typed request."""
        if self.provider is None:
            return _failure(
                text,
                ErrorCode.AI_UNAVAILABLE,
                "A IA não está ativada neste servidor (MATHCODE_AI_PROVIDER). Escreva a "
                'expressão ou use frases como "derivada de x^2".',
            )
        try:
            candidate = await self.interpret(text)
        except AIError as error:
            return _failure(text, ErrorCode.AI_FAILED, str(error))

        interpretation = Interpretation(
            method="ai",
            intent=candidate.intent,
            expression=candidate.expression,
            options=candidate.options,
            provider=self.provider.name,
            model=self.provider.model,
        )
        if candidate.steps and not candidate.clarification:
            # A compound request (ADR 0021): the AI only listed the steps.
            plan = ExecutionPlan(
                tuple(
                    PlanStep(step.title, step.intent, step.expression, dict(step.options))
                    for step in candidate.steps
                ),
                candidate.expression,
                "ai",
            )
            interpretation = interpretation.model_copy(
                update={"intent": IntentName.ASSISTANT, "options": {}}
            )
            return await run_plan(text, plan, pool, interpretation)
        if (
            candidate.intent is None
            or candidate.intent is IntentName.ASSISTANT
            or candidate.clarification
        ):
            return _failure(
                text,
                ErrorCode.AMBIGUOUS_INPUT,
                candidate.clarification or "A IA não entendeu o pedido como uma conta.",
                interpretation,
            )

        # The candidate is calculated exactly like a typed request: the parser,
        # the intent's schema and the verification all apply.
        result = await pool.calculate(
            candidate.expression, candidate.intent, candidate.options or None
        )
        error = result.error
        if error is not None:
            # A position would point into the AI's expression, not what was typed.
            error = error.model_copy(update={"position": None})
        return result.model_copy(
            update={"input": text, "interpretation": interpretation, "error": error}
        )


def _failure(
    text: str, code: ErrorCode, message: str, interpretation: Interpretation | None = None
) -> MathResult:
    return MathResult(
        success=False,
        input=text,
        error=ResultError(code=code, message=message),
        interpretation=interpretation,
    )

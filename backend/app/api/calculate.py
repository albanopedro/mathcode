from typing import Annotated

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field

from app.ai import needs_ai
from app.ai.service import AIService
from app.assistant import ASSISTANT_HELP, run_plan
from app.core.errors import ErrorCode, MathError
from app.core.limits import MAX_INPUT_LENGTH
from app.core.workers import WorkerPool
from app.interpreter.planner import ExecutionPlan, plan_request
from app.models.intents import IntentName, OptionValue
from app.models.result import Interpretation, MathResult, ResultError

router = APIRouter(tags=["calculate"])

# Transport cap. Between MAX_INPUT_LENGTH and this, the pipeline answers with a
# readable INPUT_TOO_LONG; beyond it, the request itself is malformed (422).
MAX_REQUEST_INPUT_LENGTH = 4 * MAX_INPUT_LENGTH

# Math errors are answers (200 with success=false); only these are HTTP failures.
_HTTP_STATUS = {
    ErrorCode.INTERNAL_ERROR: 500,
    ErrorCode.SERVER_BUSY: 503,
}


class CalculateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    input: str = Field(
        max_length=MAX_REQUEST_INPUT_LENGTH,
        description="Expressão ou equação, como '2x + 5 = 17'.",
        examples=["2x + 5 = 17"],
    )
    intent: IntentName | None = Field(
        default=None, description="Operação desejada. Sem valor, é detectada pela entrada."
    )
    options: dict[str, OptionValue] | None = Field(
        default=None,
        max_length=8,
        description=(
            "Parâmetros da operação: variable; order (derivative); lower e upper (integral); "
            "point e side (limit). São validados pelo schema da operação."
        ),
        examples=[{"variable": "x", "order": 2}],
    )
    allow_ai: bool = Field(
        default=False,
        description=(
            "Permite que uma frase que as regras locais não entendem seja interpretada por "
            "IA (o texto é enviado ao modelo configurado no servidor). A IA nunca calcula."
        ),
    )


def get_pool(request: Request) -> WorkerPool:
    return request.app.state.pool


def get_ai(request: Request) -> AIService:
    return request.app.state.ai


@router.post(
    "/calculate",
    response_model=MathResult,
    responses={
        500: {"model": MathResult, "description": "Erro interno (error.code = INTERNAL_ERROR)."},
        503: {"model": MathResult, "description": "Servidor ocupado (error.code = SERVER_BUSY)."},
    },
)
async def post_calculate(
    body: CalculateRequest,
    pool: Annotated[WorkerPool, Depends(get_pool)],
    ai: Annotated[AIService, Depends(get_ai)],
) -> JSONResponse:
    result = await _assistant(body, pool, ai)
    if result is None:
        if body.allow_ai and body.intent is None and body.options is None and needs_ai(body.input):
            result = await ai.calculate(body.input, pool)
        else:
            result = await pool.calculate(body.input, body.intent, body.options)
    status = _HTTP_STATUS.get(result.error.code, 200) if result.error else 200
    return JSONResponse(status_code=status, content=result.model_dump(mode="json"))


async def _assistant(body: CalculateRequest, pool: WorkerPool, ai: AIService) -> MathResult | None:
    """A compound request (Phase 12, ADR 0021), or None to calculate it as usual."""
    asked = body.intent is IntentName.ASSISTANT
    if body.intent is not None and not asked:
        return None
    if body.options is not None or len(body.input) > MAX_INPUT_LENGTH:
        if not asked:
            return None
        message = (
            "O assistente não aceita parâmetros extras."
            if body.options is not None
            else f"A entrada passa de {MAX_INPUT_LENGTH} caracteres."
        )
        return _failure(body.input, ErrorCode.INVALID_INPUT_FOR_INTENT, message)
    try:
        plan = plan_request(body.input)
    except MathError as error:
        return _failure(body.input, error.code, error.message)
    if plan is not None:
        return await run_plan(body.input, plan, pool, _read_by_rules(plan))
    if not asked:
        return None
    if body.allow_ai:
        return await ai.calculate(body.input, pool)
    return _failure(body.input, ErrorCode.INVALID_INPUT_FOR_INTENT, ASSISTANT_HELP)


def _read_by_rules(plan: ExecutionPlan) -> Interpretation:
    return Interpretation(method="rules", intent=IntentName.ASSISTANT, expression=plan.function)


def _failure(text: str, code: ErrorCode, message: str) -> MathResult:
    return MathResult(
        success=False,
        intent=IntentName.ASSISTANT,
        input=text,
        error=ResultError(code=code, message=message),
    )

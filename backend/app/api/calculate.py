from typing import Annotated

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field

from app.ai import needs_ai
from app.ai.service import AIService
from app.core.errors import ErrorCode
from app.core.limits import MAX_INPUT_LENGTH
from app.core.workers import WorkerPool
from app.models.intents import IntentName, OptionValue
from app.models.result import MathResult

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
    if body.allow_ai and body.intent is None and body.options is None and needs_ai(body.input):
        result = await ai.calculate(body.input, pool)
    else:
        result = await pool.calculate(body.input, body.intent, body.options)
    status = _HTTP_STATUS.get(result.error.code, 200) if result.error else 200
    return JSONResponse(status_code=status, content=result.model_dump(mode="json"))

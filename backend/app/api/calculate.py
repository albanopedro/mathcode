from typing import Annotated

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field

from app.core.errors import ErrorCode
from app.core.limits import MAX_INPUT_LENGTH
from app.core.workers import WorkerPool
from app.models.intents import IntentName
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


def get_pool(request: Request) -> WorkerPool:
    return request.app.state.pool


@router.post(
    "/calculate",
    response_model=MathResult,
    responses={
        500: {"model": MathResult, "description": "Erro interno (error.code = INTERNAL_ERROR)."},
        503: {"model": MathResult, "description": "Servidor ocupado (error.code = SERVER_BUSY)."},
    },
)
async def post_calculate(
    body: CalculateRequest, pool: Annotated[WorkerPool, Depends(get_pool)]
) -> JSONResponse:
    result = await pool.calculate(body.input, body.intent)
    status = _HTTP_STATUS.get(result.error.code, 200) if result.error else 200
    return JSONResponse(status_code=status, content=result.model_dump(mode="json"))

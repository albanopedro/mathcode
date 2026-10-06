"""The single response shape of the math pipeline (docs/architecture.md, section 4)."""

from enum import StrEnum
from typing import Any, Self

from pydantic import BaseModel, Field, model_validator

from app.core.errors import ErrorCode
from app.core.notices import NoticeCode
from app.models.intents import IntentName


class VerificationStatus(StrEnum):
    VERIFIED_SYMBOLIC = "verified_symbolic"
    VERIFIED_NUMERIC = "verified_numeric"
    PARTIAL = "partial"
    UNVERIFIED = "unverified"
    NOT_APPLICABLE = "not_applicable"
    FAILED = "failed"


class VerificationReport(BaseModel):
    status: VerificationStatus
    method: str
    checks: list[str] = Field(default_factory=list)
    message: str


class ResultValue(BaseModel):
    plain: str
    latex: str
    approx: str | None = None


class Step(BaseModel):
    description: str
    latex: str | None = None


class ResultWarning(BaseModel):
    code: NoticeCode
    message: str


class ResultError(BaseModel):
    code: ErrorCode
    message: str
    position: int | None = None  # index into ``input``


class MathResult(BaseModel):
    success: bool
    intent: IntentName | None = None
    input: str
    normalized_input: str | None = None
    result: ResultValue | None = None
    # Stays empty until real step-by-step rules exist (docs/architecture.md).
    steps: list[Step] = Field(default_factory=list)
    details: dict[str, Any] = Field(default_factory=dict)
    verification: VerificationReport | None = None
    warnings: list[ResultWarning] = Field(default_factory=list)
    error: ResultError | None = None

    @model_validator(mode="after")
    def _consistent(self) -> Self:
        if self.success:
            if self.error is not None or self.result is None or self.verification is None:
                raise ValueError("a successful result needs a value and a verification, no error")
            if self.verification.status is VerificationStatus.FAILED:
                raise ValueError("a failed verification cannot be presented as a success")
        elif self.error is None or self.result is not None:
            raise ValueError("a failed result needs an error and no value")
        return self

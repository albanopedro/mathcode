"""The single response shape of the math pipeline (docs/architecture.md, section 4)."""

from enum import StrEnum
from typing import Any, Literal, Self

from pydantic import BaseModel, Field, computed_field, model_validator

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


class CheckKind(StrEnum):
    """The strategy behind one check (ADR 0010)."""

    SYMBOLIC = "symbolic"  # exact algebra: a difference reduces to 0, an exact product
    SUBSTITUTION = "substitution"  # a solution put back into the original
    NUMERIC = "numeric"  # the independent evaluator, quadrature, finite differences
    COMPARISON = "comparison"  # a second, different method reaches the same result
    COMPLETENESS = "completeness"  # nothing is missing (Sturm, ranks)
    DOMAIN = "domain"  # the result exists where the original does
    EXECUTION = "execution"  # the verification run itself (time limit, internal error)


class CheckOutcome(StrEnum):
    PASSED = "passed"
    FAILED = "failed"
    INCONCLUSIVE = "inconclusive"


class ReasonCode(StrEnum):
    """Why a result is only partially verified, or not verified at all."""

    COMPLETENESS_NOT_PROVED = "completeness_not_proved"  # right, but maybe not all
    NUMERIC_EVIDENCE_ONLY = "numeric_evidence_only"  # evidence, not proof (limits)
    FEW_POINTS = "few_points"  # not enough points of the domain to compare
    TOO_LARGE = "too_large"  # beyond the independent evaluator's precision
    INCONCLUSIVE = "inconclusive"  # the check ran and could not decide
    NO_STRATEGY = "no_strategy"  # this kind of result has no check (divergence...)
    DEADLINE = "deadline"  # the verification did not finish in time
    INTERNAL_ERROR = "internal_error"  # the verification itself broke


class VerificationCheck(BaseModel):
    kind: CheckKind
    outcome: CheckOutcome
    message: str


class VerificationReport(BaseModel):
    """What was checked and what it proves (ADR 0003, ADR 0010).

    The status must agree with the checks: a failed check means ``failed``; a
    verified result has no failed check; ``partial`` and ``unverified`` say why.
    """

    status: VerificationStatus
    checks: list[VerificationCheck] = Field(min_length=1)
    message: str
    reason: ReasonCode | None = None

    @computed_field
    @property
    def methods(self) -> list[CheckKind]:
        """The strategies used, in the order they first appear."""
        return list(dict.fromkeys(check.kind for check in self.checks))

    @model_validator(mode="after")
    def _status_matches_checks(self) -> Self:
        outcomes = {check.outcome for check in self.checks}
        failed = CheckOutcome.FAILED in outcomes
        match self.status:
            case VerificationStatus.FAILED:
                if not failed:
                    raise ValueError("a failed verification needs a failed check")
            case VerificationStatus.VERIFIED_SYMBOLIC | VerificationStatus.VERIFIED_NUMERIC:
                if failed or CheckOutcome.PASSED not in outcomes:
                    raise ValueError("a verified result needs passed checks and no failed one")
            case VerificationStatus.PARTIAL:
                if failed or outcomes != {CheckOutcome.PASSED, CheckOutcome.INCONCLUSIVE}:
                    raise ValueError("a partial verification has passed and inconclusive checks")
            case VerificationStatus.UNVERIFIED | VerificationStatus.NOT_APPLICABLE:
                if failed:
                    raise ValueError("a failed check means the verification failed")
        needs_reason = self.status in (VerificationStatus.PARTIAL, VerificationStatus.UNVERIFIED)
        if needs_reason != (self.reason is not None):
            raise ValueError("partial and unverified results, and only they, carry a reason")
        return self


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


class Interpretation(BaseModel):
    """How a request in words was understood, so the user can check it."""

    method: Literal["rules", "ai"]
    intent: IntentName | None = None
    expression: str  # the math text that was calculated
    options: dict[str, str | int] = Field(default_factory=dict)
    provider: str | None = None  # AI only, e.g. "opencode"
    model: str | None = None  # AI only


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
    # Set when the request was a phrase (Phase 8); None for plain math.
    interpretation: Interpretation | None = None

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

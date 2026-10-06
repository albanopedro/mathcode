import pytest
from pydantic import ValidationError

from app.core.errors import ErrorCode
from app.models.result import (
    MathResult,
    ResultError,
    ResultValue,
    VerificationReport,
    VerificationStatus,
)

VALUE = ResultValue(plain="4", latex="4")
VERIFIED = VerificationReport(
    status=VerificationStatus.VERIFIED_NUMERIC, method="independent_numeric", message="ok"
)
ERROR = ResultError(code=ErrorCode.PARSE_ERROR, message="erro")


def test_valid_success_and_failure() -> None:
    MathResult(success=True, input="2+2", result=VALUE, verification=VERIFIED)
    MathResult(success=False, input="2+", error=ERROR)


@pytest.mark.parametrize(
    "fields",
    [
        {"success": True, "result": VALUE},  # no verification
        {"success": True, "verification": VERIFIED},  # no value
        {"success": True, "result": VALUE, "verification": VERIFIED, "error": ERROR},
        {
            "success": True,
            "result": VALUE,
            "verification": VERIFIED.model_copy(update={"status": VerificationStatus.FAILED}),
        },
        {"success": False},  # no error
        {"success": False, "error": ERROR, "result": VALUE},  # failure with a value
    ],
)
def test_inconsistent_results_are_rejected(fields: dict[str, object]) -> None:
    with pytest.raises(ValidationError):
        MathResult.model_validate({"input": "x", **fields})


def test_serializes_enums_as_strings() -> None:
    data = MathResult(success=False, input="", error=ERROR).model_dump(mode="json")
    assert data["error"] == {"code": "PARSE_ERROR", "message": "erro", "position": None}
    assert data["steps"] == []

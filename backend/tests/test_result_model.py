import pytest
from pydantic import ValidationError

from app.core.errors import ErrorCode
from app.models.result import (
    CheckKind,
    CheckOutcome,
    MathResult,
    ReasonCode,
    ResultError,
    ResultValue,
    VerificationCheck,
    VerificationReport,
    VerificationStatus,
)

VALUE = ResultValue(plain="4", latex="4")
PASSED = VerificationCheck(kind=CheckKind.NUMERIC, outcome=CheckOutcome.PASSED, message="ok")
FAILED = VerificationCheck(kind=CheckKind.SYMBOLIC, outcome=CheckOutcome.FAILED, message="não")
OPEN = VerificationCheck(
    kind=CheckKind.COMPLETENESS, outcome=CheckOutcome.INCONCLUSIVE, message="talvez"
)
VERIFIED = VerificationReport(
    status=VerificationStatus.VERIFIED_NUMERIC, checks=[PASSED], message="ok"
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


S = VerificationStatus


@pytest.mark.parametrize(
    ("status", "checks", "reason"),
    [
        (S.VERIFIED_SYMBOLIC, [PASSED], None),
        (S.VERIFIED_NUMERIC, [PASSED, OPEN], None),  # an extra check that did not decide
        (S.PARTIAL, [PASSED, OPEN], ReasonCode.COMPLETENESS_NOT_PROVED),
        (S.UNVERIFIED, [OPEN], ReasonCode.DEADLINE),
        (S.NOT_APPLICABLE, [PASSED], None),
        (S.FAILED, [PASSED, FAILED], None),
    ],
)
def test_reports_whose_status_matches_the_checks(
    status: VerificationStatus, checks: list[VerificationCheck], reason: ReasonCode | None
) -> None:
    VerificationReport(status=status, checks=checks, message="m", reason=reason)


@pytest.mark.parametrize(
    ("status", "checks", "reason"),
    [
        (S.VERIFIED_SYMBOLIC, [], None),  # no check at all
        (S.FAILED, [PASSED], None),  # failed, but no check failed
        (S.VERIFIED_SYMBOLIC, [PASSED, FAILED], None),  # verified despite a failed check
        (S.VERIFIED_NUMERIC, [OPEN], None),  # verified with nothing passed
        (S.PARTIAL, [PASSED], ReasonCode.INCONCLUSIVE),  # partial, but nothing left open
        (S.PARTIAL, [OPEN], ReasonCode.INCONCLUSIVE),  # partial, but nothing passed
        (S.PARTIAL, [PASSED, OPEN], None),  # partial without saying why
        (S.UNVERIFIED, [OPEN], None),  # unverified without saying why
        (S.UNVERIFIED, [FAILED], ReasonCode.INCONCLUSIVE),  # a failed check is a failure
        (S.VERIFIED_NUMERIC, [PASSED], ReasonCode.DEADLINE),  # a reason without a gap
    ],
)
def test_reports_whose_status_contradicts_the_checks(
    status: VerificationStatus, checks: list[VerificationCheck], reason: ReasonCode | None
) -> None:
    with pytest.raises(ValidationError):
        VerificationReport(status=status, checks=checks, message="m", reason=reason)


def test_methods_list_the_strategies_in_order() -> None:
    report = VerificationReport(
        status=S.PARTIAL,
        checks=[PASSED, OPEN, PASSED.model_copy(update={"kind": CheckKind.SUBSTITUTION}), PASSED],
        message="m",
        reason=ReasonCode.COMPLETENESS_NOT_PROVED,
    )

    data = report.model_dump(mode="json")

    assert data["methods"] == ["numeric", "completeness", "substitution"]
    assert data["checks"][1] == {
        "kind": "completeness",
        "outcome": "inconclusive",
        "message": "talvez",
    }
    # What the API sends can be read back (the worker sends JSON to the server).
    assert VerificationReport.model_validate(data) == report

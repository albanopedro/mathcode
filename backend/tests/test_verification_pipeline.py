"""The verification inside the pipeline: time budget, internal errors (ADR 0010)."""

import logging
import time
from dataclasses import replace

import pytest

from app.calculator import calculate
from app.interpreter.registry import REGISTRY
from app.models.intents import IntentName
from app.models.result import VerificationStatus


def test_a_verification_out_of_time_leaves_the_result_unverified(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    spec = REGISTRY[IntentName.ARITHMETIC]

    def slow(outcome: object) -> None:
        time.sleep(5)

    monkeypatch.setitem(REGISTRY, IntentName.ARITHMETIC, replace(spec, verify=slow))

    started = time.monotonic()
    result = calculate("2 + 2", verify_until=time.monotonic() + 0.2)

    assert time.monotonic() - started < 2
    assert result.success  # the result is kept...
    assert result.result is not None and result.result.plain == "4"
    assert result.verification is not None  # ...and says it was not checked
    assert result.verification.status is VerificationStatus.UNVERIFIED
    assert result.verification.reason == "deadline"
    assert result.verification.methods == ["execution"]
    assert "não terminou a tempo" in result.verification.message


def test_a_broken_verification_leaves_the_result_unverified(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    spec = REGISTRY[IntentName.ARITHMETIC]

    def broken(outcome: object) -> None:
        raise RuntimeError("bug")

    monkeypatch.setitem(REGISTRY, IntentName.ARITHMETIC, replace(spec, verify=broken))

    with caplog.at_level(logging.ERROR):
        result = calculate("2 + 2")

    assert result.success
    assert result.verification is not None
    assert result.verification.status is VerificationStatus.UNVERIFIED
    assert result.verification.reason == "internal_error"
    assert "verification of arithmetic failed" in caplog.text  # logged for the developer


def test_no_budget_means_no_limit() -> None:
    result = calculate("2 + 2", verify_until=None)
    assert result.verification is not None
    assert result.verification.status is VerificationStatus.VERIFIED_SYMBOLIC


def test_the_timer_is_disarmed_after_verification() -> None:
    calculate("2 + 2", verify_until=time.monotonic() + 0.2)
    time.sleep(0.4)  # an armed timer would interrupt this
    assert calculate("3 * 3").success


def test_algebraic_roots_are_verified_quickly() -> None:
    """Simplifying a substituted CRootOf took over 20 s; divisibility is exact and fast."""
    started = time.monotonic()
    result = calculate("x^20 - 3x^7 + 1 = 0")
    elapsed = time.monotonic() - started

    assert result.verification is not None
    assert result.verification.status is VerificationStatus.VERIFIED_SYMBOLIC
    assert elapsed < 3

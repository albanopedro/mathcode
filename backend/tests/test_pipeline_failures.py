"""What the pipeline does when a step misbehaves: never show an unconfirmed result."""

import logging
from dataclasses import replace

import pytest
import sympy as sp

from app.calculator import calculate
from app.core.errors import ErrorCode
from app.interpreter import registry
from app.math_engine.arithmetic import ArithmeticOutcome
from app.models.intents import ArithmeticParams, IntentName
from app.models.result import VerificationStatus


def test_a_result_the_verifier_rejects_is_not_shown(monkeypatch: pytest.MonkeyPatch) -> None:
    spec = registry.REGISTRY[IntentName.ARITHMETIC]

    def wrong_engine(params: ArithmeticParams) -> ArithmeticOutcome:
        return replace(spec.execute(params), value=sp.Integer(5))

    monkeypatch.setitem(
        registry.REGISTRY, IntentName.ARITHMETIC, replace(spec, execute=wrong_engine)
    )
    result = calculate("2 + 2")

    assert not result.success
    assert result.result is None
    assert result.error is not None
    assert result.error.code is ErrorCode.VERIFICATION_FAILED
    assert result.verification is not None
    assert result.verification.status is VerificationStatus.FAILED
    assert result.normalized_input == "2 + 2"


def test_unexpected_exceptions_become_internal_errors(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    spec = registry.REGISTRY[IntentName.ARITHMETIC]

    def broken_engine(params: ArithmeticParams) -> ArithmeticOutcome:
        raise RuntimeError("boom")

    monkeypatch.setitem(
        registry.REGISTRY, IntentName.ARITHMETIC, replace(spec, execute=broken_engine)
    )
    with caplog.at_level(logging.ERROR):
        result = calculate("2 + 2")

    assert not result.success
    assert result.error is not None
    assert result.error.code is ErrorCode.INTERNAL_ERROR
    assert "boom" not in result.error.message  # internals are logged, not shown
    assert "boom" in caplog.text

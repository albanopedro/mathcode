"""The clickable examples of the interface (ADR 0024) must work with the real engine."""

import re
from pathlib import Path

import pytest

from app.calculator import calculate

SOURCE = Path(__file__).parents[2] / "frontend" / "src" / "utils" / "examples.ts"
EXAMPLES = re.findall(r'subject: "([^"]+)", text: "([^"]+)"', SOURCE.read_text(encoding="utf-8"))


def test_the_examples_were_found() -> None:
    assert len(EXAMPLES) >= 10


@pytest.mark.parametrize(("subject", "text"), EXAMPLES)
def test_an_example_is_calculated_and_verified(subject: str, text: str) -> None:
    result = calculate(text)
    assert result.success, f"{subject}: {result.error}"
    assert result.verification is not None
    assert result.verification.status.value != "failed"

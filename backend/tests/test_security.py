"""Rule 16: user input never becomes executable code (ADR 0002).

It also never freezes the server (ADR 0026): a long list used to make the rules
backtrack for an exponential time.
"""

import contextlib
import re
import time
from pathlib import Path

import pytest

from app.calculator import calculate
from app.core.errors import MathError
from app.interpreter.language import match_language

APP = Path(__file__).resolve().parents[1] / "app"

# Calls that execute text, directly or through SymPy. The builtins count only
# when called bare: re.compile(...) builds a regex and executes nothing.
FORBIDDEN = re.compile(
    r"(?<![\w.])(eval|exec|compile|__import__)\s*\("
    r"|\b(sympify|parse_expr|lambdify)\s*\("
)


def test_the_guard_itself() -> None:
    for bad in [
        "eval(x)",
        "exec (code)",
        "compile(src, 'f', 'exec')",
        "sp.sympify(t)",
        "sympy.parse_expr(t)",
        "lambdify(x, e)",
        "__import__('os')",
    ]:
        assert FORBIDDEN.search(bad), bad
    for fine in ["re.compile(r'x')", "pattern.compile(", "evaluate(tree)", "medieval(x)"]:
        assert not FORBIDDEN.search(fine), fine


def test_no_code_executing_calls_in_the_app() -> None:
    offenders = [
        f"{path.relative_to(APP)}:{number}: {line.strip()}"
        for path in APP.rglob("*.py")
        for number, line in enumerate(path.read_text().splitlines(), start=1)
        if FORBIDDEN.search(line)
    ]
    assert offenders == []


def test_sympy_strings_are_never_passed_to_constructors() -> None:
    """``S("...")`` and ``Symbol``-from-text helpers also go through sympify."""
    pattern = re.compile(r"\bsp\.S\(|\bsympy\.S\(|\bS\(\s*[\"']")
    offenders = [str(path) for path in APP.rglob("*.py") if pattern.search(path.read_text())]
    assert offenders == []


@pytest.mark.parametrize(
    "text",
    [
        "__import__('os').system('ls')",
        "eval('2+2')",
        "exec('x=1')",
        "lambda: 1",
        "().__class__",
        "x.__class__",
        "open('/etc/passwd')",
        "import os",
        "os.system('rm -rf /')",
        "Symbol('x')",
        "sympify('2')",
        "S('2')",
        "2; import os",
        "$(ls)",
        "`ls`",
        "{{7*7}}",
        "${7*7}",
        "<script>alert(1)</script>",
        "1' OR '1'='1",
        "\x00",
    ],
)
def test_malicious_input_is_rejected_as_a_math_error(text: str) -> None:
    result = calculate(text)
    assert not result.success
    assert result.error is not None
    assert result.error.code.value != "INTERNAL_ERROR"


def test_a_long_list_does_not_freeze_the_rules() -> None:
    """The list of values is read by a regex that used to backtrack exponentially.

    Every item had two ways to take the blank before it, so the regex tried all
    of them: 150 items meant 2^150 ways to read the same text (ADR 0026).
    """
    payload = "media " + "; ".join(["1"] * 150) + ","
    start = time.monotonic()
    with contextlib.suppress(MathError):
        # The rules may recognize it and refuse it: that is the right answer.
        match_language(payload)
    # The broken regex needed more than the age of the universe here.
    assert time.monotonic() - start < 2.0


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("media 1", "1"),
        ("media 1; 2", "1; 2"),
        ("media 1, 2", "1, 2"),
        ("media 10, 20 e 30", "10, 20; 30"),
        ("media 2,5; 3,5", "2,5; 3,5"),
        ("media 1/2; 3/4", "1/2; 3/4"),
        ("media -1; +2", "-1; +2"),
    ],
)
def test_the_list_of_values_is_still_read_the_same_way(text: str, expected: str) -> None:
    """The fix for the backtracking must not change what the rules understand."""
    found = match_language(text)
    assert found is not None
    assert found.intent is not None
    assert found.text == expected
    assert found.options == {"measure": "mean"}

"""Rule 16: user input never becomes executable code (ADR 0002)."""

import re
from pathlib import Path

import pytest

from app.calculator import calculate

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

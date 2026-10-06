import pytest

from app.calculator import calculate
from app.core.errors import ErrorCode
from app.core.notices import NoticeCode
from app.models.intents import IntentName
from app.models.result import VerificationStatus


def test_derived_example_from_the_spec() -> None:
    result = calculate("2x + 5 = 17")

    assert result.success
    assert result.intent is IntentName.SOLVE_EQUATION
    assert result.input == "2x + 5 = 17"
    assert result.normalized_input == "2*x + 5 = 17"
    assert result.result is not None
    assert result.result.plain == "x = 6"
    assert result.result.latex == "x = 6"
    assert result.details == {"variable": "x", "solution_set": "unique", "solutions": ["6"]}
    assert result.verification is not None
    assert result.verification.status is VerificationStatus.VERIFIED_SYMBOLIC
    assert result.steps == []
    assert result.error is None


@pytest.mark.parametrize(
    ("text", "intent", "plain", "approx"),
    [
        ("2 + 2", IntentName.ARITHMETIC, "4", None),
        ("0.1 + 0.2", IntentName.ARITHMETIC, "3/10", "0.3"),
        ("1/3", IntentName.ARITHMETIC, "1/3", "0.333333333333333"),
        ("sqrt(8)", IntentName.ARITHMETIC, "2*sqrt(2)", "2.82842712474619"),
        ("sen(30°)", IntentName.ARITHMETIC, "1/2", "0.5"),
        ("e^2", IntentName.ARITHMETIC, "exp(2)", "7.38905609893065"),
        ("10^3999 + 1 - 10^3999", IntentName.ARITHMETIC, "1", None),
        ("x² + 2x + x²", IntentName.SIMPLIFY, "2*x*(x + 1)", None),
        ("sqrt(x^2)", IntentName.SIMPLIFY, "abs(x)", None),
        ("(x + 1)^2 = x^2", IntentName.SOLVE_EQUATION, "x = -1/2", "-0.5"),
        ("x + 1 = x + 2", IntentName.SOLVE_EQUATION, "∅", None),
        ("2(x + 1) = 2x + 2", IntentName.SOLVE_EQUATION, "x ∈ ℝ", None),
    ],
)
def test_detects_intent_and_formats(
    text: str, intent: IntentName, plain: str, approx: str | None
) -> None:
    result = calculate(text)
    assert result.success, result.error
    assert result.intent is intent
    assert result.result is not None
    assert result.result.plain == plain
    assert result.result.approx == approx


def test_latex_output() -> None:
    result = calculate("sqrt(x^2) + 1/2")
    assert result.result is not None
    assert result.result.latex == r"\left|{x}\right| + \frac{1}{2}"


def test_every_success_is_verified_or_says_it_is_not() -> None:
    for text in ["2 + 2", "x + x", "2x = 4", "sqrt(x - 1000)"]:
        result = calculate(text)
        assert result.success
        assert result.verification is not None
        assert result.verification.message


def test_unverifiable_result_is_reported_honestly() -> None:
    result = calculate("sqrt(x - 1000)")
    assert result.success
    assert result.verification is not None
    assert result.verification.status is VerificationStatus.UNVERIFIED


def test_explicit_intent() -> None:
    result = calculate("x + x", intent="simplify")
    assert result.intent is IntentName.SIMPLIFY
    mismatch = calculate("x + 1", intent="arithmetic")
    assert not mismatch.success
    assert mismatch.error is not None
    assert mismatch.error.code is ErrorCode.INVALID_INPUT_FOR_INTENT


def test_unknown_intent() -> None:
    result = calculate("2 + 2", intent="derivative")
    assert not result.success
    assert result.error is not None
    assert result.error.code is ErrorCode.UNSUPPORTED_INTENT


def test_warnings_are_reported_once() -> None:
    result = calculate("log(10) + log(100)")
    assert [w.code for w in result.warnings] == [NoticeCode.LOG_BASE_10]


def test_letter_before_parenthesis_is_a_product_with_a_warning() -> None:
    result = calculate("f(x)")
    assert result.success
    assert result.normalized_input == "f*x"
    assert [w.code for w in result.warnings] == [NoticeCode.AMBIGUOUS_IMPLICIT_MULTIPLICATION]
    assert "f(x)" in result.warnings[0].message


def test_domain_change_warning() -> None:
    result = calculate("(x^2 - 1)/(x - 1)")
    assert result.result is not None and result.result.plain == "x + 1"
    assert [w.code for w in result.warnings] == [NoticeCode.DOMAIN_CHANGED]


@pytest.mark.parametrize(
    ("text", "code"),
    [
        ("", ErrorCode.EMPTY_INPUT),
        ("   ", ErrorCode.EMPTY_INPUT),
        ("1" * 501, ErrorCode.INPUT_TOO_LONG),
        ("2 +", ErrorCode.PARSE_ERROR),
        ("1,2,3", ErrorCode.AMBIGUOUS_INPUT),
        ("abc", ErrorCode.UNKNOWN_SYMBOL),
        ("foo(2)", ErrorCode.UNKNOWN_FUNCTION),
        ("1/0", ErrorCode.DIVISION_BY_ZERO),
        ("sqrt(-9)", ErrorCode.DOMAIN_ERROR),
        ("log(0)", ErrorCode.DOMAIN_ERROR),
        ("10^5000", ErrorCode.LIMIT_EXCEEDED),
        ("x^2 = 4", ErrorCode.UNSUPPORTED_FEATURE),
        ("2i", ErrorCode.UNSUPPORTED_FEATURE),
    ],
)
def test_errors(text: str, code: ErrorCode) -> None:
    result = calculate(text)
    assert not result.success
    assert result.result is None
    assert result.error is not None
    assert result.error.code is code
    assert result.error.message

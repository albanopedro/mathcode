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
    assert result.details == {
        "variable": "x",
        "solution_set": "finite",
        "solutions": ["6"],
        "multiplicities": [1],
    }
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
    result = calculate("2 + 2", intent="teleport")
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
        ("sin(x) = 0", ErrorCode.UNSUPPORTED_FEATURE),
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


# -- Phase 5: algebra ------------------------------------------------------------------


@pytest.mark.parametrize(
    ("text", "intent", "plain", "latex"),
    [
        ("x^2 - 4", "factor", "(x - 2)*(x + 2)", r"\left(x - 2\right) \left(x + 2\right)"),
        ("360", "factor", "2^3 * 3^2 * 5", r"2^{3} \cdot 3^{2} \cdot 5"),
        ("-84", "factor", "-2^2 * 3 * 7", r"-2^{2} \cdot 3 \cdot 7"),
        ("(x + 1)^3", "expand", "x^3 + 3*x^2 + 3*x + 1", "x^{3} + 3 x^{2} + 3 x + 1"),
        (
            "(x^3 + 2x + 5)/(x^2 + 1)",
            "polynomial_division",
            "quociente: x; resto: x + 5",
            r"Q(x) = x, \quad R(x) = x + 5",
        ),
    ],
)
def test_explicit_algebra_intents(text: str, intent: str, plain: str, latex: str) -> None:
    result = calculate(text, intent=intent)
    assert result.success, result.error
    assert result.result is not None
    assert (result.result.plain, result.result.latex) == (plain, latex)
    assert result.verification is not None
    assert result.verification.status is VerificationStatus.VERIFIED_SYMBOLIC


def test_rewrite_details_say_whether_anything_changed() -> None:
    assert calculate("x^2 - 4", intent="factor").details == {"changed": True}
    assert calculate("x^2 - 2", intent="factor").details == {"changed": False}


def test_prime_factorization_details() -> None:
    details = calculate("360", intent="factor").details
    assert details["prime_factors"] == [
        {"prime": "2", "exponent": 3},
        {"prime": "3", "exponent": 2},
        {"prime": "5", "exponent": 1},
    ]


def test_division_details() -> None:
    details = calculate("(x^3 - 1)/(x - 1)", intent="polynomial_division").details
    assert details == {"variable": "x", "quotient": "x^2 + x + 1", "remainder": "0", "exact": True}


@pytest.mark.parametrize(
    ("text", "plain", "approx", "status"),
    [
        ("x^2 - 5x + 6 = 0", "x = 2 ou x = 3", None, VerificationStatus.VERIFIED_SYMBOLIC),
        (
            "x^2 = 2",
            "x = -sqrt(2) ou x = sqrt(2)",
            "-1.4142135623731; 1.4142135623731",
            VerificationStatus.VERIFIED_SYMBOLIC,
        ),
        ("x/x = 1", "x ∈ ℝ, x ≠ 0", None, VerificationStatus.VERIFIED_SYMBOLIC),
        ("sqrt(x + 2) = x", "x = 2", None, VerificationStatus.PARTIAL),
    ],
)
def test_equations(text: str, plain: str, approx: str | None, status: VerificationStatus) -> None:
    result = calculate(text)
    assert result.intent is IntentName.SOLVE_EQUATION
    assert result.result is not None
    assert (result.result.plain, result.result.approx) == (plain, approx)
    assert result.verification is not None and result.verification.status is status


def test_roots_without_radicals_are_shown_approximately() -> None:
    result = calculate("x^3 = 3x - 1")
    assert result.result is not None
    assert result.result.plain.startswith("x ≈ -1.87938524157182 ou")
    assert r"\approx" in result.result.latex
    assert [w.code for w in result.warnings] == [NoticeCode.ROOTS_SHOWN_APPROXIMATELY]


def test_double_root_multiplicity_in_details() -> None:
    details = calculate("x^2 - 2x + 1 = 0").details
    assert details["solutions"] == ["1"]
    assert details["multiplicities"] == [2]


@pytest.mark.parametrize(
    ("text", "plain", "latex", "solution_set"),
    [
        (
            "x + y = 3; x - y = 1",
            "x = 2; y = 1",
            r"\begin{cases} x = 2 \\ y = 1 \end{cases}",
            "unique",
        ),
        (
            "x + y = 3; 2x + 2y = 6",
            "x = 3 - y; y ∈ ℝ",
            r"\begin{cases} x = 3 - y \\ y \in \mathbb{R} \end{cases}",
            "infinite",
        ),
        ("x + y = 3; x + y = 4", "∅", r"\varnothing", "none"),
    ],
)
def test_systems(text: str, plain: str, latex: str, solution_set: str) -> None:
    result = calculate(text)
    assert result.intent is IntentName.SOLVE_SYSTEM
    assert result.result is not None
    assert (result.result.plain, result.result.latex) == (plain, latex)
    assert result.details["solution_set"] == solution_set
    assert result.verification is not None
    assert result.verification.status is VerificationStatus.VERIFIED_SYMBOLIC


def test_several_roots_are_one_per_line_in_latex() -> None:
    """One line of roots does not fit a phone screen (seen in the browser, Phase 5)."""
    result = calculate("x^2 - 5x + 6 = 0")
    assert result.result is not None
    assert result.result.latex == r"\begin{aligned} x_{1} & = 2 \\ x_{2} & = 3 \end{aligned}"
    single = calculate("2x + 5 = 17")
    assert single.result is not None and single.result.latex == "x = 6"


# -- Phase 6: calculus -----------------------------------------------------------------


@pytest.mark.parametrize(
    ("text", "intent", "options", "plain", "latex", "status"),
    [
        (
            "x^2 sin(x)",
            "derivative",
            {"order": 2},
            "-x^2*sin(x) + 4*x*cos(x) + 2*sin(x)",
            r"- x^{2} \sin{\left(x \right)} + 4 x \cos{\left(x \right)} + 2 \sin{\left(x \right)}",
            VerificationStatus.VERIFIED_NUMERIC,
        ),
        (
            "1/x",
            "integral",
            None,
            "log(abs(x)) + C",
            r"\log{\left(\left|{x}\right| \right)} + C",
            VerificationStatus.VERIFIED_SYMBOLIC,
        ),
        (
            "x^2",
            "integral",
            {"lower": "0", "upper": "1"},
            "1/3",
            r"\frac{1}{3}",
            VerificationStatus.VERIFIED_NUMERIC,
        ),
        (
            "1/x",
            "integral",
            {"lower": "1", "upper": "inf"},
            "∞",
            r"\infty",
            VerificationStatus.UNVERIFIED,
        ),
        ("sin(x)/x", "limit", {"point": "0"}, "1", "1", VerificationStatus.PARTIAL),
        ("1/x^2", "limit", {"point": "0"}, "∞", r"\infty", VerificationStatus.PARTIAL),
        ("1/x", "limit", {"point": "0"}, "não existe", r"\nexists", VerificationStatus.PARTIAL),
    ],
)
def test_calculus(
    text: str,
    intent: str,
    options: dict | None,
    plain: str,
    latex: str,
    status: VerificationStatus,
) -> None:
    result = calculate(text, intent, options)
    assert result.success, result.error
    assert result.result is not None
    assert (result.result.plain, result.result.latex) == (plain, latex)
    assert result.verification is not None
    assert result.verification.status is status


def test_calculus_details() -> None:
    assert calculate("x^3", "derivative", {"order": 2}).details == {"variable": "x", "order": 2}
    assert calculate("x^2", "integral").details == {"variable": "x", "definite": False}
    assert calculate("x^2", "integral", {"lower": "0", "upper": "inf"}).details == {
        "variable": "x",
        "definite": True,
        "lower": "0",
        "upper": "∞",
        "converges": False,
    }
    assert calculate("abs(x)/x", "limit", {"point": "0"}).details == {
        "variable": "x",
        "point": "0",
        "side": "both",
        "requested_side": "both",
        "exists": False,
        "oscillates": False,
        "left": "-1",
        "right": "1",
    }


def test_one_sided_domain_shows_in_details_and_warnings() -> None:
    result = calculate("sqrt(x)", "limit", {"point": "0"})
    assert result.details["side"] == "right"
    assert result.details["requested_side"] == "both"
    assert [w.code for w in result.warnings] == [NoticeCode.ONE_SIDED_DOMAIN]


def test_invalid_options_are_answers() -> None:
    result = calculate("x^2", "derivative", {"order": 99})
    assert not result.success
    assert result.error is not None
    assert result.error.code is ErrorCode.INVALID_INPUT_FOR_INTENT
    assert "ordem" in result.error.message


# -- Phase 7: graphs ---------------------------------------------------------------------


@pytest.mark.parametrize(
    ("text", "plain", "latex"),
    [
        ("y = x^2 - 4x + 3", "y = x^2 - 4*x + 3", "y = x^{2} - 4 x + 3"),
        (
            "x^2; 2x + 1",
            "y = x^2; y = 2*x + 1",
            r"\begin{aligned} y_{1} &= x^{2} \\ y_{2} &= 2 x + 1 \end{aligned}",
        ),
    ],
)
def test_graphs_are_detected(text: str, plain: str, latex: str) -> None:
    result = calculate(text)
    assert result.intent is IntentName.GRAPH
    assert result.result is not None
    assert (result.result.plain, result.result.latex) == (plain, latex)


def test_graph_details() -> None:
    details = calculate("x^2 - 4x + 3", "graph", {"x_min": "0", "x_max": "4"}).details
    assert details["variable"] == "x"
    assert details["x_range"] == [0.0, 4.0]
    assert details["x_range_text"] == ["0", "4"]
    (function,) = details["functions"]
    assert function["label"] == "x^2 - 4*x + 3"
    assert len(function["x"]) == len(function["y"])
    assert details["points"] == [
        {
            "function": 0,
            "kind": "root",
            "x": "1",
            "y": "0",
            "x_value": 1.0,
            "y_value": 0.0,
            "exact": True,
        },
        {
            "function": 0,
            "kind": "root",
            "x": "3",
            "y": "0",
            "x_value": 3.0,
            "y_value": 0.0,
            "exact": True,
        },
        {
            "function": 0,
            "kind": "y_intercept",
            "x": "0",
            "y": "3",
            "x_value": 0.0,
            "y_value": 3.0,
            "exact": True,
        },
    ]


def test_graph_gaps_are_null_in_json() -> None:
    result = calculate("sqrt(x)", "graph")
    data = result.model_dump(mode="json")
    assert None in data["details"]["functions"][0]["y"]


def test_graph_without_points_is_not_applicable() -> None:
    result = calculate("1/x", "graph", {"x_min": "1", "x_max": "5"})
    assert result.verification is not None
    assert result.verification.status is VerificationStatus.NOT_APPLICABLE

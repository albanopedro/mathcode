"""Trigonometry: sec/csc/cot, periodic equations, conversions, reduction, identities and
triangles, with their verification and presentation (ADR 0016)."""

from dataclasses import replace

import pytest
import sympy as sp

from app.calculator import calculate
from app.core.errors import ErrorCode, MathError
from app.core.notices import NoticeCode
from app.formatting.results import present_equation, present_trigonometry
from app.math_engine.equations import EquationOutcome, SolutionKind, solve_equation
from app.math_engine.periodic import Family, merge
from app.math_engine.trigonometry import (
    ConversionOutcome,
    IdentityOutcome,
    ReductionOutcome,
    TriangleOutcome,
    trigonometry,
)
from app.models.intents import SolveEquationParams, TrigonometryCalculation, TrigonometryParams
from app.models.result import VerificationStatus as S
from app.verification.equations import verify_equation
from app.verification.periodic import reduce_to_polynomial
from app.verification.trigonometry import verify_trigonometry

pi = sp.pi


def solve(equation: str, lower: str | None = None, upper: str | None = None) -> EquationOutcome:
    return solve_equation(SolveEquationParams(equation=equation, lower=lower, upper=upper))


def trig(expression: str, calculation: TrigonometryCalculation) -> object:
    return trigonometry(TrigonometryParams(expression=expression, calculation=calculation))


# -- sec, csc and cot in the language ------------------------------------------------------------


@pytest.mark.parametrize(
    ("text", "plain"),
    [
        ("sec(pi/3)", "2"),
        ("csc(pi/6)", "2"),
        ("cossec(30°)", "2"),
        ("cot(pi/4)", "1"),
        ("cotg(45°)", "1"),
        ("csc(x)^2 - cot(x)^2", "1"),
    ],
)
def test_reciprocal_functions(text: str, plain: str) -> None:
    result = calculate(text)
    assert result.result is not None and result.result.plain == plain
    assert result.verification is not None and result.verification.status is not S.FAILED


def test_reciprocal_functions_in_calculus() -> None:
    derivative = calculate("sec(x)", "derivative")
    assert derivative.result is not None and derivative.result.plain == "tan(x)*sec(x)"
    assert derivative.verification is not None
    assert derivative.verification.status is S.VERIFIED_SYMBOLIC
    limit = calculate("cot(x)", "limit", {"point": "pi/4"})
    assert limit.verification is not None and limit.verification.status is S.VERIFIED_SYMBOLIC
    assert calculate("sec(pi/2)").error is not None  # a pole


# -- periodic equations -------------------------------------------------------------------------

PERIODIC = [
    ("sin(x) = 1/2", [(pi / 6, 2 * pi), (5 * pi / 6, 2 * pi)], [pi / 6, 5 * pi / 6]),
    ("tan(x) = 1", [(pi / 4, pi)], [pi / 4, 5 * pi / 4]),
    ("sin(x) = 0", [(0, pi)], [0, pi]),  # 2kπ and π + 2kπ merged
    ("2cos(x)^2 - 1 = 0", [(pi / 4, pi / 2)], [pi / 4, 3 * pi / 4, 5 * pi / 4, 7 * pi / 4]),
    (
        "sin(2x) = 1/2",
        [(pi / 12, pi), (5 * pi / 12, pi)],
        [pi / 12, 5 * pi / 12, 13 * pi / 12, 17 * pi / 12],
    ),
    ("cos(3x + pi/4) = 0", [(pi / 12, pi / 3)], None),
    ("sec(x) = 2", [(pi / 3, 2 * pi), (5 * pi / 3, 2 * pi)], [pi / 3, 5 * pi / 3]),
    ("cot(x) = 1", [(pi / 4, pi)], [pi / 4, 5 * pi / 4]),
    ("tan(x)^2 = 3", [(pi / 3, pi), (2 * pi / 3, pi)], None),
    ("2sin(x)^2 + cos(x) - 1 = 0", [(0, 2 * pi / 3)], [0, 2 * pi / 3, 4 * pi / 3]),
    ("cos(x) = sqrt(2)/2", [(pi / 4, 2 * pi), (7 * pi / 4, 2 * pi)], None),
    (
        "sin(x) = 1/3",
        [(sp.asin(sp.Rational(1, 3)), 2 * pi), (pi - sp.asin(sp.Rational(1, 3)), 2 * pi)],
        None,
    ),
    ("sin(pi*x) = 0", [(0, 1)], None),
]


@pytest.mark.parametrize(("equation", "families", "listed"), PERIODIC)
def test_periodic_solutions_are_proved_complete(
    equation: str, families: list[tuple[sp.Expr, sp.Expr]], listed: list[sp.Expr] | None
) -> None:
    outcome = solve(equation)
    assert outcome.kind is SolutionKind.PERIODIC
    assert [(f.offset, f.period) for f in outcome.families] == [
        (sp.sympify(o), sp.sympify(p)) for o, p in families
    ]
    if listed is not None:
        assert list(outcome.solutions) == [sp.sympify(v) for v in listed]
    report = verify_equation(outcome)
    assert report.status is S.VERIFIED_SYMBOLIC, report.checks


@pytest.mark.parametrize(
    "equation", ["sin(x) = cos(x)", "sin(x) + cos(x) = 1", "sin(2x) = sin(x)", "(x - 1)sin(x) = 0"]
)
def test_other_periodic_equations_are_partial(equation: str) -> None:
    report = verify_equation(solve(equation))
    assert report.status is S.PARTIAL
    assert report.reason == "completeness_not_proved"


def test_isolated_solutions_join_the_families() -> None:
    outcome = solve("(x - 1)sin(x) = 0")
    assert outcome.isolated == (1,)
    assert list(outcome.solutions) == [0, 1, pi]


def test_families_outside_the_domain_are_discarded() -> None:
    outcome = solve("cos(x)tan(x) = 1")  # solveset says π/2 + 2kπ, where tan is undefined
    assert outcome.kind is SolutionKind.NONE
    assert outcome.rejected_families == (Family(pi / 2, 2 * pi),)
    report = verify_equation(outcome)
    assert report.status is S.UNVERIFIED
    assert any(check.kind == "domain" for check in report.checks)


def test_no_solution_and_identities_are_proved_by_reduction() -> None:
    none = verify_equation(solve("cos(x) = 2"))
    assert none.status is S.VERIFIED_SYMBOLIC
    assert "u = 2" in none.checks[0].message
    identity = verify_equation(solve("sin(x)^2 + cos(x)^2 = 1"))
    assert identity.status is S.VERIFIED_SYMBOLIC


def test_interval_of_the_listed_solutions() -> None:
    outcome = solve("sin(x) = 1/2", "0", "4pi")
    assert list(outcome.solutions) == [pi / 6, 5 * pi / 6, 13 * pi / 6, 17 * pi / 6]
    assert outcome.interval is not None and outcome.interval.closed
    closed = solve("sin(x) = 0", "0", "2pi")  # a typed interval includes its ends
    assert list(closed.solutions) == [0, pi, 2 * pi]
    assert verify_equation(closed).status is S.VERIFIED_SYMBOLIC


def test_many_solutions_are_truncated_with_a_notice() -> None:
    outcome = solve("sin(x) = 0", "0", "1000")
    assert len(outcome.solutions) == 100 and outcome.listed_total == 319
    assert NoticeCode.SOLUTIONS_TRUNCATED in {n.code for n in outcome.notices}
    assert verify_equation(outcome).status is S.VERIFIED_SYMBOLIC


def test_an_interval_for_a_finite_equation_is_ignored_with_a_notice() -> None:
    outcome = solve("x^2 = 4", "0", "10")
    assert outcome.solutions == (-2, 2)
    assert NoticeCode.INTERVAL_IGNORED in {n.code for n in outcome.notices}


@pytest.mark.parametrize(
    ("lower", "upper", "message"),
    [("2", "1", "maior que o início"), ("0", "inf", "limitado"), ("x", "1", "variáveis")],
)
def test_bad_intervals(lower: str, upper: str, message: str) -> None:
    with pytest.raises(MathError) as exc:
        solve("sin(x) = 0", lower, upper)
    assert message in exc.value.message


def test_merging_families() -> None:
    quarter = [Family(k * pi / 2, 2 * pi) for k in range(4)]
    assert merge(quarter) == [Family(sp.Integer(0), pi / 2)]
    assert merge([Family(pi / 6, 2 * pi), Family(5 * pi / 6, 2 * pi)]) == [
        Family(pi / 6, 2 * pi),
        Family(5 * pi / 6, 2 * pi),
    ]


def test_reduction_to_a_polynomial() -> None:
    x = sp.Symbol("x", real=True)
    reduction = reduce_to_polynomial(2 * sp.sin(x) ** 2 + sp.cos(x) - 1, x)
    assert reduction is not None and reduction.function == "cos" and reduction.rewritten
    assert reduce_to_polynomial(sp.sin(x) - sp.cos(x), x) is None  # odd powers of both
    assert reduce_to_polynomial(sp.sin(x) - x, x) is None  # x outside the functions
    assert reduce_to_polynomial(sp.sin(2 * x) - sp.sin(x), x) is None  # two arguments


def test_wrong_periodic_answers_are_caught() -> None:
    outcome = solve("sin(x) = 1/2")
    wrong_offset = replace(outcome, families=(Family(pi / 6, 2 * pi), Family(pi / 3, 2 * pi)))
    assert verify_equation(wrong_offset).status is S.FAILED
    missing = replace(
        outcome, families=(Family(pi / 6, 2 * pi),), solutions=(pi / 6,), listed_total=1
    )
    report = verify_equation(missing)
    assert report.status is S.FAILED and report.checks[-1].kind == "completeness"
    wrong_list = replace(outcome, listed_total=3)
    assert verify_equation(wrong_list).status is S.FAILED


def test_a_missing_family_is_caught_by_the_scan() -> None:
    outcome = solve("sin(x) = cos(x)")
    missing = replace(
        outcome, families=(Family(pi / 4, 2 * pi),), solutions=(pi / 4,), listed_total=1
    )
    report = verify_equation(missing)
    assert report.status is S.FAILED
    assert "varredura" in report.checks[-1].message


def test_sympy_tangent_shifts_are_not_trusted() -> None:
    """SymPy says tan(2kπ + 2π/3) = √3/3: the substitution rewrites tan with sin and cos."""
    k = sp.Symbol("k", integer=True)
    assert sp.tan(2 * pi * k + 2 * pi / 3) != sp.tan(2 * pi / 3)  # the SymPy bug, still there
    report = verify_equation(solve("tan(x)^2 = 3"))
    assert report.status is S.VERIFIED_SYMBOLIC


def test_presentation_of_periodic_solutions() -> None:
    presentation = present_equation(solve("sin(x) = 1/2"))
    assert presentation.result.plain == "x = pi/6 + 2*pi*k ou x = 5*pi/6 + 2*pi*k (k inteiro)"
    latex = presentation.result.latex
    assert r"\frac{\pi}{6} + 2k\pi" in latex and r"k \in \mathbb{Z}" in latex
    details = presentation.details
    assert details["solution_set"] == "periodic"
    assert details["solutions_latex"] == [r"\frac{\pi}{6}", r"\frac{5 \pi}{6}"]
    assert details["interval"]["latex"] == r"[0, 2 \pi)"
    assert details["integer"] == "k"
    assert present_equation(solve("sin(k) = 0")).details["integer"] == "n"  # k is taken
    assert r"\frac{k\pi}{2}" in present_equation(solve("2cos(x)^2 - 1 = 0")).result.latex


def test_periodic_through_the_pipeline() -> None:
    result = calculate("sin(x) = 1/2", "solve_equation", {"lower": "0", "upper": "pi"})
    assert result.success and result.details["solutions"] == ["pi/6", "5*pi/6"]
    assert result.verification is not None
    assert result.verification.status is S.VERIFIED_SYMBOLIC


# -- conversions ----------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("text", "plain", "status"),
    [
        ("30°", "pi/6 rad", S.VERIFIED_SYMBOLIC),
        ("45° + 15°", "pi/3 rad", S.VERIFIED_SYMBOLIC),
        ("pi/6", "30°", S.VERIFIED_SYMBOLIC),
        ("2", "360/pi° ≈ 114.592°", S.VERIFIED_NUMERIC),
    ],
)
def test_conversions(text: str, plain: str, status: S) -> None:
    outcome = trig(text, "convert")
    assert isinstance(outcome, ConversionOutcome)
    assert present_trigonometry(outcome).result.plain == plain
    assert verify_trigonometry(outcome).status is status


def test_a_wrong_conversion_is_caught() -> None:
    outcome = trig("30°", "convert")
    assert isinstance(outcome, ConversionOutcome)
    wrong = replace(outcome, radians=pi / 5, degrees=sp.Integer(36))
    assert verify_trigonometry(wrong).status is S.FAILED


# -- reduction to the first quadrant -------------------------------------------------------------


@pytest.mark.parametrize(
    ("text", "plain"),
    [
        ("150°", "150° está no 2º quadrante; ângulo de referência 30°"),
        ("sin(150°)", "sin(150°) = sin(30°) = 1/2"),
        ("cos(150°)", "cos(150°) = -cos(30°) = -sqrt(3)/2"),
        ("tan(225°)", "tan(225°) = tan(45°) = 1"),
        ("sec(120°)", "sec(120°) = -sec(60°) = -2"),
        ("750°", "750° está no 1º quadrante; ângulo de referência 30°"),
        ("-30°", "-30° está no 4º quadrante; ângulo de referência 30°"),
        ("90°", "90° está sobre um eixo (primeira determinação 90°)"),
        ("5pi/4", "5*pi/4 está no 3º quadrante; ângulo de referência pi/4"),
    ],
)
def test_reductions(text: str, plain: str) -> None:
    outcome = trig(text, "reduce")
    assert isinstance(outcome, ReductionOutcome)
    assert present_trigonometry(outcome).result.plain == plain
    assert verify_trigonometry(outcome).status is S.VERIFIED_SYMBOLIC


def test_reduction_details() -> None:
    outcome = trig("750°", "reduce")
    assert isinstance(outcome, ReductionOutcome)
    assert outcome.turns == 2 and outcome.first == pi / 6 and outcome.quadrant == 1
    details = present_trigonometry(trig("cos(150°)", "reduce")).details
    assert details["quadrant"] == 2 and details["reference"] == "30°"
    rows = {row["function"]: row for row in details["values"]}
    assert rows["cos"]["reduced_latex"] == r"-\cos\left(30^\circ\right)"
    assert rows["tan"]["sign"] == -1


def test_reduction_errors_and_tampering() -> None:
    with pytest.raises(MathError) as exc:
        trig("tan(90°)", "reduce")
    assert exc.value.code is ErrorCode.DOMAIN_ERROR
    outcome = trig("sin(150°)", "reduce")
    assert isinstance(outcome, ReductionOutcome)
    assert verify_trigonometry(replace(outcome, reference=pi / 3)).status is S.FAILED
    assert (
        verify_trigonometry(replace(outcome, signs={**outcome.signs, "cos": 1})).status is S.FAILED
    )


# -- identities ------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    "text",
    [
        "sin(x)^2 + cos(x)^2 = 1",
        "tan(x) = sin(x)/cos(x)",
        "sin(2x) = 2sin(x)cos(x)",
        "sin(a + b) = sin(a)cos(b) + cos(a)sin(b)",
        "sec(x)^2 = 1 + tan(x)^2",
        "cos(x)^4 - sin(x)^4 = cos(2x)",
        "(1 - cos(x)^2)/sin(x) = sin(x)",
    ],
)
def test_identities_are_proved(text: str) -> None:
    outcome = trig(text, "identity")
    assert isinstance(outcome, IdentityOutcome) and outcome.holds and outcome.proved
    report = verify_trigonometry(outcome)
    assert report.status is S.VERIFIED_SYMBOLIC
    assert any("Euler" in check.message for check in report.checks)


def test_a_false_identity_has_a_counterexample() -> None:
    outcome = trig("tan(x) = sin(x)", "identity")
    assert isinstance(outcome, IdentityOutcome) and not outcome.holds
    assert outcome.counterexample == {"x": pi / 6}
    presentation = present_trigonometry(outcome)
    assert presentation.result.latex == r"\tan{\left(x \right)} \not\equiv \sin{\left(x \right)}"
    counterexample = presentation.details["counterexample"]
    assert counterexample["left_latex"] == r"\frac{\sqrt{3}}{3}"
    assert verify_trigonometry(outcome).status is S.VERIFIED_SYMBOLIC


def test_a_fake_counterexample_is_caught() -> None:
    outcome = trig("tan(x) = sin(x)", "identity")
    assert isinstance(outcome, IdentityOutcome)
    fake = replace(outcome, counterexample={"x": sp.Integer(0)})  # tan(0) = sin(0)
    assert verify_trigonometry(fake).status is S.FAILED
    wrong = replace(trig("tan(x) = sin(x)", "identity"), holds=True, proved=True)  # type: ignore[type-var]
    assert verify_trigonometry(wrong).status is S.FAILED


@pytest.mark.parametrize(
    ("text", "message"),
    [("1 + 1 = 2", "tem variáveis"), ("sin(x)", "falta o sinal"), ("a + b + c + d = 1", "até 3")],
)
def test_identity_errors(text: str, message: str) -> None:
    with pytest.raises(MathError) as exc:
        trig(text, "identity")
    assert message in exc.value.message


# -- triangles ------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("text", "case", "computed"),
    [
        ("a = 3; b = 4; c = 5", "LLL", "A ≈ 36.8699°; B ≈ 53.1301°; C = 90°"),
        ("a = 5; b = 7; C = 60°", "LAL", "A ≈ 43.8979°; B ≈ 76.1021°; c = sqrt(39) ≈ 6.245"),
        (
            "a = 10; B = 30°; C = 45°",
            "ALA",
            "A = 105°; b = -5*sqrt(2) + 5*sqrt(6) ≈ 5.17638; c = -10 + 10*sqrt(3) ≈ 7.32051",
        ),
        ("a = 2; b = 2; c = 2", "LLL", "A = 60°; B = 60°; C = 60°"),
        ("a = 1; b = 2; A = 30°", "LLA", "B = 90°; c = sqrt(3) ≈ 1.73205; C = 60°"),
    ],
)
def test_triangles(text: str, case: str, computed: str) -> None:
    outcome = trig(text, "triangle")
    assert isinstance(outcome, TriangleOutcome) and outcome.case == case
    assert present_trigonometry(outcome).result.plain == computed
    assert verify_trigonometry(outcome).status is S.VERIFIED_SYMBOLIC


def test_the_ambiguous_case_has_two_triangles() -> None:
    outcome = trig("a = 5; b = 7; A = 30°", "triangle")
    assert isinstance(outcome, TriangleOutcome) and len(outcome.triangles) == 2
    report = verify_trigonometry(outcome)
    assert report.status is S.VERIFIED_SYMBOLIC
    assert any("2 raiz(es) positiva(s)" in check.message for check in report.checks)
    one = replace(outcome, triangles=outcome.triangles[:1])
    assert verify_trigonometry(one).status is S.FAILED


def test_a_wrong_triangle_is_caught() -> None:
    outcome = trig("a = 5; b = 7; C = 60°", "triangle")
    assert isinstance(outcome, TriangleOutcome)
    (triangle,) = outcome.triangles
    wrong = replace(triangle, sides={**triangle.sides, "c": triangle.sides["c"] + 1})
    assert verify_trigonometry(replace(outcome, triangles=(wrong,))).status is S.FAILED


@pytest.mark.parametrize(
    ("text", "message"),
    [
        ("a = 1; b = 3; A = 30°", "sen B = 3/2 > 1"),
        ("a = 5; b = 7; C = 60", "Para graus, escreva C = 60°"),
        ("A = 30°; B = 60°; C = 90°", "pelo menos um lado"),
        ("a = 1; b = 1; c = 3", "não formam um triângulo"),
        ("a = 5; B = 100°; C = 90°", "somam 180°"),
        ("a = 5; b = 7", "três medidas"),
        ("a = 5; d = 7; C = 60°", "a, b ou c"),
        ("a = -5; b = 7; C = 60°", "positivos"),
        ("5; 7; 60°", "o nome de cada uma"),
    ],
)
def test_triangle_errors(text: str, message: str) -> None:
    with pytest.raises(MathError) as exc:
        trig(text, "triangle")
    assert message in exc.value.message


def test_an_angle_without_degrees_is_radians_with_a_notice() -> None:
    outcome = trig("a = 3; b = 4; C = 1", "triangle")
    assert isinstance(outcome, TriangleOutcome)
    assert NoticeCode.ANGLE_IN_RADIANS in {n.code for n in outcome.notices}


def test_triangle_details() -> None:
    details = present_trigonometry(trig("a = 5; b = 7; C = 60°", "triangle")).details
    assert details["case"] == "LAL" and details["law"] == "lei dos cossenos"
    rows = details["triangles"][0]["rows"]
    assert [row["side"] for row in rows] == ["a", "b", "c"]
    assert rows[2]["side_latex"] == r"\sqrt{39} \approx 6.245"
    assert rows[2]["angle_latex"] == r"60^\circ" and rows[2]["angle_given"]


def test_trigonometry_through_the_pipeline() -> None:
    result = calculate("a = 5; b = 7; C = 60°", "trigonometry", {"calculation": "triangle"})
    assert result.success and result.intent == "trigonometry"
    assert result.normalized_input == "a = 5; b = 7; C = 60°"
    assert result.verification is not None
    assert result.verification.status is S.VERIFIED_SYMBOLIC

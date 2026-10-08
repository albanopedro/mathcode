"""Counting and probability: n!, C and A in the language, engine, verification (ADR 0015)."""

from dataclasses import replace
from fractions import Fraction

import pytest
import sympy as sp
from mpmath import mp, mpf

from app.calculator import calculate
from app.core.errors import ErrorCode, MathError
from app.core.notices import NoticeCode
from app.formatting.results import percent, present_probability
from app.math_engine.probability import (
    CATALOG,
    BinomialSummary,
    ProbabilityOutcome,
    probability,
)
from app.models.intents import ProbabilityCalculation, ProbabilityParams
from app.models.result import VerificationStatus as S
from app.parsing import parse
from app.parsing.ast import Call, Negate
from app.parsing.build import ExpressionBuilder
from app.verification.exact import exact_value
from app.verification.numeric import evaluate
from app.verification.probability import verify_probability

R = sp.Rational


def run(data: str, calculation: ProbabilityCalculation) -> ProbabilityOutcome:
    return probability(ProbabilityParams(data=data, calculation=calculation))


# -- n!, C(n, k) and A(n, k) in the language ------------------------------------------------------


@pytest.mark.parametrize(
    ("text", "canonical", "value"),
    [
        ("5!", "5!", 120),
        ("0!", "0!", 1),
        ("2^3!", "2^3!", 64),  # 2^(3!)
        ("-3!", "-3!", -6),  # -(3!)
        ("3!^2", "3!^2", 36),
        ("(3!)!", "(3!)!", 720),
        ("(2 + 1)!", "(2 + 1)!", 6),
        ("C(10, 3)", "C(10, 3)", 120),
        ("C(10; 3)", "C(10, 3)", 120),
        ("A(6, 2)", "A(6, 2)", 30),
        ("C(0, 0)", "C(0, 0)", 1),
        ("C(4, 2)/C(52, 2)", "C(4, 2)/C(52, 2)", R(1, 221)),
        ("(0.1*30)!", "(0.1*30)!", 6),
        ("C(10^15, 2)", "C(10^15, 2)", 10**15 * (10**15 - 1) // 2),
    ],
)
def test_counting_in_expressions(text: str, canonical: str, value: object) -> None:
    parsed = parse(text)
    assert parsed.canonical == canonical
    assert parse(parsed.canonical).tree == parsed.tree  # the printed text reads back the same
    assert ExpressionBuilder().build(parsed.tree) == value
    result = calculate(text)
    assert result.success and result.verification is not None
    assert result.verification.status is S.VERIFIED_SYMBOLIC


def test_the_factorial_binds_tighter_than_the_sign() -> None:
    tree = parse("-3!").tree
    assert isinstance(tree, Negate) and isinstance(tree.operand, Call)
    assert tree.operand.name == "factorial"


def test_c_and_a_are_variables_without_two_arguments() -> None:
    result = calculate("C(x + 1)")
    assert result.success and result.normalized_input == "C*(x + 1)"
    assert calculate("A + C").success


@pytest.mark.parametrize(
    ("text", "code", "message"),
    [
        ("3!!", ErrorCode.AMBIGUOUS_INPUT, "(3!)!"),
        ("C(10,3)", ErrorCode.AMBIGUOUS_INPUT, "C(10, 3), com espaço"),
        ("A(6,2)", ErrorCode.AMBIGUOUS_INPUT, "o arranjo"),
        ("c(10, 3)", ErrorCode.PARSE_ERROR, "letra maiúscula"),
        ("C(1, 2, 3)", ErrorCode.PARSE_ERROR, "recebe 2"),
        ("!5", ErrorCode.PARSE_ERROR, "Falta um termo"),
        ("x!", ErrorCode.UNSUPPORTED_FEATURE, "sem variáveis"),
        ("C(n, 2)", ErrorCode.UNSUPPORTED_FEATURE, "sem variáveis"),
        ("(1/2)!", ErrorCode.DOMAIN_ERROR, "inteiros não negativos"),
        ("(-1)!", ErrorCode.DOMAIN_ERROR, "inteiros não negativos"),
        ("C(5, -1)", ErrorCode.DOMAIN_ERROR, "inteiros não negativos"),
        ("pi!", ErrorCode.DOMAIN_ERROR, "inteiros não negativos"),
        ("1500!", ErrorCode.LIMIT_EXCEEDED, "4000 dígitos"),
        ("C(100000, 50000)", ErrorCode.LIMIT_EXCEEDED, "4000 dígitos"),
        ("A(10^20, 10^5)", ErrorCode.LIMIT_EXCEEDED, "4000 dígitos"),
    ],
)
def test_counting_errors(text: str, code: ErrorCode, message: str) -> None:
    result = calculate(text)
    assert result.error is not None
    assert result.error.code is code
    assert message in result.error.message


def test_choosing_more_than_there_is_gives_zero_with_a_notice() -> None:
    result = calculate("C(3, 5)")
    assert result.result is not None and result.result.plain == "0"
    assert [w.code for w in result.warnings] == [NoticeCode.COUNT_IS_ZERO]
    assert "A ordem é C(n, k)" in result.warnings[0].message


def test_the_independent_evaluators_count_by_themselves() -> None:
    assert exact_value(parse("C(10, 3) + A(6, 2) - 4!").tree) == Fraction(126)
    assert exact_value(parse("C(3, 5)").tree) == 0
    assert exact_value(parse("(1/2)!").tree) is None  # an error in the pipeline
    with mp.workdps(60):
        assert evaluate(parse("C(10, 3)/A(6, 2)").tree).value == mpf(4)
        assert evaluate(parse("(0.1*30)!").tree).value == mpf(6)


def test_an_exclamation_after_a_word_is_still_punctuation() -> None:
    result = calculate("quanto é 5!")
    assert result.result is not None and result.result.plain == "120"


# -- every calculation of the catalog -------------------------------------------------------------

EXPECTED: list[tuple[str, ProbabilityCalculation, object]] = [
    ("n = 5", "factorial", 120),
    ("5", "factorial", 120),  # one value: its name may be left out
    ("n = 0", "factorial", 1),
    ("n = 6; k = 2", "arrangement", 30),
    ("n = 3; k = 2", "arrangement_repetition", 9),
    ("n = 10; k = 3", "combination", 120),
    ("n = 10, k = 3", "combination", 120),
    ("n = 3; k = 2", "combination_repetition", 6),
    ("n = 2000; k = 3", "combination", 1331334000),  # too many to list: formula only
    ("BANANA", "anagrams", 60),
    ("MISSISSIPPI", "anagrams", 34650),
    ("amor", "anagrams", 24),
    ("P(A) = 1/4", "complement", R(3, 4)),
    ("1/4", "complement", R(3, 4)),
    ("P(A) = 1/2; P(B) = 1/3; P(A ou B) = 2/3", "intersection", R(1, 6)),
    ("P(A) = 1/2; P(B) = 1/3", "intersection_independent", R(1, 6)),
    ("P(A) = 1/2; P(B) = 1/3; P(A e B) = 1/6", "union", R(2, 3)),
    ("P(A) = 1/2; P(B) = 1/3; P(A ∩ B) = 1/6", "union", R(2, 3)),
    ("P(A) = 50%; P(B) = 30%", "union_independent", R(13, 20)),
    ("P(A e B) = 1/6; P(B) = 1/3", "conditional", R(1, 2)),
    ("P(A) = 1/2; P(B) = 1/3; P(A e B) = 1/6", "conditional", R(1, 2)),  # P(A) checked, unused
    ("n = 5; k = 3; p = 1/2", "binomial_exact", R(5, 16)),
    ("n = 5; k = 3; p = 1/2", "binomial_at_most", R(13, 16)),
    ("n = 5; k = 3; p = 1/2", "binomial_at_least", R(1, 2)),
    ("n = 4; k = 4; p = 1", "binomial_exact", 1),
    ("n = 4; k = 0; p = 0", "binomial_exact", 1),
    ("n = 4; k = 1; p = 0", "binomial_at_least", 0),
    ("n = 10; p = 30%", "binomial_summary", (3, R(21, 10))),
]


@pytest.mark.parametrize(("data", "calculation", "expected"), EXPECTED)
def test_results_and_their_verification(
    data: str, calculation: ProbabilityCalculation, expected: object
) -> None:
    outcome = run(data, calculation)
    if isinstance(outcome.result, BinomialSummary):
        assert (outcome.result.mean, outcome.result.variance) == expected
    else:
        assert outcome.result == expected
    verification = verify_probability(outcome)
    assert verification.status is S.VERIFIED_SYMBOLIC, verification.checks


def test_every_calculation_of_the_catalog_is_tested() -> None:
    assert {calculation for _, calculation, _ in EXPECTED} == set(CATALOG)


def test_small_counts_are_also_listed_one_by_one() -> None:
    small = verify_probability(run("n = 10; k = 3", "combination"))
    assert any("uma a uma" in check.message for check in small.checks)
    large = verify_probability(run("n = 2000; k = 3", "combination"))
    assert not any("uma a uma" in check.message for check in large.checks)


def test_values_are_read_with_percentages_and_shown_as_read() -> None:
    outcome = run("P(A) = 50%;  P(B)=0,3", "union_independent")
    assert outcome.values == {"A": R(1, 2), "B": R(3, 10)}
    assert outcome.parsed.canonical == "P(A) = 50%; P(B) = 0.3"
    assert [n.code for n in outcome.notices] == [NoticeCode.DECIMAL_COMMA]


def test_anagrams_ignore_accents_with_a_notice() -> None:
    outcome = run("Matemática", "anagrams")
    assert outcome.parsed.canonical == "MATEMATICA"
    assert outcome.letters == (("M", 2), ("A", 3), ("T", 2), ("E", 1), ("I", 1), ("C", 1))
    assert outcome.result == 151200
    assert [n.code for n in outcome.notices] == [NoticeCode.ACCENTS_IGNORED]


def test_unused_values_get_a_notice() -> None:
    outcome = run("n = 10; k = 2; p = 1/2", "binomial_summary")
    assert [n.code for n in outcome.notices] == [NoticeCode.UNUSED_VALUES]
    assert "k" in outcome.notices[0].message


def test_more_chosen_than_there_is() -> None:
    outcome = run("n = 3; k = 5", "arrangement")
    assert outcome.result == 0
    assert [n.code for n in outcome.notices] == [NoticeCode.COUNT_IS_ZERO]
    assert verify_probability(outcome).status is S.VERIFIED_SYMBOLIC


@pytest.mark.parametrize(
    ("data", "calculation", "message"),
    [
        ("k = 3", "combination", "informe: n = 10; k = 3"),
        ("n = 10; n = 3", "combination", "duas vezes"),
        ("x = 3", "factorial", "x não é um valor"),
        ("P(A) = 1/2", "factorial", "P(A) não é um valor"),
        ("n = 5; k = 3", "complement", "n não é um valor"),
        ("n = 10 k = 3", "combination", "Escreva cada valor com o seu nome"),
        ("n = ", "factorial", "Falta o valor de n"),
        ("n = 5;", "factorial", "valor vazio"),
        ("n = 5,5", "factorial", "inteiro não negativo"),
        ("n = -2", "factorial", "inteiro não negativo"),
        ("n = 0; k = 2", "arrangement_repetition", "maior ou igual a 1"),
        ("n = x", "factorial", "sem variáveis"),
        ("n = [1, 2]", "factorial", "precisa ser um número"),
        ("n = 10%", "factorial", "Só probabilidades"),
        ("n = 1500", "factorial", "4000 dígitos"),
        ("n = 10; k = 3,5", "combination", "inteiro não negativo"),
        ("BAN ANA", "anagrams", "sem espaços"),
        ("B4NANA", "anagrams", "sem espaços"),
        ("ΑΒΓ", "anagrams", "de A a Z"),
        ("A" * 31, "anagrams", "30 letras"),
        ("P(C) = 1/2", "complement", "Os eventos são"),
        ("P(A) = 3/2", "complement", "vai de 0 a 1"),
        ("P(A) = sqrt(2)/2", "complement", "racional"),
        ("P(A) = 1/2; P(B) = 1/3", "union", "independentes"),
        ("P(A) = 1/2; P(B) = 1/3", "intersection", "informe: P(A) = 1/2; P(B) = 1/3; P(A ou"),
        ("P(A) = 1/2; P(B) = 1/3; P(A e B) = 2/3", "union", "maior que P(A)"),
        ("P(A) = 3/4; P(B) = 3/4; P(A e B) = 1/4", "union", "pelo menos 1/2"),
        ("P(A) = 1/2; P(B) = 1/3; P(A ou B) = 1/4", "intersection", "menor que P(A)"),
        ("P(A) = 1/4; P(B) = 1/4; P(A ou B) = 3/4", "intersection", "maior que P(A) + P(B)"),
        (
            "P(A) = 1/2; P(B) = 1/3; P(A e B) = 1/6; P(A ou B) = 1/2",
            "union",
            "não combinam",
        ),
        ("P(A) = 1/2; P(B) = 1/3; P(A e B) = 1/5", "union_independent", "não são independentes"),
        ("P(A) = 1/2; P(B) = 1/3; P(A ou B) = 1/2", "intersection_independent", "não são"),
        ("P(A e B) = 0; P(B) = 0", "conditional", "P(B) = 0"),
        ("n = 5; k = 6; p = 1/2", "binomial_exact", "k vai de 0 a n"),
        ("n = 0; k = 0; p = 1/2", "binomial_exact", "maior ou igual a 1"),
        ("n = 5; k = 3; p = 1,5", "binomial_exact", "vai de 0 a 1"),
        ("n = 1001; k = 3; p = 1/2", "binomial_exact", "até 1000"),
        ("n = 1000; k = 3; p = 1/10007", "binomial_exact", "4000 dígitos"),
    ],
)
def test_errors_are_explained(data: str, calculation: ProbabilityCalculation, message: str) -> None:
    with pytest.raises(MathError) as exc:
        run(data, calculation)
    assert message in exc.value.message


def test_error_positions_point_into_the_values() -> None:
    result = calculate("n = 10; k = 1/0", "probability", {"calculation": "combination"})
    assert result.error is not None and result.error.code is ErrorCode.DIVISION_BY_ZERO
    assert result.error.position == "n = 10; k = 1/0".index("/")


def test_large_binomial_sums_stay_exact() -> None:
    outcome = run("n = 1000; k = 500; p = 1/3", "binomial_at_most")
    assert isinstance(outcome.result, sp.Rational) and 0 < outcome.result < 1
    assert verify_probability(outcome).status is S.VERIFIED_SYMBOLIC


# -- the verification catches wrong results -------------------------------------------------------


@pytest.mark.parametrize(
    ("data", "calculation"),
    [
        ("n = 5", "factorial"),
        ("n = 6; k = 2", "arrangement"),
        ("n = 3; k = 2", "arrangement_repetition"),
        ("n = 10; k = 3", "combination"),
        ("n = 2000; k = 3", "combination"),
        ("n = 3; k = 2", "combination_repetition"),
        ("BANANA", "anagrams"),
        ("P(A) = 1/4", "complement"),
        ("P(A) = 1/2; P(B) = 1/3; P(A ou B) = 2/3", "intersection"),
        ("P(A) = 1/2; P(B) = 1/3", "intersection_independent"),
        ("P(A) = 1/2; P(B) = 1/3; P(A e B) = 1/6", "union"),
        ("P(A) = 1/2; P(B) = 1/3", "union_independent"),
        ("P(A e B) = 1/6; P(B) = 1/3", "conditional"),
        ("n = 5; k = 3; p = 1/2", "binomial_exact"),
        ("n = 5; k = 3; p = 1/2", "binomial_at_most"),
        ("n = 5; k = 3; p = 1/2", "binomial_at_least"),
    ],
)
def test_a_wrong_number_is_caught(data: str, calculation: ProbabilityCalculation) -> None:
    outcome = run(data, calculation)
    wrong = outcome.result + (1 if outcome.group == "counting" else R(1, 100))
    assert verify_probability(replace(outcome, result=wrong)).status is S.FAILED


def test_a_wrong_summary_is_caught() -> None:
    outcome = run("n = 10; p = 30%", "binomial_summary")
    assert isinstance(outcome.result, BinomialSummary)
    for wrong in (
        replace(outcome.result, mean=outcome.result.mean + 1),
        replace(outcome.result, variance=outcome.result.variance + 1),
        replace(outcome.result, std=outcome.result.std + 1),
    ):
        assert verify_probability(replace(outcome, result=wrong)).status is S.FAILED


def test_a_misread_value_is_caught() -> None:
    outcome = run("n = 10; k = 3", "combination")
    misread = replace(outcome, values={**outcome.values, "n": sp.Integer(11)})
    assert verify_probability(misread).status is S.FAILED


def test_misread_letters_are_caught() -> None:
    outcome = run("BANANA", "anagrams")
    misread = replace(outcome, letters=(("B", 1), ("A", 2), ("N", 3)))
    assert verify_probability(misread).status is S.FAILED


def test_values_that_are_not_simple_fractions_are_noted() -> None:
    outcome = run("n = sqrt(16); k = 2", "combination")
    verification = verify_probability(outcome)
    assert verification.status is S.VERIFIED_SYMBOLIC
    assert verification.checks[0].outcome == "inconclusive"


# -- presentation ---------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("value", "text", "exact"),
    [
        (R(3, 8), "37,5%", True),
        (R(1, 2), "50%", True),
        (sp.Integer(1), "100%", True),
        (sp.Integer(0), "0%", True),
        (R(1, 6), "16,67%", False),
        (R(2, 3), "66,67%", False),
        (R(1, 3200), "0,03125%", True),
        (R(1, 7000), "0,01429%", False),
        (R(1, 7), "14,29%", False),
        (R(1, 2**1000), "9,333·10⁻³⁰⁰%", False),
        (R(1, 10**6), "0,0001%", True),
        (R(1, 3 * 10**6), "3,333·10⁻⁵%", False),
        (R(1, 3 * 10**5), "0,0003333%", False),
        (R(99999, 100000) - R(1, 10**9), "100%", False),  # rounded, shown with ≈
    ],
)
def test_percentages(value: sp.Rational, text: str, exact: bool) -> None:
    assert percent(value) == (text, exact)


def test_presentation_of_a_probability() -> None:
    presentation = present_probability(run("P(A) = 1/2; P(B) = 1/3", "union_independent"))
    assert presentation.result.plain == "P(A ∪ B) = 2/3"
    assert presentation.result.latex == r"P(A \cup B) = \frac{2}{3}"
    assert presentation.result.approx is None  # a fraction and a percentage, no decimal
    assert presentation.details["percent"] == "66,67%"
    assert presentation.details["percent_exact"] is False
    assert presentation.details["group"] == "events"
    assert presentation.details["values"] == {"P(A)": "1/2", "P(B)": "1/3"}


def test_presentation_of_counts() -> None:
    presentation = present_probability(run("n = 10; k = 3", "combination"))
    assert presentation.result.plain == "C(10, 3) = 120"
    assert presentation.details["percent"] is None
    assert presentation.details["formula"] == r"C(n, k) = \frac{n!}{k! \, (n - k)!}"
    anagrams = present_probability(run("BANANA", "anagrams"))
    assert anagrams.details["letters"] == [
        {"letter": "B", "count": 1},
        {"letter": "A", "count": 3},
        {"letter": "N", "count": 2},
    ]
    assert anagrams.details["formula"] == r"P_{6}^{3, 2} = \frac{6!}{3! \, 2!}"
    assert anagrams.result.latex == "P_{6}^{3, 2} = 60"  # short enough for a phone
    assert anagrams.result.plain == "anagramas de BANANA = 60"
    assert present_probability(run("AMOR", "anagrams")).result.latex == "P_{4} = 24"


def test_presentation_of_a_binomial_summary() -> None:
    presentation = present_probability(run("n = 10; p = 30%", "binomial_summary"))
    assert presentation.result.plain == "μ = 3; σ² = 21/10; σ = sqrt(210)/10 ≈ 1.44914"
    assert r"\begin{aligned}" in presentation.result.latex
    assert presentation.details["summary"] == {
        "mean": "3",
        "variance": "21/10",
        "std": "sqrt(210)/10",
    }


def test_probability_through_the_pipeline() -> None:
    result = calculate(
        "P(A) = 1/2; P(B) = 1/3; P(A e B) = 1/6", "probability", {"calculation": "union"}
    )
    assert result.success and result.intent == "probability"
    assert result.normalized_input == "P(A) = 1/2; P(B) = 1/3; P(A ∩ B) = 1/6"
    assert result.result is not None and result.result.plain == "P(A ∪ B) = 2/3"
    assert result.verification is not None
    assert result.verification.status is S.VERIFIED_SYMBOLIC

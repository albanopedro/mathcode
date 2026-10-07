"""The second methods and the tools of the verification engine (ADR 0010)."""

import ast
import threading
import time
from fractions import Fraction
from pathlib import Path

import pytest
import sympy as sp

from app.parsing import parse
from app.parsing.build import ExpressionBuilder, symbol
from app.verification import differentiate as differentiate_module
from app.verification.continuity import continuity_obstacle
from app.verification.deadline import StepTimeout, VerificationTimeout, time_limit
from app.verification.differentiate import differentiate
from app.verification.exact import exact_value
from app.verification.newton_leibniz import newton_leibniz
from app.verification.symbolic import compare_constants, reduces_to_zero

x, y = symbol("x"), symbol("y")


def build(text: str) -> sp.Expr:
    return ExpressionBuilder().build(parse(text).tree)


# -- exact rational arithmetic ---------------------------------------------------------------


@pytest.mark.parametrize(
    ("text", "value"),
    [
        ("0.1 + 0.2", Fraction(3, 10)),
        ("2^10 - 1/3", Fraction(3071, 3)),
        ("(-2)^3", Fraction(-8)),
        ("(3/4)^-2", Fraction(16, 9)),
        ("-(2 - 0.5) * 4 / 3", Fraction(-2)),
    ],
)
def test_exact_value(text: str, value: Fraction) -> None:
    assert exact_value(parse(text).tree) == value


@pytest.mark.parametrize("text", ["2^(1/2)", "pi + 1", "sin(1)", "30°", "1/0", "0^0", "0^-1"])
def test_exact_value_out_of_scope(text: str) -> None:
    assert exact_value(parse(text).tree) is None


def test_exact_value_refuses_huge_powers() -> None:
    assert exact_value(parse("10^100000").tree) is None


# -- the second differentiator --------------------------------------------------------------


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("x^3", "3x^2"),
        ("sin(x) cos(x)", "cos(x)^2 - sin(x)^2"),
        ("tan(x)", "1 + tan(x)^2"),
        ("asin(x)", "1/sqrt(1 - x^2)"),
        ("acos(x)", "-1/sqrt(1 - x^2)"),
        ("atan(x)", "1/(1 + x^2)"),
        ("e^(3x)", "3e^(3x)"),
        ("ln(x^2 + 1)", "2x/(x^2 + 1)"),
        ("2^x", "2^x ln(2)"),
        ("x^x", "x^x (ln(x) + 1)"),
        ("sqrt(x)", "1/(2sqrt(x))"),
        ("x y^2", "y^2"),
    ],
)
def test_textbook_rules(text: str, expected: str) -> None:
    derivative = differentiate(build(text), x)
    assert derivative is not None
    assert reduces_to_zero(derivative - build(expected)) is not None


def test_abs_uses_sign_and_sign_is_out_of_scope() -> None:
    assert differentiate(build("abs(x)"), x) == sp.sign(x)
    assert differentiate(build("abs(x)"), x, 2) is None


def test_the_second_differentiator_never_calls_sympys_diff() -> None:
    """Otherwise the comparison would compare SymPy with itself."""
    source = Path(differentiate_module.__file__).read_text()
    calls = {
        node.func.attr if isinstance(node.func, ast.Attribute) else getattr(node.func, "id", "")
        for node in ast.walk(ast.parse(source))
        if isinstance(node, ast.Call)
    }
    assert not calls & {"diff", "Derivative", "derivative", "fdiff"}


# -- continuity -----------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("text", "point"),
    [
        ("x^2 + 1", sp.Integer(2)),
        ("sqrt(x)", sp.Integer(4)),
        ("tan(x)", sp.pi / 4),
        ("ln(x - 1)", sp.Integer(2)),
        ("x^x", sp.Integer(1)),
        ("x^-2", sp.Integer(1)),
        ("acos(x/2)", sp.Integer(1)),
        ("e^x cos(x)", sp.pi),
    ],
)
def test_continuous_at_the_point(text: str, point: sp.Expr) -> None:
    assert continuity_obstacle(parse(text).tree, "x", point) is None


@pytest.mark.parametrize(
    ("text", "point", "why"),
    [
        ("sin(x)/x", sp.Integer(0), "denominador se anula"),
        ("sqrt(x)", sp.Integer(0), "borda do domínio"),
        ("tan(x)", sp.pi / 2, "polo"),
        ("1/(x^2 - 4)", sp.Integer(2), "denominador se anula"),
        ("x^-2", sp.Integer(0), "denominador se anula"),
        ("asin(x)", sp.Integer(1), "borda do domínio"),
        ("x^(1/3)", sp.Integer(0), "borda do domínio"),  # conservative: not claimed
        ("ln(x y)", sp.Integer(1), "não foi possível provar"),  # depends on y
    ],
)
def test_not_proved_continuous(text: str, point: sp.Expr, why: str) -> None:
    obstacle = continuity_obstacle(parse(text).tree, "x", point)
    assert obstacle is not None and why in obstacle


# -- exact comparisons ------------------------------------------------------------------------


def test_reduces_to_zero_says_how() -> None:
    assert reduces_to_zero(sp.Integer(0)) == "diretamente"
    assert reduces_to_zero((x + 1) ** 2 - x**2 - 2 * x - 1) == "expandindo"
    assert reduces_to_zero(1 / (x - 1) - 1 / (x + 1) - 2 / (x**2 - 1)) == "juntando as frações"
    assert reduces_to_zero(sp.sin(x) ** 2 + sp.cos(x) ** 2 - 1) == "simplificando"
    assert reduces_to_zero(x + 1) is None


def test_a_slow_simplify_means_not_proved(monkeypatch: pytest.MonkeyPatch) -> None:
    def slow(expr: sp.Expr) -> sp.Expr:
        time.sleep(5)
        return sp.Integer(0)

    monkeypatch.setattr(sp, "simplify", slow)
    monkeypatch.setattr("app.verification.symbolic.SIMPLIFY_SECONDS", 0.05)

    started = time.monotonic()
    assert reduces_to_zero(sp.sin(x) ** 2 + sp.cos(x) ** 2 - 1) is None
    assert time.monotonic() - started < 1


def test_compare_constants() -> None:
    assert compare_constants(sp.pi / 4, sp.atan(1)).equal is True
    different = compare_constants(sp.Rational(1, 3), sp.Rational(1, 3) + sp.Rational(1, 10**20))
    assert different.equal is False
    assert compare_constants(sp.oo, sp.oo).equal is True
    assert compare_constants(sp.oo, sp.Integer(5)).equal is False


# -- Newton–Leibniz ----------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("integrand", "lower", "upper"),
    [
        (sp.sin(x), 0, 1),  # not a rational function
        (x**2, 0, sp.pi),  # irrational bound
        (x * y, 0, 1),  # another symbol
        (sp.sqrt(2) * x, 0, 1),  # irrational coefficient
    ],
)
def test_newton_leibniz_out_of_scope(integrand: sp.Expr, lower: object, upper: object) -> None:
    assert newton_leibniz(integrand, x, sp.sympify(lower), sp.sympify(upper)) is None


def test_newton_leibniz_refuses_a_pole_in_the_interval() -> None:
    found = newton_leibniz(1 / x, x, sp.Integer(-1), sp.Integer(1))
    assert found is not None and found.value is None
    assert "polo" in found.note


# -- time limits -------------------------------------------------------------------------------


def test_a_step_runs_out_of_time_and_the_rest_goes_on() -> None:
    with time_limit(5):
        with pytest.raises(StepTimeout), time_limit(0.05, step=True):
            time.sleep(2)
        time.sleep(0.1)  # the outer limit is still armed and has time left


def test_the_outer_limit_wins_over_a_step() -> None:
    started = time.monotonic()
    with pytest.raises(VerificationTimeout), time_limit(0.05), time_limit(5, step=True):
        time.sleep(2)
    assert time.monotonic() - started < 1


def test_no_limit_outside_the_main_thread() -> None:
    errors: list[BaseException] = []

    def body() -> None:
        try:
            with time_limit(0.01):
                time.sleep(0.05)
        except BaseException as error:
            errors.append(error)

    thread = threading.Thread(target=body)
    thread.start()
    thread.join()
    assert errors == []

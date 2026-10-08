"""Geometry: points, engine, verification and presentation (ADR 0014)."""

from dataclasses import replace

import pytest
import sympy as sp

from app.calculator import calculate
from app.core.errors import MathError
from app.formatting.results import present_geometry
from app.math_engine.geometry import CATALOG, Classification, GeometryOutcome, Line, geometry
from app.models.intents import Figure, GeometryCalculation, GeometryParams
from app.models.result import VerificationStatus as S
from app.parsing import parse
from app.parsing.ast import ExpressionList, Point
from app.verification.geometry import verify_geometry

pi, sqrt = sp.pi, sp.sqrt


def run(measures: str, figure: Figure, calculation: GeometryCalculation) -> GeometryOutcome:
    return geometry(GeometryParams(measures=measures, figure=figure, calculation=calculation))


# -- points in the parser -------------------------------------------------------------------------


def test_points() -> None:
    tree = parse("(1, 2)").tree
    assert isinstance(tree, Point) and len(tree.coordinates) == 2
    assert isinstance(parse("(1, 2); (4, 6)").tree, ExpressionList)
    assert parse("(1,5, -2)").canonical == "(1.5, -2)"  # "1,5" is still a decimal
    assert parse("(x + 1)").canonical == "x + 1"  # plain parentheses are unchanged


@pytest.mark.parametrize(
    ("text", "message"),
    [("(1, 2, 3, 4)", "2 ou 3 coordenadas"), ("(1, (2, 3))", "são números")],
)
def test_bad_points(text: str, message: str) -> None:
    with pytest.raises(MathError) as exc:
        parse(text)
    assert message in exc.value.message


def test_points_alone_ask_for_a_calculation() -> None:
    result = calculate("(1, 2); (4, 6)")
    assert result.error is not None and "Geometria" in result.error.message


# -- every figure and calculation of the catalog --------------------------------------------------

EXPECTED: list[tuple[str, Figure, GeometryCalculation, object]] = [
    ("r = 5", "circle", "area", 25 * pi),
    ("5", "circle", "perimeter", 10 * pi),  # one measure: its name may be left out
    ("d = 10", "circle", "area", 25 * pi),
    ("l = 4", "square", "area", 16),
    ("l = 4", "square", "perimeter", 16),
    ("b = 4; h = 3", "rectangle", "area", 12),
    ("b = 4; h = 3", "rectangle", "perimeter", 14),
    ("b = 6; h = 4", "triangle", "area", 12),
    ("a = 5; b = 6; c = 7", "triangle", "area", 6 * sqrt(6)),  # Heron
    ("a = 3; b = 4; c = 5", "triangle", "perimeter", 12),
    ("B = 6; b = 4; h = 3", "trapezoid", "area", 15),
    ("D = 6; d = 8", "rhombus", "area", 24),
    ("D = 6; d = 8", "rhombus", "perimeter", 20),
    ("b = 5; h = 2", "parallelogram", "area", 10),
    ("a = 3; b = 5", "parallelogram", "perimeter", 16),
    ("a = 3", "cube", "volume", 27),
    ("a = 3", "cube", "surface_area", 54),
    ("a = 2; b = 3; c = 4", "box", "volume", 24),
    ("a = 2; b = 3; c = 4", "box", "surface_area", 52),
    ("r = 3", "sphere", "volume", 36 * pi),
    ("r = 3", "sphere", "surface_area", 36 * pi),
    ("r = 2; h = 5", "cylinder", "volume", 20 * pi),
    ("r = 2; h = 5", "cylinder", "surface_area", 28 * pi),
    ("r = 3; h = 4", "cone", "volume", 12 * pi),
    ("r = 3; h = 4", "cone", "surface_area", 24 * pi),
    ("a = 3; b = 4", "right_triangle", "missing_side", 5),
    ("b = 5; c = 13", "right_triangle", "missing_side", 12),
    ("(1, 2); (4, 6)", "points", "distance", 5),
    ("(0, 0); (5, 0); (5, 2); (2, 2); (2, 5); (0, 5)", "points", "polygon_area", 16),  # concave
]


@pytest.mark.parametrize(("measures", "figure", "calculation", "expected"), EXPECTED)
def test_results_and_their_verification(
    measures: str, figure: Figure, calculation: GeometryCalculation, expected: object
) -> None:
    outcome = run(measures, figure, calculation)
    assert outcome.result == expected
    report = verify_geometry(outcome)
    assert report.status is S.VERIFIED_SYMBOLIC
    assert any(
        check.kind in ("comparison", "substitution", "symbolic") for check in report.checks[1:]
    )


def test_every_calculation_of_the_catalog_is_tested() -> None:
    tested = {(figure, calculation) for _, figure, calculation, _ in EXPECTED}
    tested |= {
        ("triangle", "classify"),
        ("points", "midpoint"),
        ("points", "line"),
    }
    catalog = {(f, c) for f, spec in CATALOG.items() for c in spec.calculations}
    assert catalog <= tested


@pytest.mark.parametrize(
    ("sides", "by_sides", "by_angles"),
    [
        ("a = 3; b = 4; c = 5", "escaleno", "retângulo"),
        ("a = 2; b = 2; c = 2", "equilátero", "acutângulo"),
        ("a = 2; b = 2; c = 3", "isósceles", "obtusângulo"),
        ("a = 2; b = 3; c = 4", "escaleno", "obtusângulo"),
        ("a = 5; b = 6; c = 7", "escaleno", "acutângulo"),
    ],
)
def test_classification(sides: str, by_sides: str, by_angles: str) -> None:
    outcome = run(sides, "triangle", "classify")
    assert outcome.result == Classification(by_sides, by_angles)
    assert verify_geometry(outcome).status is S.VERIFIED_SYMBOLIC


def test_midpoint_and_line() -> None:
    assert run("(1, 2); (4, 7)", "points", "midpoint").result == (
        sp.Rational(5, 2),
        sp.Rational(9, 2),
    )
    line = run("(1, 2); (4, 6)", "points", "line").result
    assert line == Line(4, -3, -2, sp.Rational(4, 3), sp.Rational(2, 3))
    vertical = run("(1, 2); (1, 6)", "points", "line").result
    assert isinstance(vertical, Line) and vertical.slope is None and vertical.c == 1


@pytest.mark.parametrize(
    ("measures", "figure", "calculation", "message"),
    [
        ("r = 5", "circle", "volume", "cálculos possíveis"),
        ("r = 5", "square", "area", "não é uma medida do quadrado"),
        ("h = 3", "rectangle", "area", "informe: b = 5; h = 3"),
        ("b = 4; h = -3", "rectangle", "area", "positivas"),
        ("b = 4; b = 3", "rectangle", "area", "duas vezes"),
        ("b = 4; h = x", "rectangle", "area", "números"),
        ("a = 1; b = 2; c = 3", "triangle", "area", "não formam um triângulo"),
        ("a = 5; c = 3", "right_triangle", "missing_side", "maior que o cateto"),
        ("(1, 2)", "points", "distance", "dois pontos"),
        ("(1, 2); (1, 2)", "points", "line", "iguais"),
        ("(0, 0); (4, 3); (4, 0); (0, 3)", "points", "polygon_area", "se cruzam"),
        ("(0, 0); (1, 1); (2, 2)", "points", "polygon_area", "alinhados"),
        ("(1, 2, 3); (4, 5, 6)", "points", "line", "pontos do plano"),
        ("r = 5", "points", "distance", "entre parênteses"),
    ],
)
def test_errors_are_explained(
    measures: str, figure: Figure, calculation: GeometryCalculation, message: str
) -> None:
    with pytest.raises(MathError) as exc:
        run(measures, figure, calculation)
    assert message in exc.value.message


# -- verification ---------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("measures", "figure", "calculation"),
    [
        ("r = sqrt(2)", "sphere", "volume"),
        ("a = 1; b = sqrt(3)", "right_triangle", "missing_side"),
        ("(0, 0); (sqrt(2), 1)", "points", "distance"),
    ],
)
def test_irrational_measures_are_verified_numerically(
    measures: str, figure: Figure, calculation: GeometryCalculation
) -> None:
    assert verify_geometry(run(measures, figure, calculation)).status is S.VERIFIED_NUMERIC


@pytest.mark.parametrize(
    ("measures", "figure", "calculation"),
    [(m, f, c) for m, f, c, _ in EXPECTED if f not in ("right_triangle",)],
)
def test_a_wrong_number_is_caught(
    measures: str, figure: Figure, calculation: GeometryCalculation
) -> None:
    outcome = run(measures, figure, calculation)
    report = verify_geometry(replace(outcome, result=outcome.result + 1))  # type: ignore[operator]
    assert report.status is S.FAILED


@pytest.mark.parametrize(
    ("measures", "figure", "calculation", "wrong"),
    [
        ("a = 3; b = 4", "right_triangle", "missing_side", sp.Integer(6)),
        ("a = 3; b = 4; c = 5", "triangle", "classify", Classification("escaleno", "agudo")),
        ("(1, 2); (4, 7)", "points", "midpoint", (sp.Integer(2), sp.Integer(4))),
        (
            "(1, 2); (4, 6)",
            "points",
            "line",
            Line(sp.Integer(1), sp.Integer(-1), sp.Integer(-1), sp.Integer(1), sp.Integer(1)),
        ),
    ],
)
def test_other_wrong_results_are_caught(
    measures: str, figure: Figure, calculation: GeometryCalculation, wrong: object
) -> None:
    outcome = run(measures, figure, calculation)
    assert verify_geometry(replace(outcome, result=wrong)).status is S.FAILED  # type: ignore[arg-type]


def test_a_misread_measure_is_caught() -> None:
    outcome = run("r = 5", "circle", "area")
    assert verify_geometry(replace(outcome, measures={"r": sp.Integer(6)})).status is S.FAILED


# -- presentation -------------------------------------------------------------------------------


def test_presentation() -> None:
    p = present_geometry(run("r = 5", "circle", "area"))
    assert (p.result.plain, p.result.latex) == ("A = 25*pi", r"A = 25 \pi")
    assert p.result.approx == "78.5398163397448"
    assert p.details == {
        "figure": "circle",
        "calculation": "area",
        "measures": {"r": "5"},
        "points": [],
        "formula": r"A = \pi r^2",
        "quantity": "area",
    }


def test_presentation_of_a_line_and_a_classification() -> None:
    line = present_geometry(run("(1, 2); (4, 6)", "points", "line"))
    assert line.result.plain == "y = 4*x/3 + 2/3"
    assert line.details["equation"] == "4*x - 3*y = -2"
    kind = present_geometry(run("a = 3; b = 4; c = 5", "triangle", "classify"))
    assert kind.result.plain == "triângulo escaleno e retângulo"

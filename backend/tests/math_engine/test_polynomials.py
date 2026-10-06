import pytest
import sympy as sp

from app.math_engine.polynomials import (
    Shape,
    count_distinct_real_roots,
    real_roots_with_multiplicity,
    shape,
)
from app.parsing import parse
from app.parsing.build import symbol

x = symbol("x")


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("x^2 + 3x = 1", Shape.POLYNOMIAL),
        ("(x + 1)^3 = 0", Shape.POLYNOMIAL),
        ("1/x = 2", Shape.RATIONAL),
        ("x^(-2) = 4", Shape.RATIONAL),
        ("x/x = 1", Shape.RATIONAL),  # decided from the AST, before SymPy cancels
        ("sqrt(x) = 3", Shape.OTHER),
        ("2^x = 8", Shape.OTHER),
        ("x^0.5 = 2", Shape.OTHER),
        ("x° = 1", Shape.OTHER),
        ("1/x + sin(x) = 0", Shape.OTHER),  # the most general shape wins
    ],
)
def test_shape(text: str, expected: Shape) -> None:
    found, reason = shape(parse(text).tree, "x")
    assert found is expected
    assert (reason is None) == (expected is Shape.POLYNOMIAL)


def test_roots_with_multiplicity_and_sturm_count() -> None:
    poly = sp.Poly((x - 1) ** 3 * (x + 2) * (x**2 + 1), x)
    assert real_roots_with_multiplicity(poly) == [(-2, 1), (1, 3)]
    assert count_distinct_real_roots(poly) == 2

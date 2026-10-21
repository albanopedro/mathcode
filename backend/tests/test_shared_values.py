"""The helpers shared by the engine, the interpreter and the verification."""

from fractions import Fraction

import sympy as sp

from app.core.text import fold
from app.math_engine.values import simplified, to_fraction, to_rational
from app.parsing.angles import degrees_of, radians_of


def test_fold_lowercases_and_drops_the_accents() -> None:
    assert fold("Raízes, Vértice e Gráfico") == "raizes, vertice e grafico"
    assert fold("Círculo") == "circulo"


def test_fold_keeps_one_character_for_each_one() -> None:
    # The rules use the position of the text they matched.
    assert len(fold("ação")) == len("ação")


def test_degrees_of_simplifies() -> None:
    assert degrees_of(sp.pi / 4) == 45
    assert degrees_of(sp.Integer(0)) == 0


def test_radians_of_is_exact() -> None:
    assert radians_of(sp.Integer(30)) == sp.pi / 6
    assert radians_of(sp.Integer(180)) == sp.pi


def test_the_two_conversions_are_inverse() -> None:
    for degrees in (0, 30, 45, 90, 180):
        assert degrees_of(radians_of(sp.Integer(degrees))) == sp.Integer(degrees)


def test_simplified_leaves_a_rational_alone() -> None:
    assert simplified(sp.Rational(3, 4)) == sp.Rational(3, 4)
    assert simplified(sp.sqrt(4)) == 2


def test_the_fraction_conversions_are_exact() -> None:
    assert to_rational(Fraction(3, 4)) == sp.Rational(3, 4)
    assert to_fraction(sp.Rational(3, 4)) == Fraction(3, 4)
    assert to_fraction(to_rational(Fraction(7, 11))) == Fraction(7, 11)

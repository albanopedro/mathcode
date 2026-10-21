"""Angles: the same angle, in degrees or in radians.

The notation ``30°`` is read by the parser, and the same conversion was
written in three other places. Keeping it here means the convention (and the
simplification that goes with it) lives in one place.

The names are ``degrees_of`` and ``radians_of`` and not ``to_degrees`` and
``to_radians`` because the domain already uses ``to_degrees`` for the flag that
says whether the answer is in degrees, and the two would shadow each other.

This module is a leaf: it imports nothing from the project, so any layer can
use it without creating a cycle.
"""

import sympy as sp


def degrees_of(radians: sp.Expr) -> sp.Expr:
    """The angle in degrees, simplified (``pi/4`` becomes ``45``)."""
    return sp.simplify(radians * 180 / sp.pi)


def radians_of(degrees: sp.Expr) -> sp.Expr:
    """The angle in radians (``30`` becomes ``pi/6``)."""
    return degrees * sp.pi / 180

"""SymPy expression -> the three representations shown to the user."""

import sympy as sp
from sympy.printing.str import StrPrinter

APPROX_DIGITS = 15


class _InputSyntaxPrinter(StrPrinter):
    """Prints with the names the user types: abs(x) and e, not Abs(x) and E.

    "E" must not be printed for Euler's number: in the input it is a variable.
    """

    def _print_Abs(self, expr: sp.Abs) -> str:
        return f"abs({self._print(expr.args[0])})"

    def _print_Exp1(self, expr: sp.Expr) -> str:
        return "e"


def plain(expr: sp.Expr) -> str:
    # Same power syntax the user types: x^2, not x**2.
    return _InputSyntaxPrinter().doprint(expr).replace("**", "^")


def latex(expr: sp.Expr) -> str:
    return sp.latex(expr)


def approx(expr: sp.Expr) -> str | None:
    """Decimal approximation, only when the exact form is not already a plain integer."""
    if expr.free_symbols or expr.is_Integer:
        return None
    value = sp.N(expr, APPROX_DIGITS)
    if not value.is_Number:
        return None
    return _trim_zeros(str(value))


def _trim_zeros(text: str) -> str:
    mantissa, separator, exponent = text.partition("e")
    if "." in mantissa:
        mantissa = mantissa.rstrip("0").rstrip(".")
    return mantissa + separator + exponent

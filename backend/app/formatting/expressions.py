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


class _ParserTextPrinter(_InputSyntaxPrinter):
    """Text the safe parser reads back as the same expression: there, log is base 10."""

    def _print_log(self, expr: sp.log) -> str:
        if len(expr.args) != 1:
            raise ValueError("a logarithm with a base has no input syntax")
        return f"ln({self._print(expr.args[0])})"


def plain(expr: sp.Expr) -> str:
    # Same power syntax the user types: x^2, not x**2.
    return _InputSyntaxPrinter().doprint(expr).replace("**", "^")


def parser_text(expr: sp.Expr) -> str:
    """``expr`` as input text that parses back to it (natural log as ln, ADR 0021)."""
    return _ParserTextPrinter().doprint(expr).replace("**", "^")


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

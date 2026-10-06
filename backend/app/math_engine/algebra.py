"""Simplification and first-degree equations (Phase 2). The rest of algebra is Phase 5."""

from dataclasses import dataclass
from enum import StrEnum

import sympy as sp

from app.core.errors import ErrorCode, MathError
from app.core.notices import Notice, NoticeCode
from app.formatting.expressions import plain
from app.math_engine.inputs import require_equation, require_expression
from app.models.intents import SimplifyParams, SolveEquationParams
from app.parsing import ParseResult, parse
from app.parsing.ast import Binary, Call, Degrees, Equation, Node, Number, variables, walk
from app.parsing.build import ExpressionBuilder, ensure_within_limits, symbol

# -- simplify -------------------------------------------------------------------


@dataclass(frozen=True)
class SimplifyOutcome:
    parsed: ParseResult
    tree: Node
    original: sp.Expr
    result: sp.Expr
    notices: tuple[Notice, ...]


def simplify(params: SimplifyParams) -> SimplifyOutcome:
    parsed = parse(params.expression)
    tree = require_expression(parsed)
    builder = ExpressionBuilder()
    original = builder.build(tree)
    result = sp.simplify(original)
    ensure_within_limits(result)
    notices = parsed.notices + tuple(builder.notices) + _domain_notices(builder, result)
    return SimplifyOutcome(parsed, tree, original, result, notices)


def _domain_notices(builder: ExpressionBuilder, result: sp.Expr) -> tuple[Notice, ...]:
    """Points where the original is undefined (a denominator is zero) but the result is not.

    Only denominators with a single variable whose zeros SymPy can list are
    checked; other domain restrictions (sqrt, log) are not detected yet.
    """
    notices: list[Notice] = []
    for denominator in builder.denominators:
        if len(denominator.free_symbols) != 1:
            continue
        (var,) = denominator.free_symbols
        zeros = sp.solveset(denominator, var, domain=sp.S.Reals)
        if not isinstance(zeros, sp.FiniteSet):
            continue
        for zero in zeros:
            if result.subs(var, zero).is_finite:
                notices.append(
                    Notice(
                        NoticeCode.DOMAIN_CHANGED,
                        f"A expressão original não é definida para {var} = {plain(zero)}; "
                        f"o resultado só equivale a ela para {var} ≠ {plain(zero)}.",
                    )
                )
    return tuple(notices)


# -- first-degree equations -------------------------------------------------------


class SolutionKind(StrEnum):
    UNIQUE = "unique"
    NONE = "none"
    ALL_REALS = "all_reals"


@dataclass(frozen=True)
class EquationOutcome:
    parsed: ParseResult
    equation: Equation
    variable: sp.Symbol
    left: sp.Expr
    right: sp.Expr
    kind: SolutionKind
    solution: sp.Expr | None
    notices: tuple[Notice, ...]


def solve_linear(params: SolveEquationParams) -> EquationOutcome:
    parsed = parse(params.equation)
    equation = require_equation(parsed)
    names = variables(equation)
    if not names:
        raise MathError(
            ErrorCode.INVALID_INPUT_FOR_INTENT, "A equação não tem variável para resolver."
        )
    if params.variable is not None and params.variable not in names:
        raise MathError(
            ErrorCode.INVALID_INPUT_FOR_INTENT,
            f"A variável '{params.variable}' não aparece na equação.",
        )
    if len(names) > 1:
        raise MathError(
            ErrorCode.UNSUPPORTED_FEATURE,
            f"Equações com mais de uma variável ({', '.join(sorted(names))}) "
            "ainda não são suportadas.",
        )
    (name,) = names
    _ensure_polynomial(equation, name)

    builder = ExpressionBuilder()
    left = builder.build(equation.left)
    right = builder.build(equation.right)
    var = symbol(name)
    difference = sp.expand(left - right)
    degree = sp.Poly(difference, var).degree()
    if degree > 1:
        raise MathError(
            ErrorCode.UNSUPPORTED_FEATURE,
            f"Esta equação é de grau {degree}. Por enquanto, só equações do 1º grau "
            "são resolvidas.",
        )

    solutions = sp.solveset(difference, var, domain=sp.S.Reals)
    solution: sp.Expr | None = None
    if solutions == sp.S.Reals:
        kind = SolutionKind.ALL_REALS
    elif solutions is sp.S.EmptySet:
        kind = SolutionKind.NONE
    elif isinstance(solutions, sp.FiniteSet) and len(solutions) == 1:
        kind = SolutionKind.UNIQUE
        (solution,) = solutions
    else:
        raise MathError(ErrorCode.UNSUPPORTED_FEATURE, "Não foi possível resolver esta equação.")

    return EquationOutcome(
        parsed=parsed,
        equation=equation,
        variable=var,
        left=left,
        right=right,
        kind=kind,
        solution=solution,
        notices=parsed.notices + tuple(builder.notices),
    )


def _ensure_polynomial(equation: Equation, name: str) -> None:
    """Rejects, from the AST, anything that is not a polynomial in the variable.

    Checked before SymPy simplifies: in "x/x = 1" the variable disappears
    during construction, but the equation is still not first-degree.
    """
    for node in walk(equation):
        match node:
            case Call(name=function) if name in variables(node):
                reason = f"a variável aparece dentro de {function}(...)"
            case Degrees() if name in variables(node):
                reason = "a variável aparece num ângulo em graus"
            case Binary(op="/", right=right) if name in variables(right):
                reason = "a variável aparece num denominador"
            case Binary(op="^", right=right) if name in variables(right):
                reason = "a variável aparece num expoente"
            case Binary(op="^", left=left, right=right) if name in variables(left) and not (
                isinstance(right, Number) and right.value.isdigit()
            ):
                reason = "a variável está elevada a um expoente que não é inteiro positivo"
            case _:
                continue
        raise MathError(
            ErrorCode.UNSUPPORTED_FEATURE,
            f"Por enquanto só equações do 1º grau são resolvidas, e aqui {reason}.",
            node.position,
        )

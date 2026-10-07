"""Cartesian graphs (Phase 7): samples, gaps, y range and relevant points (ADR 0008).

The samples are computed by the AST evaluator of ``verification/numeric.py``:
801 points take about 0.03 s, and every convention of the project (base-10
log, real odd roots, degrees) and every domain cut is applied exactly as in
the rest of the pipeline. Points outside the domain become gaps.

The relevant points (roots and the y-intercept) come from the exact engines
and are checked by the verifier, as for any other intent.
"""

from dataclasses import dataclass
from typing import Literal

import mpmath
import sympy as sp
from mpmath import mp, mpf

from app.core.errors import ErrorCode, MathError
from app.core.limits import GRAPH_SAMPLES, MAX_GRAPH_FUNCTIONS, MAX_GRAPH_WIDTH
from app.core.notices import Notice, NoticeCode
from app.math_engine.calculus import parse_value
from app.math_engine.equations import EquationOutcome, SolutionKind, solve_equation
from app.models.intents import GraphParams, SolveEquationParams
from app.parsing import ParseResult, parse
from app.parsing.ast import Equation, ExpressionList, Node, System, Tree, Variable, variables
from app.parsing.build import ExpressionBuilder, symbol
from app.parsing.printer import to_text
from app.verification.numeric import OutsideDomain, TooLarge, decimal, evaluate

MAX_POINTS_PER_FUNCTION = 20

type PointKind = Literal["root", "y_intercept"]


@dataclass(frozen=True)
class GraphPoint:
    kind: PointKind
    function: int  # index into GraphOutcome.functions
    x: sp.Expr | None  # exact value, when known
    y: sp.Expr | None
    x_value: float
    y_value: float
    x_decimal: str  # full-precision x, for checking (x_value is rounded for display)

    @property
    def exact(self) -> bool:
        return self.x is not None


@dataclass(frozen=True)
class GraphFunction:
    tree: Node
    expr: sp.Expr
    label: str  # the function as understood, e.g. "x^2 - 4*x + 3"
    xs: tuple[float, ...]
    ys: tuple[float | None, ...]  # None: a gap (outside the domain, or an asymptote)
    # The equation f(x) = 0 solved by the exact engine; None when the roots were
    # found numerically (sign changes) or there was nothing to solve.
    equation: EquationOutcome | None
    numeric_roots: bool


@dataclass(frozen=True)
class GraphOutcome:
    parsed: ParseResult
    variable: sp.Symbol
    x_min: sp.Expr
    x_max: sp.Expr
    x_range_text: tuple[str, str]  # as typed ("-2pi"), or the defaults
    functions: tuple[GraphFunction, ...]
    y_range: tuple[float, float]
    y_clipped: bool
    points: tuple[GraphPoint, ...]
    notices: tuple[Notice, ...]


def graph(params: GraphParams) -> GraphOutcome:
    parsed = parse(params.expression)
    trees = _functions(parsed.tree)
    if len(trees) > MAX_GRAPH_FUNCTIONS:
        raise MathError(
            ErrorCode.LIMIT_EXCEEDED,
            f"Um gráfico mostra até {MAX_GRAPH_FUNCTIONS} funções.",
        )
    names = set().union(*(variables(tree) for tree in trees))
    if len(names) > 1:
        raise MathError(
            ErrorCode.UNSUPPORTED_FEATURE,
            f"Gráficos com mais de uma variável ({', '.join(sorted(names))}) ainda não são "
            "suportados.",
        )
    var = symbol(next(iter(names), "x"))
    notices: list[Notice] = list(parsed.notices)
    x_min, x_max = _x_range(params, notices)

    builder = ExpressionBuilder()
    exprs = [builder.build(tree) for tree in trees]
    notices += builder.notices

    xs = _sample_xs(x_min, x_max)
    raw = [[_value(tree, var.name, text) for text in xs] for tree in trees]
    finite = [y for ys in raw for y in ys if y is not None]
    if not finite:
        raise MathError(
            ErrorCode.DOMAIN_ERROR,
            "Nenhuma das funções tem valores reais nessa faixa de x (o domínio é ℝ).",
        )
    (low, high), clipped = _y_range(finite)
    if clipped:
        notices.append(
            Notice(
                NoticeCode.Y_RANGE_CLIPPED,
                "O eixo y foi limitado à parte central dos valores, para que picos perto de "
                "assíntotas não achatem o gráfico. Use o zoom para ver mais.",
            )
        )

    x_floats = [float(text) for text in xs]
    functions: list[GraphFunction] = []
    points: list[GraphPoint] = []
    for index, (tree, expr, ys) in enumerate(zip(trees, exprs, raw, strict=True)):
        gx, gy = _with_gaps(x_floats, ys, low, high)
        roots, equation, numeric = _roots(tree, var, x_min, x_max, xs, ys, index, low, high)
        if len(roots) > MAX_POINTS_PER_FUNCTION:
            roots = roots[:MAX_POINTS_PER_FUNCTION]
            notices.append(
                Notice(
                    NoticeCode.POINTS_TRUNCATED,
                    f"Só as {MAX_POINTS_PER_FUNCTION} primeiras raízes de cada função são "
                    "listadas.",
                )
            )
        if numeric and roots:
            notices.append(
                Notice(
                    NoticeCode.NUMERIC_ROOTS,
                    "Algumas raízes foram encontradas numericamente, pela mudança de sinal; "
                    "raízes em que o gráfico só toca o eixo podem não aparecer.",
                )
            )
        points += roots
        intercept = _y_intercept(tree, expr, var, x_min, x_max, index)
        if intercept is not None:
            points.append(intercept)
        functions.append(
            GraphFunction(tree, expr, to_text(tree), tuple(gx), tuple(gy), equation, numeric)
        )

    return GraphOutcome(
        parsed=parsed,
        variable=var,
        x_min=x_min,
        x_max=x_max,
        x_range_text=(
            (params.x_min or "-10").strip(),
            (params.x_max or "10").strip(),
        ),
        functions=tuple(functions),
        y_range=(low, high),
        y_clipped=clipped,
        points=tuple(points),
        notices=tuple(notices),
    )


# -- input ------------------------------------------------------------------------------------


def _functions(tree: Tree) -> list[Node]:
    """The functions to draw: expressions, or equations written as y = f(x)."""
    match tree:
        case ExpressionList(expressions=expressions):
            return list(expressions)
        case Equation() if _is_y_equals(tree):
            return [tree.right]
        case System(equations=equations) if all(_is_y_equals(eq) for eq in equations):
            return [eq.right for eq in equations]
        case Equation() | System():
            raise MathError(
                ErrorCode.INVALID_INPUT_FOR_INTENT,
                "Para o gráfico, escreva expressões em x, como x^2 - 4, ou y = x^2 - 4.",
            )
        case _:
            return [tree]


def is_graph_input(tree: Tree) -> bool:
    """Used by detection: a list of expressions, or y = f(x)."""
    match tree:
        case ExpressionList():
            return True
        case Equation():
            return _is_y_equals(tree)
        case System(equations=equations):
            return all(_is_y_equals(eq) for eq in equations)
    return False


def _is_y_equals(equation: Equation) -> bool:
    return (
        isinstance(equation.left, Variable)
        and equation.left.name == "y"
        and "y" not in variables(equation.right)
    )


def _x_range(params: GraphParams, notices: list[Notice]) -> tuple[sp.Expr, sp.Expr]:
    bounds: list[sp.Expr] = []
    for text, label, default in (
        (params.x_min, "início da faixa de x", sp.Integer(-10)),
        (params.x_max, "fim da faixa de x", sp.Integer(10)),
    ):
        if text is None:
            bounds.append(default)
            continue
        value, value_notices = parse_value(text, label)
        if value in (sp.oo, -sp.oo):
            raise MathError(
                ErrorCode.INVALID_INPUT_FOR_INTENT, f"O {label} precisa ser um número finito."
            )
        bounds.append(value)
        notices += value_notices
    low, high = bounds
    if not low < high:
        raise MathError(
            ErrorCode.INVALID_INPUT_FOR_INTENT,
            "O início da faixa de x precisa ser menor que o fim.",
        )
    if high - low > MAX_GRAPH_WIDTH:
        raise MathError(
            ErrorCode.LIMIT_EXCEEDED,
            f"A faixa de x pode ter no máximo {MAX_GRAPH_WIDTH} de largura.",
        )
    return low, high


# -- samples ----------------------------------------------------------------------------------


def _sample_xs(x_min: sp.Expr, x_max: sp.Expr) -> list[str]:
    """Evenly spaced points as exact decimal text (the evaluator's input format)."""
    with mp.workdps(30):
        low, high = mpf(str(sp.N(x_min, 30))), mpf(str(sp.N(x_max, 30)))
        step = (high - low) / (GRAPH_SAMPLES - 1)
        return [mpmath.nstr(low + i * step, 20) for i in range(GRAPH_SAMPLES)]


def _value(tree: Node, name: str, x: str) -> float | None:
    try:
        value = float(evaluate(tree, {name: x}).value)
    except OutsideDomain, TooLarge, OverflowError:
        return None
    return value if abs(value) < 1e300 else None


def _y_range(values: list[float]) -> tuple[tuple[float, float], bool]:
    """The visible y range. Outliers (near asymptotes) are cut, not shown."""
    ordered = sorted(values)
    last = len(ordered) - 1
    low_all, high_all = ordered[0], ordered[-1]
    p_low, p_high = ordered[int(0.02 * last)], ordered[int(0.98 * last)]
    core = p_high - p_low or max(1.0, abs(p_high))
    if high_all - low_all <= 3 * core:
        low, high, clipped = low_all, high_all, False
    else:
        low, high, clipped = p_low - 0.25 * core, p_high + 0.25 * core, True
    pad = 0.05 * (high - low) or 1.0
    return (_round(low - pad), _round(high + pad)), clipped


def _with_gaps(
    xs: list[float], ys: list[float | None], low: float, high: float
) -> tuple[list[float], list[float | None]]:
    """Breaks the line across a jump over the whole visible range (an asymptote)."""
    span = high - low
    gx: list[float] = []
    gy: list[float | None] = []
    for i, (x, y) in enumerate(zip(xs, ys, strict=True)):
        if i > 0:
            previous = ys[i - 1]
            if (
                previous is not None
                and y is not None
                and previous * y < 0
                and abs(y - previous) > span
            ):
                gx.append(_round((xs[i - 1] + x) / 2))
                gy.append(None)
        gx.append(_round(x))
        gy.append(None if y is None else _round(y))
    return gx, gy


def _round(value: float) -> float:
    return float(f"{value:.10g}")


# -- relevant points ----------------------------------------------------------------------------


def _roots(
    tree: Node,
    var: sp.Symbol,
    x_min: sp.Expr,
    x_max: sp.Expr,
    xs: list[str],
    ys: list[float | None],
    index: int,
    low: float,
    high: float,
) -> tuple[list[GraphPoint], EquationOutcome | None, bool]:
    """Roots inside [x_min, x_max]: exact when the equation engine solves f(x) = 0."""
    if not variables(tree):
        return [], None, False  # a constant: zero everywhere or nowhere
    try:
        outcome = solve_equation(
            SolveEquationParams(equation=f"{to_text(tree)} = 0", variable=var.name)
        )
    except MathError:
        outcome = None

    if outcome is not None:
        if outcome.kind is SolutionKind.ALL_REALS:
            return [], outcome, False
        low, high = float(sp.N(x_min, 20)), float(sp.N(x_max, 20))
        points = [
            GraphPoint("root", index, root, sp.Integer(0), _round(value), 0.0, decimal(root))
            for root in outcome.solutions
            if low <= (value := float(sp.N(root, 20))) <= high
        ]
        return points, outcome, False
    return _numeric_roots(tree, var.name, xs, ys, index, y_scale(low, high)), None, True


def y_scale(low: float, high: float) -> float:
    """Size of the visible values. Not max|y|: near a pole that is ~1e14."""
    return max(1.0, abs(low), abs(high))


def _numeric_roots(
    tree: Node, name: str, xs: list[str], ys: list[float | None], index: int, scale: float
) -> list[GraphPoint]:
    """Sign changes between samples, refined by bisection on the evaluator."""
    points: list[GraphPoint] = []

    def f(t: mpf) -> mpf:
        return evaluate(tree, {name: mpmath.nstr(t, 50)}).value

    # A sample this small is a zero (sin(2pi) is ~1e-30 at the 20-digit sample).
    tiny = 1e-12 * scale

    def zero(y: float | None) -> bool:
        return y is not None and abs(y) <= tiny

    for i, right in enumerate(ys):
        if right is None:
            continue
        if zero(right):
            # A zero at a sample (sin at x = 0): bisection would need a sign change.
            if i == 0 or not zero(ys[i - 1]):
                points.append(
                    GraphPoint("root", index, None, None, _round(float(xs[i])), 0.0, xs[i])
                )
            continue
        left = ys[i - 1] if i > 0 else None
        if left is None or zero(left) or left * right > 0:
            continue
        try:
            with mp.workdps(40):
                root = mpmath.findroot(f, (mpf(xs[i - 1]), mpf(xs[i])), solver="bisect")
                residual = abs(f(root))
        except OutsideDomain, TooLarge, ValueError, ZeroDivisionError:
            continue
        # A pole also changes sign: keep only true zeros.
        if residual < mpf("1e-20"):
            points.append(
                GraphPoint(
                    "root", index, None, None, _round(float(root)), 0.0, mpmath.nstr(root, 40)
                )
            )
    return points


def _y_intercept(
    tree: Node, expr: sp.Expr, var: sp.Symbol, x_min: sp.Expr, x_max: sp.Expr, index: int
) -> GraphPoint | None:
    if not (x_min <= 0 <= x_max):
        return None
    try:
        evaluate(tree, {var.name: "0"})
    except OutsideDomain, TooLarge:
        return None  # 0 is outside the domain
    value = sp.simplify(expr.subs(var, 0))
    if not value.is_number or not value.is_finite or value.has(sp.I):
        return None
    return GraphPoint("y_intercept", index, sp.Integer(0), value, 0.0, _round(float(value)), "0")

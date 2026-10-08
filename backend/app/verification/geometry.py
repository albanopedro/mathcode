"""Verification of geometry results (ADR 0014).

The measures and points are read again from the parser's tree without SymPy
(fractions when rational, the mpmath evaluator otherwise). Then the result is
obtained by a different method from the formula the engine used:

- polygons: the vertices of a figure with those measures, and the shoelace
  formula (area) or the sum of the sides (perimeter);
- triangle by its sides: coordinates of its vertices (instead of Heron);
- circle and solids: integration (area under a curve, solid and surface of
  revolution), a different method from the closed formula;
- Pythagoras: the sides found satisfy a² + b² = c²;
- classification: sides compared and the largest angle by a dot product;
- points: d² = Σ(Δ)², M equidistant from both points, both points on the
  line, the polygon's area by a fan of triangles (instead of the shoelace).
"""

from collections.abc import Callable
from itertools import pairwise

import sympy as sp

from app.formatting.expressions import plain
from app.math_engine.geometry import Classification, GeometryOutcome, Line
from app.models.result import (
    CheckKind,
    ReasonCode,
    VerificationCheck,
    VerificationReport,
    VerificationStatus,
)
from app.parsing.ast import Node
from app.parsing.build import symbol
from app.verification.deadline import StepTimeout, time_limit
from app.verification.exact import exact_value
from app.verification.numeric import Evaluation, OutsideDomain, TooLarge, agrees, evaluate, to_mpf
from app.verification.reports import failure, inconclusive, passed, report, unverified
from app.verification.symbolic import compare_constants

INTEGRATION_SECONDS = 1.5
x = symbol("x")

type Vertex = tuple[sp.Expr, sp.Expr]
type Method = Callable[[], tuple[str, sp.Expr] | None]


# -- reading again ----------------------------------------------------------------------------


class _Reread:
    """Each value read again from its expression: exactly when possible."""

    def __init__(self) -> None:
        self.exact = True

    def value(self, node: Node, engine: sp.Expr) -> sp.Expr | None:
        """The value (exact, or the engine's after a numeric match); None on a mismatch."""
        fraction = exact_value(node)
        if fraction is not None:
            value = sp.Rational(fraction.numerator, fraction.denominator)
            return value if value == engine else None
        self.exact = False
        try:
            evaluation = evaluate(node)
        except OutsideDomain, TooLarge:
            return None
        actual = to_mpf(engine)
        return engine if actual is not None and agrees(evaluation, actual) else None


def _numerically_equal(a: sp.Expr, b: sp.Expr) -> bool:
    first, second = to_mpf(a), to_mpf(b)
    return first is not None and second is not None and agrees(Evaluation(second, 0), first)


# -- second methods -------------------------------------------------------------------------------


def _shoelace(vertices: list[Vertex]) -> sp.Expr:
    pairs = zip(vertices, vertices[1:] + vertices[:1], strict=True)
    return sp.Abs(sum(x1 * y2 - x2 * y1 for (x1, y1), (x2, y2) in pairs)) / 2


def _sides(vertices: list[Vertex]) -> sp.Expr:
    pairs = zip(vertices, vertices[1:] + vertices[:1], strict=True)
    return sum(sp.sqrt((x2 - x1) ** 2 + (y2 - y1) ** 2) for (x1, y1), (x2, y2) in pairs)


def _integral(integrand: sp.Expr, low: sp.Expr, high: sp.Expr) -> sp.Expr:
    return sp.integrate(integrand, (x, low, high))


def _revolution_surface(radius: sp.Expr, low: sp.Expr, high: sp.Expr) -> sp.Expr:
    """2π ∫ f √(1 + f'²) dx: the surface swept by y = f(x) around the x axis."""
    slope = sp.diff(radius, x)
    return 2 * sp.pi * _integral(sp.simplify(radius * sp.sqrt(1 + slope**2)), low, high)


def _vertices(figure: str, m: dict[str, sp.Expr], calculation: str) -> list[Vertex] | None:
    zero, one = sp.Integer(0), sp.Integer(1)
    match figure:
        case "square":
            side = m["l"]
            return [(zero, zero), (side, zero), (side, side), (zero, side)]
        case "rectangle":
            return [(zero, zero), (m["b"], zero), (m["b"], m["h"]), (zero, m["h"])]
        case "trapezoid":
            return [(zero, zero), (m["B"], zero), (m["b"], m["h"]), (zero, m["h"])]
        case "rhombus":
            half, half_minor = m["D"] / 2, m["d"] / 2
            return [(half, zero), (zero, half_minor), (-half, zero), (zero, -half_minor)]
        case "parallelogram" if calculation == "area":
            # Any slant: shearing does not change the area.
            return [(zero, zero), (m["b"], zero), (m["b"] + one, m["h"]), (one, m["h"])]
        case "parallelogram":
            return [(zero, zero), (m["b"], zero), (m["b"], m["a"]), (zero, m["a"])]
        case "triangle" if "h" in m:
            return [(zero, zero), (m["b"], zero), (zero, m["h"])]
        case "triangle":
            # A = (0, 0), B = (c, 0) and C from |AC| = b, |BC| = a.
            a, b, c = m["a"], m["b"], m["c"]
            cx = (b**2 + c**2 - a**2) / (2 * c)
            return [(zero, zero), (c, zero), (cx, sp.sqrt(b**2 - cx**2))]
    return None


def _second_method(outcome: GeometryOutcome, m: dict[str, sp.Expr]) -> tuple[str, sp.Expr] | None:
    """(how it was obtained, value) by another method; None when there is none."""
    figure, calculation = outcome.figure, outcome.calculation
    vertices = _vertices(figure, m, calculation)
    if vertices is not None and calculation == "area":
        return (
            "Pelos vértices de uma figura com essas medidas, a área pela fórmula do cadarço "
            "(produtos cruzados) é a mesma.",
            _shoelace(vertices),
        )
    if vertices is not None and calculation == "perimeter":
        return (
            "Pelos vértices de uma figura com essas medidas, a soma das distâncias entre "
            "vértices consecutivos dá o mesmo perímetro.",
            _sides(vertices),
        )
    r, h = m.get("r", sp.Integer(0)), m.get("h", sp.Integer(0))
    match figure, calculation:
        case "circle", _:
            r = m["r"] if "r" in m else m["d"] / 2
            if calculation == "area":
                return (
                    "Integrando a altura do círculo, ∫ 2√(r² − x²) dx de −r a r, a área é a mesma.",
                    _integral(2 * sp.sqrt(r**2 - x**2), -r, r),
                )
            return (
                "Pelo comprimento de arco, 2 ∫ r/√(r² − x²) dx de −r a r, a circunferência é a "
                "mesma.",
                _integral(2 * r / sp.sqrt(r**2 - x**2), -r, r),
            )
        case "sphere", "volume":
            return (
                "Como sólido de revolução, ∫ π(r² − x²) dx de −r a r, o volume é o mesmo.",
                _integral(sp.pi * (r**2 - x**2), -r, r),
            )
        case "sphere", _:
            return (
                "Como superfície de revolução de y = √(r² − x²), a área é a mesma.",
                _revolution_surface(sp.sqrt(r**2 - x**2), -r, r),
            )
        case "cylinder", "volume":
            return (
                "Como sólido de revolução, ∫ π r² dx de 0 a h, o volume é o mesmo.",
                _integral(sp.pi * r**2 + 0 * x, 0, h),
            )
        case "cylinder", _:
            return (
                "Somando a superfície de revolução lateral e os dois círculos, a área é a mesma.",
                _revolution_surface(r + 0 * x, 0, h) + 2 * sp.pi * r**2,
            )
        case "cone", "volume":
            return (
                "Como sólido de revolução, ∫ π (r·x/h)² dx de 0 a h, o volume é o mesmo.",
                _integral(sp.pi * (r * x / h) ** 2, 0, h),
            )
        case "cone", _:
            return (
                "Somando a superfície de revolução lateral e o círculo da base, a área é a mesma.",
                _revolution_surface(r * x / h, 0, h) + sp.pi * r**2,
            )
        case "cube", "volume":
            return (
                "Integrando a área da seção (a²) ao longo da aresta, o volume é o mesmo.",
                _integral(m["a"] ** 2 + 0 * x, 0, m["a"]),
            )
        case "cube", _:
            return (
                "Base e topo mais as faces laterais (perímetro × altura) somam a mesma área.",
                2 * m["a"] ** 2 + 4 * m["a"] * m["a"],
            )
        case "box", "volume":
            return (
                "Integrando a área da seção (a·b) ao longo da altura, o volume é o mesmo.",
                _integral(m["a"] * m["b"] + 0 * x, 0, m["c"]),
            )
        case "box", _:
            a, b, c = m["a"], m["b"], m["c"]
            return (
                "Base e topo mais as faces laterais (perímetro × altura) somam a mesma área.",
                2 * a * b + 2 * (a + b) * c,
            )
    return None


# -- the verifier ---------------------------------------------------------------------------------


def verify_geometry(outcome: GeometryOutcome) -> VerificationReport:
    reread = _Reread()
    m: dict[str, sp.Expr] = {}
    for name, node in outcome.measure_nodes.items():
        value = reread.value(node, outcome.measures[name])
        if value is None:
            return failure(
                CheckKind.COMPARISON, f"Relendo a medida {name}, ela não é a usada no cálculo."
            )
        m[name] = value
    points: list[tuple[sp.Expr, ...]] = []
    for node, point in zip(outcome.point_nodes, outcome.points, strict=True):
        coordinates = [reread.value(c, v) for c, v in zip(node.coordinates, point, strict=True)]
        if any(c is None for c in coordinates):
            return failure(
                CheckKind.COMPARISON, "Relendo os pontos, eles não são os usados no cálculo."
            )
        points.append(tuple(c for c in coordinates if c is not None))

    what = "Os pontos" if outcome.figure == "points" else "As medidas"
    checks: list[VerificationCheck] = [
        passed(
            CheckKind.COMPARISON if reread.exact else CheckKind.NUMERIC,
            f"{what}, relidos da expressão sem o SymPy, são os usados no cálculo."
            if outcome.figure == "points"
            else f"{what}, relidas da expressão sem o SymPy, são as usadas no cálculo.",
        )
    ]
    verified = (
        VerificationStatus.VERIFIED_SYMBOLIC
        if reread.exact
        else VerificationStatus.VERIFIED_NUMERIC
    )

    result = outcome.result
    if isinstance(result, Classification):
        return _verify_classification(m, result, checks, verified)
    if outcome.figure == "points":
        return _verify_points(outcome.calculation, points, result, checks, verified)
    if isinstance(result, Line | tuple):
        raise AssertionError("a measure of a figure is a number")
    if outcome.figure == "right_triangle":
        return _verify_pythagoras(outcome.symbol, m, result, checks, verified)
    return _compare(lambda: _second_method(outcome, m), result, checks, verified)


def _compare(
    method: Method,
    result: sp.Expr,
    checks: list[VerificationCheck],
    verified: VerificationStatus,
) -> VerificationReport:
    try:
        with time_limit(INTEGRATION_SECONDS, step=True):
            found = method()
            verdict = None if found is None else compare_constants(result, found[1])
    except StepTimeout:
        checks.append(inconclusive(CheckKind.COMPARISON, "O segundo método não terminou a tempo."))
        return report(VerificationStatus.PARTIAL, checks, ReasonCode.DEADLINE)
    if found is None or verdict is None:
        return unverified(
            ReasonCode.NO_STRATEGY,
            CheckKind.COMPARISON,
            "Não há um segundo método para este cálculo.",
            *checks,
        )
    how, value = found
    if verdict.equal is False:
        return failure(
            CheckKind.COMPARISON,
            f"Por um segundo método, o valor é {plain(value)}, e não {plain(result)}.",
            *checks,
        )
    if verdict.equal is None:  # not shown equal exactly: are they equal numerically?
        if not _numerically_equal(result, value):
            checks.append(inconclusive(CheckKind.COMPARISON, how))
            return report(VerificationStatus.PARTIAL, checks, ReasonCode.INCONCLUSIVE)
        checks.append(passed(CheckKind.NUMERIC, f"{how} (conferido em 30 algarismos)"))
        return report(VerificationStatus.VERIFIED_NUMERIC, checks)
    checks.append(passed(CheckKind.COMPARISON, how))
    return report(verified, checks)


def _verify_pythagoras(
    found: str,
    m: dict[str, sp.Expr],
    result: sp.Expr,
    checks: list[VerificationCheck],
    verified: VerificationStatus,
) -> VerificationReport:
    sides = {**m, found: result}
    verdict = compare_constants(sides["a"] ** 2 + sides["b"] ** 2, sides["c"] ** 2)
    if verdict.equal is not True or result.is_positive is not True:
        return failure(
            CheckKind.SUBSTITUTION, "Os três lados não satisfazem a² + b² = c².", *checks
        )
    checks.append(
        passed(
            CheckKind.SUBSTITUTION,
            f"Com {found} = {plain(result)}, os três lados satisfazem a² + b² = c² (substituindo).",
        )
    )
    return report(verified, checks)


def _verify_classification(
    m: dict[str, sp.Expr],
    result: Classification,
    checks: list[VerificationCheck],
    verified: VerificationStatus,
) -> VerificationReport:
    a, b, c = m["a"], m["b"], m["c"]
    equal = sum(1 for p, q in ((a, b), (b, c), (a, c)) if compare_constants(p, q).equal)
    by_sides = "equilátero" if equal == 3 else "isósceles" if equal == 1 else "escaleno"

    # The largest angle is at the vertex opposite the longest side (a is opposite A...).
    vertices = _vertices("triangle", m, "classify")
    if vertices is None:
        raise AssertionError("a triangle by its sides has vertices")
    longest = max(range(3), key=lambda i: float((a, b, c)[i]))
    corner = vertices[longest]
    p, q = (vertices[i] for i in range(3) if i != longest)
    dot = (p[0] - corner[0]) * (q[0] - corner[0]) + (p[1] - corner[1]) * (q[1] - corner[1])
    if compare_constants(dot, sp.Integer(0)).equal:
        by_angles = "retângulo"
    else:
        value = to_mpf(dot)
        by_angles = "acutângulo" if value is not None and value > 0 else "obtusângulo"

    if (by_sides, by_angles) != (result.by_sides, result.by_angles):
        return failure(
            CheckKind.COMPARISON,
            f"Comparando os lados e o maior ângulo pelas coordenadas: {by_sides} e {by_angles}.",
            *checks,
        )
    checks.append(
        passed(
            CheckKind.COMPARISON,
            "Comparando os lados e o sinal do produto escalar no vértice do maior ângulo "
            "(pelas coordenadas do triângulo), a classificação é a mesma.",
        )
    )
    return report(verified, checks)


def _verify_points(
    calculation: str,
    points: list[tuple[sp.Expr, ...]],
    result: sp.Expr | tuple[sp.Expr, ...] | Line | Classification,
    checks: list[VerificationCheck],
    verified: VerificationStatus,
) -> VerificationReport:
    if calculation == "distance" and isinstance(result, sp.Expr):
        p, q = points
        squares = sum((u - v) ** 2 for u, v in zip(p, q, strict=True))
        if compare_constants(result**2, squares).equal is not True or result.is_negative:
            return failure(
                CheckKind.SYMBOLIC, "d² não é a soma dos quadrados das diferenças.", *checks
            )
        checks.append(
            passed(CheckKind.SYMBOLIC, f"d² = {plain(squares)} = Σ (diferenças)², e d ≥ 0.")
        )
        return report(verified, checks)

    if calculation == "midpoint" and isinstance(result, tuple):
        p, q = points
        averages = [(u + v) / 2 for u, v in zip(p, q, strict=True)]
        if any(
            compare_constants(av, r).equal is not True
            for av, r in zip(averages, result, strict=True)
        ):
            return failure(CheckKind.COMPARISON, "As médias das coordenadas são outras.", *checks)
        to_p = sum((u - r) ** 2 for u, r in zip(p, result, strict=True))
        to_q = sum((v - r) ** 2 for v, r in zip(q, result, strict=True))
        if compare_constants(to_p, to_q).equal is not True:
            return failure(
                CheckKind.SYMBOLIC, "M não está à mesma distância dos dois pontos.", *checks
            )
        checks += [
            passed(CheckKind.COMPARISON, "As médias das coordenadas, refeitas, são as mesmas."),
            passed(CheckKind.SYMBOLIC, "M está à mesma distância dos dois pontos."),
        ]
        return report(verified, checks)

    if calculation == "line" and isinstance(result, Line):
        for px, py in points:
            if compare_constants(result.a * px + result.b * py, result.c).equal is not True:
                return failure(
                    CheckKind.SUBSTITUTION,
                    f"O ponto ({plain(px)}, {plain(py)}) não está na reta.",
                    *checks,
                )
        checks.append(
            passed(
                CheckKind.SUBSTITUTION,
                "Substituindo os dois pontos na equação da reta, ela vale nos dois.",
            )
        )
        if result.slope is not None:
            (x1, y1), (x2, y2) = points
            if compare_constants(result.slope, (y2 - y1) / (x2 - x1)).equal is not True:
                return failure(CheckKind.COMPARISON, "A inclinação Δy/Δx é outra.", *checks)
            checks.append(passed(CheckKind.COMPARISON, "A inclinação Δy/Δx, refeita, é a mesma."))
        return report(verified, checks)

    if calculation == "polygon_area" and isinstance(result, sp.Expr):
        x0, y0 = points[0]
        fan = sum(
            (x1 - x0) * (y2 - y0) - (x2 - x0) * (y1 - y0)
            for (x1, y1), (x2, y2) in pairwise(points[1:])
        )
        return _compare(
            lambda: (
                "Dividindo o polígono em triângulos a partir do primeiro vértice (em vez da "
                "fórmula do cadarço), a área é a mesma.",
                sp.Abs(fan) / 2,
            ),
            result,
            checks,
            verified,
        )
    raise AssertionError(f"unexpected result for {calculation}")

"""Geometry with exact numbers (Phase 10, ADR 0014).

A figure is described by named measures ("r = 5", "b = 4; h = 3") or, in
analytic geometry, by points ("(1, 2); (4, 6)"). The catalog below says, for
each figure, which measures exist and which sets of them each calculation
needs; everything else (missing, extra or non-positive measures, impossible
triangles) is refused with an explanation. Results are exact: π stays π.
"""

from dataclasses import dataclass, field

import sympy as sp

from app.core.errors import ErrorCode, MathError
from app.core.notices import Notice
from app.models.intents import Figure, GeometryCalculation, GeometryParams
from app.parsing import ParseResult, parse
from app.parsing.ast import (
    Equation,
    ExpressionList,
    Node,
    Point,
    System,
    Variable,
    has_brackets,
    has_points,
    variables,
)
from app.parsing.build import ExpressionBuilder, ensure_within_limits

type Needs = tuple[frozenset[str], ...]  # alternative sets of measures


@dataclass(frozen=True)
class FigureSpec:
    label: str  # with its article: "o círculo", "a esfera"
    measures: dict[str, str]  # symbol -> what it is
    calculations: dict[GeometryCalculation, Needs]

    @property
    def of(self) -> str:
        """'do círculo', 'da esfera', 'dos pontos'."""
        article, name = self.label.split(" ", 1)
        return f"d{article} {name}"


def _sets(*alternatives: str) -> Needs:
    return tuple(frozenset(alternative.split()) for alternative in alternatives)


CATALOG: dict[Figure, FigureSpec] = {
    "circle": FigureSpec(
        "o círculo",
        {"r": "raio", "d": "diâmetro"},
        {"area": _sets("r", "d"), "perimeter": _sets("r", "d")},
    ),
    "square": FigureSpec(
        "o quadrado", {"l": "lado"}, {"area": _sets("l"), "perimeter": _sets("l")}
    ),
    "rectangle": FigureSpec(
        "o retângulo",
        {"b": "base", "h": "altura"},
        {"area": _sets("b h"), "perimeter": _sets("b h")},
    ),
    "triangle": FigureSpec(
        "o triângulo",
        {"a": "lado a", "b": "lado b (ou a base)", "c": "lado c", "h": "altura"},
        {
            "area": _sets("b h", "a b c"),
            "perimeter": _sets("a b c"),
            "classify": _sets("a b c"),
        },
    ),
    "trapezoid": FigureSpec(
        "o trapézio",
        {"B": "base maior", "b": "base menor", "h": "altura"},
        {"area": _sets("B b h")},
    ),
    "rhombus": FigureSpec(
        "o losango",
        {"D": "diagonal maior", "d": "diagonal menor"},
        {"area": _sets("D d"), "perimeter": _sets("D d")},
    ),
    "parallelogram": FigureSpec(
        "o paralelogramo",
        {"b": "base", "h": "altura", "a": "lado"},
        {"area": _sets("b h"), "perimeter": _sets("a b")},
    ),
    "cube": FigureSpec(
        "o cubo", {"a": "aresta"}, {"volume": _sets("a"), "surface_area": _sets("a")}
    ),
    "box": FigureSpec(
        "o paralelepípedo",
        {"a": "comprimento", "b": "largura", "c": "altura"},
        {"volume": _sets("a b c"), "surface_area": _sets("a b c")},
    ),
    "sphere": FigureSpec(
        "a esfera", {"r": "raio"}, {"volume": _sets("r"), "surface_area": _sets("r")}
    ),
    "cylinder": FigureSpec(
        "o cilindro",
        {"r": "raio", "h": "altura"},
        {"volume": _sets("r h"), "surface_area": _sets("r h")},
    ),
    "cone": FigureSpec(
        "o cone",
        {"r": "raio", "h": "altura"},
        {"volume": _sets("r h"), "surface_area": _sets("r h")},
    ),
    "right_triangle": FigureSpec(
        "o triângulo retângulo",
        {"a": "cateto a", "b": "cateto b", "c": "hipotenusa"},
        {"missing_side": _sets("a b", "a c", "b c")},
    ),
    "points": FigureSpec(
        "os pontos",
        {},
        {"distance": (), "midpoint": (), "line": (), "polygon_area": ()},
    ),
}

CALCULATION_LABELS: dict[GeometryCalculation, str] = {
    "area": "a área",
    "perimeter": "o perímetro",
    "volume": "o volume",
    "surface_area": "a área da superfície",
    "classify": "a classificação",
    "missing_side": "o lado que falta",
    "distance": "a distância",
    "midpoint": "o ponto médio",
    "line": "a reta",
    "polygon_area": "a área do polígono",
}

PI = sp.pi


@dataclass(frozen=True)
class Line:
    """a·x + b·y = c through two points; ``slope`` None for a vertical line."""

    a: sp.Expr
    b: sp.Expr
    c: sp.Expr
    slope: sp.Expr | None
    intercept: sp.Expr | None


@dataclass(frozen=True)
class Classification:
    by_sides: str  # equilátero, isósceles, escaleno
    by_angles: str  # acutângulo, retângulo, obtusângulo


type GeometryResult = sp.Expr | tuple[sp.Expr, ...] | Line | Classification


@dataclass(frozen=True)
class GeometryOutcome:
    parsed: ParseResult
    figure: Figure
    calculation: GeometryCalculation
    measures: dict[str, sp.Expr]  # symbol -> value (empty for points)
    measure_nodes: dict[str, Node]  # the expression of each value, for the verifier
    points: tuple[tuple[sp.Expr, ...], ...]
    point_nodes: tuple[Point, ...]
    result: GeometryResult
    symbol: str  # what the result is called: A, P, V, S, d, c, M...
    formula: str  # LaTeX of the formula used
    notices: tuple[Notice, ...] = field(default_factory=tuple)


def geometry(params: GeometryParams) -> GeometryOutcome:
    spec = CATALOG[params.figure]
    if params.calculation not in spec.calculations:
        possible = ", ".join(CALCULATION_LABELS[c] for c in spec.calculations)
        raise MathError(
            ErrorCode.INVALID_INPUT_FOR_INTENT,
            f"Para {spec.label}, os cálculos possíveis são: {possible}.",
        )
    parsed = parse(params.measures)
    builder = ExpressionBuilder()
    if params.figure == "points":
        point_nodes, points = _read_points(parsed, builder)
        result, symbol, formula = _analytic(params.calculation, points)
        measures: dict[str, sp.Expr] = {}
        nodes: dict[str, Node] = {}
    else:
        point_nodes, points = (), ()
        nodes, measures = _read_measures(parsed, builder, params.figure, params.calculation)
        result, symbol, formula = _figure(params.figure, params.calculation, measures)
    for value in _numbers(result):
        ensure_within_limits(value)
    return GeometryOutcome(
        parsed=parsed,
        figure=params.figure,
        calculation=params.calculation,
        measures=measures,
        measure_nodes=nodes,
        points=points,
        point_nodes=point_nodes,
        result=result,
        symbol=symbol,
        formula=formula,
        notices=(*parsed.notices, *builder.notices),
    )


def _numbers(result: GeometryResult) -> list[sp.Expr]:
    if isinstance(result, Line):
        return [result.a, result.b, result.c]
    if isinstance(result, Classification):
        return []
    if isinstance(result, tuple):
        return list(result)
    return [result]


# -- reading the measures -------------------------------------------------------------------------


def _number(node: Node, builder: ExpressionBuilder) -> sp.Expr:
    if variables(node) or has_brackets(node) or has_points(node):
        raise MathError(
            ErrorCode.INVALID_INPUT_FOR_INTENT,
            "As medidas precisam ser números, como em r = 5 ou b = 2,5.",
            node.position,
        )
    value = builder.build(node)
    if value.is_extended_real is False or value.has(sp.I):
        raise MathError(ErrorCode.DOMAIN_ERROR, "A medida não é um número real.", node.position)
    return value


def _read_measures(
    parsed: ParseResult,
    builder: ExpressionBuilder,
    figure: Figure,
    calculation: GeometryCalculation,
) -> tuple[dict[str, Node], dict[str, sp.Expr]]:
    spec = CATALOG[figure]
    alternatives = spec.calculations[calculation]
    tree = parsed.tree
    example = _example(spec, alternatives[0])

    if isinstance(tree, Equation):
        equations = [tree]
    elif isinstance(tree, System):
        equations = list(tree.equations)
    elif isinstance(tree, ExpressionList) or has_points(tree):
        raise MathError(
            ErrorCode.INVALID_INPUT_FOR_INTENT,
            f"Escreva as medidas com o nome de cada uma: {example}.",
        )
    elif len(alternatives[0]) == 1:  # "5" for the radius of a circle
        (name,) = alternatives[0]
        return {name: tree}, {name: _positive(name, _number(tree, builder), tree)}
    else:
        raise MathError(
            ErrorCode.INVALID_INPUT_FOR_INTENT,
            f"Informe as medidas com o nome de cada uma: {example}.",
        )

    nodes: dict[str, Node] = {}
    values: dict[str, sp.Expr] = {}
    for equation in equations:
        if not isinstance(equation.left, Variable):
            raise MathError(
                ErrorCode.INVALID_INPUT_FOR_INTENT,
                f"À esquerda do '=' vai o nome da medida: {example}.",
                equation.left.position,
            )
        name = equation.left.name
        if name not in spec.measures:
            known = ", ".join(f"{s} ({label})" for s, label in spec.measures.items())
            raise MathError(
                ErrorCode.INVALID_INPUT_FOR_INTENT,
                f"'{name}' não é uma medida {spec.of}. As medidas são: {known}.",
                equation.left.position,
            )
        if name in values:
            raise MathError(
                ErrorCode.INVALID_INPUT_FOR_INTENT,
                f"A medida {name} foi informada duas vezes.",
                equation.left.position,
            )
        nodes[name] = equation.right
        values[name] = _positive(name, _number(equation.right, builder), equation.right)

    if frozenset(values) not in alternatives:
        options = " ou ".join(_example(spec, needed) for needed in alternatives)
        raise MathError(
            ErrorCode.INVALID_INPUT_FOR_INTENT,
            f"Para {CALCULATION_LABELS[calculation]} {spec.of}, informe: {options}.",
        )
    return nodes, values


def _positive(name: str, value: sp.Expr, node: Node) -> sp.Expr:
    if value.is_positive is not True:
        raise MathError(
            ErrorCode.DOMAIN_ERROR,
            f"As medidas precisam ser positivas; {name} não é.",
            node.position,
        )
    return value


def _example(spec: FigureSpec, needed: frozenset[str]) -> str:
    ordered = [s for s in spec.measures if s in needed]
    samples = ["5", "3", "4"]
    return "; ".join(f"{s} = {samples[i % 3]}" for i, s in enumerate(ordered))


# -- the figures ----------------------------------------------------------------------------------


def _figure(
    figure: Figure, calculation: GeometryCalculation, m: dict[str, sp.Expr]
) -> tuple[sp.Expr | Classification, str, str]:
    match figure, calculation:
        case "circle", _:
            r = m["r"] if "r" in m else m["d"] / 2
            given_d = "" if "r" in m else r", r = \frac{d}{2}"
            if calculation == "area":
                return PI * r**2, "A", rf"A = \pi r^2{given_d}"
            return 2 * PI * r, "C", rf"C = 2 \pi r{given_d}"
        case "square", "area":
            return m["l"] ** 2, "A", "A = l^2"
        case "square", _:
            return 4 * m["l"], "P", "P = 4 l"
        case "rectangle", "area":
            return m["b"] * m["h"], "A", r"A = b \cdot h"
        case "rectangle", _:
            return 2 * (m["b"] + m["h"]), "P", "P = 2 (b + h)"
        case "triangle", _:
            return _triangle(calculation, m)
        case "trapezoid", _:
            return (m["B"] + m["b"]) * m["h"] / 2, "A", r"A = \frac{(B + b) \cdot h}{2}"
        case "rhombus", "area":
            return m["D"] * m["d"] / 2, "A", r"A = \frac{D \cdot d}{2}"
        case "rhombus", _:
            side = sp.sqrt((m["D"] / 2) ** 2 + (m["d"] / 2) ** 2)
            return (
                _simplified(4 * side),
                "P",
                r"P = 4 \sqrt{\left(\frac{D}{2}\right)^2 + \left(\frac{d}{2}\right)^2}",
            )
        case "parallelogram", "area":
            return m["b"] * m["h"], "A", r"A = b \cdot h"
        case "parallelogram", _:
            return 2 * (m["a"] + m["b"]), "P", "P = 2 (a + b)"
        case "cube", "volume":
            return m["a"] ** 3, "V", "V = a^3"
        case "cube", _:
            return 6 * m["a"] ** 2, "S", "S = 6 a^2"
        case "box", "volume":
            return m["a"] * m["b"] * m["c"], "V", r"V = a \cdot b \cdot c"
        case "box", _:
            a, b, c = m["a"], m["b"], m["c"]
            return 2 * (a * b + a * c + b * c), "S", "S = 2 (ab + ac + bc)"
        case "sphere", "volume":
            return sp.Rational(4, 3) * PI * m["r"] ** 3, "V", r"V = \frac{4}{3} \pi r^3"
        case "sphere", _:
            return 4 * PI * m["r"] ** 2, "S", r"S = 4 \pi r^2"
        case "cylinder", "volume":
            return PI * m["r"] ** 2 * m["h"], "V", r"V = \pi r^2 h"
        case "cylinder", _:
            r, h = m["r"], m["h"]
            return _simplified(2 * PI * r * (r + h)), "S", r"S = 2 \pi r (r + h)"
        case "cone", "volume":
            return PI * m["r"] ** 2 * m["h"] / 3, "V", r"V = \frac{\pi r^2 h}{3}"
        case "cone", _:
            r, h = m["r"], m["h"]
            slant = sp.sqrt(r**2 + h**2)
            return (
                _simplified(PI * r * (r + slant)),
                "S",
                r"S = \pi r (r + g), \ g = \sqrt{r^2 + h^2}",
            )
        case "right_triangle", _:
            return _pythagoras(m)
    raise AssertionError(f"no formula for {figure} / {calculation}")


def _simplified(value: sp.Expr) -> sp.Expr:
    return value if value.is_Rational else sp.simplify(value)


def _triangle(
    calculation: GeometryCalculation, m: dict[str, sp.Expr]
) -> tuple[sp.Expr | Classification, str, str]:
    if "h" in m:  # base and height
        return m["b"] * m["h"] / 2, "A", r"A = \frac{b \cdot h}{2}"
    a, b, c = m["a"], m["b"], m["c"]
    for side, rest in ((a, b + c), (b, a + c), (c, a + b)):
        if _simplified(rest - side).is_positive is not True:
            raise MathError(
                ErrorCode.DOMAIN_ERROR,
                "Esses lados não formam um triângulo: cada lado precisa ser menor que a soma "
                "dos outros dois.",
            )
    if calculation == "perimeter":
        return a + b + c, "P", "P = a + b + c"
    if calculation == "classify":
        return classify(a, b, c), "", ""
    s = (a + b + c) / 2
    area = _simplified(sp.sqrt(s * (s - a) * (s - b) * (s - c)))
    return area, "A", r"A = \sqrt{s (s - a)(s - b)(s - c)}, \ s = \frac{a + b + c}{2}"


def classify(a: sp.Expr, b: sp.Expr, c: sp.Expr) -> Classification:
    sides = sorted((a, b, c), key=lambda side: float(side))
    equal = sum(1 for x, y in ((a, b), (b, c), (a, c)) if _simplified(x - y) == 0)
    by_sides = "equilátero" if equal == 3 else "isósceles" if equal == 1 else "escaleno"
    longest, others = sides[2], sides[:2]
    gap = _simplified(longest**2 - others[0] ** 2 - others[1] ** 2)
    by_angles = "retângulo" if gap == 0 else "obtusângulo" if gap.is_positive else "acutângulo"
    return Classification(by_sides, by_angles)


def _pythagoras(m: dict[str, sp.Expr]) -> tuple[sp.Expr, str, str]:
    if "c" not in m:
        return _simplified(sp.sqrt(m["a"] ** 2 + m["b"] ** 2)), "c", "c = \\sqrt{a^2 + b^2}"
    leg, missing = (m["a"], "b") if "a" in m else (m["b"], "a")
    if _simplified(m["c"] - leg).is_positive is not True:
        raise MathError(ErrorCode.DOMAIN_ERROR, "A hipotenusa precisa ser maior que o cateto.")
    known = "a" if missing == "b" else "b"
    return (
        _simplified(sp.sqrt(m["c"] ** 2 - leg**2)),
        missing,
        rf"{missing} = \sqrt{{c^2 - {known}^2}}",
    )


# -- analytic geometry ----------------------------------------------------------------------------


def _read_points(
    parsed: ParseResult, builder: ExpressionBuilder
) -> tuple[tuple[Point, ...], tuple[tuple[sp.Expr, ...], ...]]:
    tree = parsed.tree
    items = tree.expressions if isinstance(tree, ExpressionList) else (tree,)
    if not all(isinstance(item, Point) for item in items):
        raise MathError(
            ErrorCode.INVALID_INPUT_FOR_INTENT,
            "Escreva os pontos entre parênteses, separados por ';': (1, 2); (4, 6).",
        )
    nodes = tuple(item for item in items if isinstance(item, Point))
    values = tuple(tuple(_number(c, builder) for c in node.coordinates) for node in nodes)
    if len({len(point) for point in values}) != 1:
        raise MathError(
            ErrorCode.INVALID_INPUT_FOR_INTENT,
            "Todos os pontos precisam ter o mesmo número de coordenadas.",
        )
    return nodes, values


def _analytic(
    calculation: GeometryCalculation, points: tuple[tuple[sp.Expr, ...], ...]
) -> tuple[GeometryResult, str, str]:
    if calculation == "polygon_area":
        return _polygon_area(points)
    if len(points) != 2:
        raise MathError(
            ErrorCode.INVALID_INPUT_FOR_INTENT,
            f"Para {CALCULATION_LABELS[calculation]}, informe dois pontos: (1, 2); (4, 6).",
        )
    p, q = points
    if calculation == "distance":
        squares = sum((x - y) ** 2 for x, y in zip(p, q, strict=True))
        return (
            _simplified(sp.sqrt(squares)),
            "d",
            r"d = \sqrt{(x_2 - x_1)^2 + (y_2 - y_1)^2}",
        )
    if calculation == "midpoint":
        return (
            tuple(_simplified((x + y) / 2) for x, y in zip(p, q, strict=True)),
            "M",
            r"M = \left(\frac{x_1 + x_2}{2}, \frac{y_1 + y_2}{2}\right)",
        )
    return _line(p, q)


def _two_d(points: tuple[tuple[sp.Expr, ...], ...], what: str) -> None:
    if any(len(point) != 2 for point in points):
        raise MathError(
            ErrorCode.INVALID_INPUT_FOR_INTENT, f"{what} usa pontos do plano, como (1, 2)."
        )


def _line(p: tuple[sp.Expr, ...], q: tuple[sp.Expr, ...]) -> tuple[Line, str, str]:
    _two_d((p, q), "A reta")
    (x1, y1), (x2, y2) = p, q
    dx, dy = _simplified(x2 - x1), _simplified(y2 - y1)
    if dx == 0 and dy == 0:
        raise MathError(
            ErrorCode.INVALID_INPUT_FOR_INTENT,
            "Os dois pontos são iguais: há infinitas retas passando por eles.",
        )
    if dx == 0:
        return Line(sp.Integer(1), sp.Integer(0), x1, None, None), "", "x = x_1"
    # dy·x − dx·y = dy·x1 − dx·y1, without a common factor when the numbers are rational
    a, b, c = dy, -dx, _simplified(dy * x1 - dx * y1)
    if all(n.is_Rational for n in (a, b, c)):
        common = sp.gcd(sp.gcd(a, b), c) if c != 0 else sp.gcd(a, b)
        a, b, c = a / common, b / common, c / common
    slope = _simplified(dy / dx)
    intercept = _simplified(y1 - slope * x1)
    return (
        Line(a, b, c, slope, intercept),
        "",
        r"m = \frac{y_2 - y_1}{x_2 - x_1}, \ y - y_1 = m (x - x_1)",
    )


def _polygon_area(points: tuple[tuple[sp.Expr, ...], ...]) -> tuple[sp.Expr, str, str]:
    if len(points) < 3:
        raise MathError(
            ErrorCode.INVALID_INPUT_FOR_INTENT,
            "Um polígono precisa de pelo menos 3 vértices: (0, 0); (4, 0); (4, 3).",
        )
    _two_d(points, "A área do polígono")
    if _self_intersecting(points):
        raise MathError(
            ErrorCode.INVALID_INPUT_FOR_INTENT,
            "Os lados do polígono se cruzam. Informe os vértices na ordem em que aparecem "
            "no contorno (horário ou anti-horário).",
        )
    twice = sum(
        x1 * y2 - x2 * y1
        for (x1, y1), (x2, y2) in zip(points, points[1:] + points[:1], strict=True)
    )
    area = _simplified(sp.Abs(twice) / 2)
    if area == 0:
        raise MathError(
            ErrorCode.INVALID_INPUT_FOR_INTENT, "Os pontos estão alinhados: a área é 0."
        )
    return (
        area,
        "A",
        r"A = \frac{1}{2} \left| \sum_{i} (x_i y_{i+1} - x_{i+1} y_i) \right|",
    )


def _self_intersecting(points: tuple[tuple[sp.Expr, ...], ...]) -> bool:
    """Whether two non-adjacent sides cross (decided with floats: a tie is not a crossing)."""
    vertices = [(float(x), float(y)) for x, y in points]
    edges = list(zip(vertices, vertices[1:] + vertices[:1], strict=True))

    def orientation(
        p: tuple[float, float], q: tuple[float, float], r: tuple[float, float]
    ) -> float:
        return (q[0] - p[0]) * (r[1] - p[1]) - (q[1] - p[1]) * (r[0] - p[0])

    n = len(edges)
    for i in range(n):
        for j in range(i + 1, n):
            if j == i + 1 or (i == 0 and j == n - 1):
                continue  # adjacent sides share a vertex
            (p1, p2), (q1, q2) = edges[i], edges[j]
            d1, d2 = orientation(q1, q2, p1), orientation(q1, q2, p2)
            d3, d4 = orientation(p1, p2, q1), orientation(p1, p2, q2)
            if d1 * d2 < 0 and d3 * d4 < 0:
                return True
    return False

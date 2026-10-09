"""Trigonometry (Phase 10, ADR 0016): conversions, reduction, identities, triangles.

- **convert:** an angle with ° becomes radians (30° = π/6 rad); without °, it is
  in radians (the convention of ADR 0005) and becomes degrees.
- **reduce:** the first determination in [0, 2π), the quadrant, the reference
  angle in the first quadrant and sin, cos and tan with their signs; with a
  function, as in sin(150°), the value by the reduction: sin(30°) = 1/2.
- **identity:** whether both sides are equal wherever both are defined. A proof
  by simplification, or a counterexample (at a notable angle when possible).
- **triangle:** "a = 5; b = 7; C = 60°" (sides in lowercase, the opposite angles
  in uppercase) completes the triangle by the laws of sines and cosines; the
  ambiguous case (two sides and an angle not between them) may have two.

Equations such as sin(x) = 1/2 are solved by the equation engine (ADR 0016).
"""

import itertools
from dataclasses import dataclass, field

import sympy as sp

from app.core.errors import ErrorCode, MathError
from app.core.notices import Notice, NoticeCode
from app.math_engine.inputs import require_equation, require_expression
from app.models.intents import TrigonometryParams
from app.parsing import ParseResult, parse
from app.parsing.ast import Call, Degrees, Equation, Node, System, Variable, variables, walk
from app.parsing.build import ExpressionBuilder, symbol
from app.parsing.vocabulary import TRIGONOMETRIC
from app.verification.deadline import StepTimeout, time_limit

PI = sp.pi
# Time for the simplification that proves an identity, inside the worker's own limit.
IDENTITY_SECONDS = 2.0
MAX_IDENTITY_VARIABLES = 3

# Angles tried first when looking for a counterexample: the answer is easier to check.
NOTABLE = (PI / 6, PI / 4, PI / 3, PI / 5, sp.Integer(1), 2 * PI / 3, sp.Integer(2), PI / 7)


def has_degrees(node: Node) -> bool:
    return any(isinstance(child, Degrees) for child in walk(node))


def _number(node: Node, builder: ExpressionBuilder, what: str) -> sp.Expr:
    if variables(node):
        raise MathError(
            ErrorCode.INVALID_INPUT_FOR_INTENT,
            f"{what} precisa ser um número, sem variáveis, como 30° ou pi/6.",
            node.position,
        )
    value = builder.build(node)
    if value.is_extended_real is False or value.has(sp.I):
        raise MathError(ErrorCode.DOMAIN_ERROR, f"{what} não é um número real.", node.position)
    return value


# -- convert ---------------------------------------------------------------------------------------


@dataclass(frozen=True)
class ConversionOutcome:
    parsed: ParseResult
    tree: Node
    radians: sp.Expr
    to_degrees: bool  # the input was in radians
    degrees: sp.Expr  # radians·180/π
    notices: tuple[Notice, ...] = field(default_factory=tuple)


def _convert(parsed: ParseResult) -> ConversionOutcome:
    tree = require_expression(parsed)
    builder = ExpressionBuilder()
    radians = _number(tree, builder, "O ângulo")
    to_degrees = not has_degrees(tree)
    notices = [*parsed.notices, *builder.notices]
    if to_degrees:
        notices = [n for n in notices if n.code is not NoticeCode.ANGLE_IN_RADIANS]
        notices.append(
            Notice(
                NoticeCode.ANGLE_IN_RADIANS,
                "Sem °, o ângulo foi lido em radianos e convertido para graus. Para converter "
                "graus em radianos, use o símbolo °, como em 30°.",
            )
        )
    return ConversionOutcome(
        parsed=parsed,
        tree=tree,
        radians=sp.simplify(radians),
        to_degrees=to_degrees,
        degrees=sp.simplify(radians * 180 / PI),
        notices=tuple(notices),
    )


# -- reduce to the first quadrant ---------------------------------------------------------------

# The sign of sin, cos and tan in each quadrant.
_SIGNS = {1: (1, 1, 1), 2: (1, -1, -1), 3: (-1, -1, 1), 4: (-1, 1, -1)}
# Reciprocals share the sign of the function they invert.
_BASE = {"sin": "sin", "cos": "cos", "tan": "tan", "csc": "sin", "sec": "cos", "cot": "tan"}
FUNCTIONS = {
    "sin": sp.sin,
    "cos": sp.cos,
    "tan": sp.tan,
    "sec": sp.sec,
    "csc": sp.csc,
    "cot": sp.cot,
}


@dataclass(frozen=True)
class ReductionOutcome:
    parsed: ParseResult
    angle_node: Node
    angle: sp.Expr  # radians
    in_degrees: bool
    function: str | None  # "sin" in sin(150°); None for an angle alone
    first: sp.Expr  # first determination, in [0, 2π)
    turns: int  # angle = first + 2π·turns
    quadrant: int | None  # None on an axis
    reference: sp.Expr  # in [0, π/2]
    values: dict[str, sp.Expr | None]  # sin, cos, tan (and the function asked); None: undefined
    signs: dict[str, int]  # +1 or −1 for each function (0 where the value is 0 or undefined)
    notices: tuple[Notice, ...] = field(default_factory=tuple)


def _reduce(parsed: ParseResult) -> ReductionOutcome:
    tree = require_expression(parsed)
    function: str | None = None
    angle_node = tree
    if isinstance(tree, Call) and tree.name in TRIGONOMETRIC:
        function, angle_node = tree.name, tree.args[0]
    builder = ExpressionBuilder()
    angle = sp.simplify(_number(angle_node, builder, "O ângulo"))
    turns = int(sp.floor(angle / (2 * PI)))
    first = sp.simplify(angle - 2 * PI * turns)

    quadrant: int | None = None
    if first == 0 or first == PI:
        reference = sp.Integer(0)
    elif first == PI / 2 or first == 3 * PI / 2:
        reference = PI / 2
    else:
        quadrant = 1 + int(sp.floor(first / (PI / 2)))
        reference = sp.simplify(
            {1: first, 2: PI - first, 3: first - PI, 4: 2 * PI - first}[quadrant]
        )

    values: dict[str, sp.Expr | None] = {}
    signs: dict[str, int] = {}
    asked = [function] if function is not None and function not in ("sin", "cos", "tan") else []
    for name in ("sin", "cos", "tan", *asked):
        value = FUNCTIONS[name](angle)
        defined = not value.has(sp.zoo, sp.nan)
        values[name] = sp.simplify(value) if defined else None
        if quadrant is not None and defined:
            signs[name] = _SIGNS[quadrant][("sin", "cos", "tan").index(_BASE[name])]
        else:
            signs[name] = 0 if not defined or value == 0 else int(sp.sign(value))
    notices = [
        n for n in (*parsed.notices, *builder.notices) if n.code is not NoticeCode.ANGLE_IN_RADIANS
    ]
    if not has_degrees(angle_node):
        notices.append(
            Notice(
                NoticeCode.ANGLE_IN_RADIANS,
                "Sem °, o ângulo foi lido em radianos. Para graus, use o símbolo °, como em 150°.",
            )
        )
    if function is not None and values[function] is None:
        raise MathError(
            ErrorCode.DOMAIN_ERROR, f"{function} não é definida nesse ângulo.", angle_node.position
        )
    return ReductionOutcome(
        parsed=parsed,
        angle_node=angle_node,
        angle=angle,
        in_degrees=has_degrees(angle_node),
        function=function,
        first=first,
        turns=turns,
        quadrant=quadrant,
        reference=reference,
        values=values,
        signs=signs,
        notices=tuple(notices),
    )


# -- identities ------------------------------------------------------------------------------------


@dataclass(frozen=True)
class IdentityOutcome:
    parsed: ParseResult
    equation: Equation
    names: tuple[str, ...]
    left: sp.Expr
    right: sp.Expr
    holds: bool
    proved: bool  # the difference simplified to 0 (otherwise, numeric evidence or a counterexample)
    counterexample: dict[str, sp.Expr] | None
    left_value: sp.Expr | None
    right_value: sp.Expr | None
    notices: tuple[Notice, ...] = field(default_factory=tuple)


def _identity(parsed: ParseResult) -> IdentityOutcome:
    equation = require_equation(parsed)
    names = tuple(sorted(variables(equation)))
    if not names:
        raise MathError(
            ErrorCode.INVALID_INPUT_FOR_INTENT,
            "Uma identidade tem variáveis, como sin(x)^2 + cos(x)^2 = 1. Para conferir uma "
            "igualdade entre números, use a operação Calcular em cada lado.",
        )
    if len(names) > MAX_IDENTITY_VARIABLES:
        raise MathError(
            ErrorCode.LIMIT_EXCEEDED,
            f"Uma identidade pode ter até {MAX_IDENTITY_VARIABLES} variáveis.",
        )
    builder = ExpressionBuilder()
    left, right = builder.build(equation.left), builder.build(equation.right)
    notices = (*parsed.notices, *builder.notices)
    base = {
        "parsed": parsed,
        "equation": equation,
        "names": names,
        "left": left,
        "right": right,
        "notices": tuple(n for n in notices if n.code is not NoticeCode.ANGLE_IN_RADIANS),
    }
    difference = left - right
    if _simplifies_to_zero(difference):
        return IdentityOutcome(
            **base, holds=True, proved=True, counterexample=None, left_value=None, right_value=None
        )
    found = _counterexample(left, right, names, builder.denominators)
    if found is None:  # no point tells them apart: equal as far as can be seen
        return IdentityOutcome(
            **base, holds=True, proved=False, counterexample=None, left_value=None, right_value=None
        )
    point, left_value, right_value = found
    return IdentityOutcome(
        **base,
        holds=False,
        proved=False,
        counterexample=point,
        left_value=left_value,
        right_value=right_value,
    )


def _simplifies_to_zero(difference: sp.Expr) -> bool:
    if sp.expand(difference) == 0:
        return True
    try:
        with time_limit(IDENTITY_SECONDS, step=True):
            if sp.simplify(difference) == 0:
                return True
            return bool(sp.simplify(sp.expand_trig(difference)) == 0)
    except StepTimeout:
        return False


def _counterexample(
    left: sp.Expr, right: sp.Expr, names: tuple[str, ...], denominators: list[sp.Expr]
) -> tuple[dict[str, sp.Expr], sp.Expr, sp.Expr] | None:
    symbols = [symbol(name) for name in names]
    candidates = itertools.islice(itertools.product(NOTABLE, repeat=len(symbols)), 60)
    for values in candidates:
        point = dict(zip(symbols, values, strict=True))
        if any(_vanishes(d.subs(point)) for d in denominators):
            continue
        left_value, right_value = left.subs(point), right.subs(point)
        if not (_defined(left_value) and _defined(right_value)):
            continue
        difference = sp.N(left_value - right_value, 30)
        if abs(difference) > sp.Float("1e-20"):
            named = {s.name: v for s, v in point.items()}
            return named, sp.simplify(left_value), sp.simplify(right_value)
    return None


def _defined(value: sp.Expr) -> bool:
    return not value.has(sp.zoo, sp.nan, sp.oo, -sp.oo) and value.is_extended_real is not False


def _vanishes(value: sp.Expr) -> bool:
    return bool(abs(sp.N(value, 30)) < sp.Float("1e-25"))


# -- triangles ------------------------------------------------------------------------------------

SIDES = ("a", "b", "c")
ANGLES = ("A", "B", "C")
_OPPOSITE = dict(zip(SIDES, ANGLES, strict=True))


@dataclass(frozen=True)
class Triangle:
    sides: dict[str, sp.Expr]  # a, b, c
    angles: dict[str, sp.Expr]  # A, B, C in radians


@dataclass(frozen=True)
class TriangleOutcome:
    parsed: ParseResult
    given: dict[str, sp.Expr]  # as typed: sides, and angles in radians
    given_nodes: dict[str, Node]
    case: str  # "LLL", "LAL", "LLA", "ALA"
    law: str  # what was used, in Portuguese
    triangles: tuple[Triangle, ...]
    notices: tuple[Notice, ...] = field(default_factory=tuple)


_EXAMPLE = "a = 5; b = 7; C = 60°"


def _triangle(parsed: ParseResult) -> TriangleOutcome:
    tree = parsed.tree
    equations = [tree] if isinstance(tree, Equation) else list(getattr(tree, "equations", []))
    if not isinstance(tree, Equation | System) or not equations:
        raise MathError(
            ErrorCode.INVALID_INPUT_FOR_INTENT,
            f"Informe três medidas com o nome de cada uma, como {_EXAMPLE} (lados em minúsculas, "
            "o ângulo oposto a cada lado em maiúscula).",
        )
    builder = ExpressionBuilder()
    given: dict[str, sp.Expr] = {}
    nodes: dict[str, Node] = {}
    notices: list[Notice] = list(parsed.notices)
    for equation in equations:
        name = equation.left.name if isinstance(equation.left, Variable) else None
        if name not in (*SIDES, *ANGLES):
            raise MathError(
                ErrorCode.INVALID_INPUT_FOR_INTENT,
                f"À esquerda do '=' vai a, b ou c (lados) ou A, B ou C (ângulos): {_EXAMPLE}.",
                equation.left.position,
            )
        if name in given:
            raise MathError(
                ErrorCode.INVALID_INPUT_FOR_INTENT,
                f"{name} foi informado duas vezes.",
                equation.left.position,
            )
        value = _number(equation.right, builder, name)
        if name in ANGLES:
            value = _angle(name, value, equation.right, notices)
        elif value.is_positive is not True:
            raise MathError(
                ErrorCode.DOMAIN_ERROR,
                f"Os lados precisam ser positivos; {name} não é.",
                equation.right.position,
            )
        given[name] = sp.simplify(value)
        nodes[name] = equation.right
    notices += [n for n in builder.notices if n.code is not NoticeCode.ANGLE_IN_RADIANS]

    sides = [n for n in SIDES if n in given]
    angles = [n for n in ANGLES if n in given]
    if len(given) != 3 or not sides:
        raise MathError(
            ErrorCode.INVALID_INPUT_FOR_INTENT,
            "Um triângulo fica determinado por três medidas, com pelo menos um lado: três "
            f"lados, dois lados e um ângulo, ou um lado e dois ângulos. Ex.: {_EXAMPLE}.",
        )
    if len(angles) >= 2 and (sum(given[n] for n in angles) - PI).is_negative is not True:
        raise MathError(
            ErrorCode.DOMAIN_ERROR,
            "Os ângulos de um triângulo somam 180°: os informados já chegam a isso.",
        )
    match len(sides):
        case 3:
            case, law, triangles = "LLL", "lei dos cossenos", [_from_three_sides(given)]
        case 2:
            (angle,) = angles
            if _OPPOSITE[_third(sides)] == angle:  # between the two sides
                case, law, triangles = "LAL", "lei dos cossenos", [_from_sas(given, sides, angle)]
            else:
                case, law = "LLA", "lei dos senos (caso ambíguo)"
                triangles = _from_ssa(given, sides, angle)
        case _:
            case, law, triangles = "ALA", "lei dos senos", [_from_one_side(given)]
    return TriangleOutcome(
        parsed=parsed,
        given=given,
        given_nodes=nodes,
        case=case,
        law=law,
        triangles=tuple(triangles),
        notices=tuple(notices),
    )


def _angle(name: str, value: sp.Expr, node: Node, notices: list[Notice]) -> sp.Expr:
    in_degrees = has_degrees(node)
    if not (value.is_positive and (value - PI).is_negative):
        hint = "" if in_degrees else f" Para graus, escreva {name} = {sp.nsimplify(value)}°."
        raise MathError(
            ErrorCode.DOMAIN_ERROR,
            f"{name} não é um ângulo de triângulo: precisa estar entre 0° e 180° (0 e π rad)."
            + hint,
            node.position,
        )
    if not in_degrees:
        notices.append(
            Notice(
                NoticeCode.ANGLE_IN_RADIANS,
                f"{name} foi lido em radianos (sem °). Para graus, use o símbolo °, como em 60°.",
            )
        )
    return value


def _third(names: list[str]) -> str:
    (missing,) = [n for n in SIDES if n not in names]
    return missing


def _complete(sides: dict[str, sp.Expr], angles: dict[str, sp.Expr]) -> Triangle:
    return Triangle(
        sides={n: sp.radsimp(sp.simplify(sides[n])) for n in SIDES},
        angles={n: sp.simplify(angles[n]) for n in ANGLES},
    )


def _law_of_cosines_angle(opposite: sp.Expr, x: sp.Expr, y: sp.Expr) -> sp.Expr:
    return sp.acos(sp.simplify((x**2 + y**2 - opposite**2) / (2 * x * y)))


def _from_three_sides(given: dict[str, sp.Expr]) -> Triangle:
    a, b, c = (given[n] for n in SIDES)
    for side, rest in ((a, b + c), (b, a + c), (c, a + b)):
        if sp.simplify(rest - side).is_positive is not True:
            raise MathError(
                ErrorCode.DOMAIN_ERROR,
                "Esses lados não formam um triângulo: cada lado precisa ser menor que a soma "
                "dos outros dois.",
            )
    return _complete(
        given,
        {
            "A": _law_of_cosines_angle(a, b, c),
            "B": _law_of_cosines_angle(b, a, c),
            "C": _law_of_cosines_angle(c, a, b),
        },
    )


def _from_sas(given: dict[str, sp.Expr], sides: list[str], angle: str) -> Triangle:
    x, y = (given[n] for n in sides)
    missing = _third(sides)
    third = sp.sqrt(sp.simplify(x**2 + y**2 - 2 * x * y * sp.cos(given[angle])))
    all_sides = {**{n: given[n] for n in sides}, missing: sp.simplify(third)}
    angles = {angle: given[angle]}
    for name in sides:
        others = [all_sides[n] for n in SIDES if n != name]
        angles[_OPPOSITE[name]] = _law_of_cosines_angle(all_sides[name], *others)
    return _complete(all_sides, angles)


def _from_ssa(given: dict[str, sp.Expr], sides: list[str], angle: str) -> list[Triangle]:
    """Two sides and an angle opposite one of them: zero, one or two triangles."""
    (known,) = [n for n in sides if _OPPOSITE[n] == angle]  # the side opposite the angle
    (other,) = [n for n in sides if n != known]
    sine = sp.simplify(given[other] * sp.sin(given[angle]) / given[known])
    if (sine - 1).is_positive:
        raise MathError(
            ErrorCode.DOMAIN_ERROR,
            f"Não existe triângulo com essas medidas: pela lei dos senos, "
            f"sen {_OPPOSITE[other]} = {sp.nsimplify(sine)} > 1.",
        )
    candidates = [sp.asin(sine)]
    if sine != 1:
        candidates.append(PI - sp.asin(sine))
    triangles = []
    for opposite_other in candidates:
        last = sp.simplify(PI - given[angle] - opposite_other)
        if last.is_positive is not True:
            continue
        angles = {angle: given[angle], _OPPOSITE[other]: opposite_other}
        (third_angle,) = [n for n in ANGLES if n not in angles]
        angles[third_angle] = last
        ratio = given[known] / sp.sin(given[angle])
        third_side = _third(sides)
        all_sides = {
            known: given[known],
            other: given[other],
            third_side: sp.simplify(sp.expand_trig(ratio * sp.sin(last))),
        }
        triangles.append(_complete(all_sides, angles))
    if not triangles:
        raise MathError(
            ErrorCode.DOMAIN_ERROR,
            "Não existe triângulo com essas medidas: os ângulos passariam de 180°.",
        )
    return triangles


def _from_one_side(given: dict[str, sp.Expr]) -> Triangle:
    angles = {n: given[n] for n in ANGLES if n in given}
    (missing,) = [n for n in ANGLES if n not in angles]
    angles[missing] = sp.simplify(PI - sum(angles.values()))
    (side,) = [n for n in SIDES if n in given]
    ratio = given[side] / sp.sin(angles[_OPPOSITE[side]])
    sides = {n: sp.simplify(sp.expand_trig(ratio * sp.sin(angles[_OPPOSITE[n]]))) for n in SIDES}
    sides[side] = given[side]
    return _complete(sides, angles)


# -- dispatch -------------------------------------------------------------------------------------

type TrigonometryOutcome = ConversionOutcome | ReductionOutcome | IdentityOutcome | TriangleOutcome


def trigonometry(params: TrigonometryParams) -> TrigonometryOutcome:
    if params.calculation == "triangle" and "=" not in params.expression:
        # "5; 7; 60°" would be a list of numbers, which the parser explains for statistics.
        raise MathError(
            ErrorCode.INVALID_INPUT_FOR_INTENT,
            f"Informe três medidas com o nome de cada uma, como {_EXAMPLE} (lados em "
            "minúsculas, o ângulo oposto a cada lado em maiúscula).",
        )
    parsed = parse(params.expression)
    match params.calculation:
        case "convert":
            return _convert(parsed)
        case "reduce":
            return _reduce(parsed)
        case "identity":
            return _identity(parsed)
        case "triangle":
            return _triangle(parsed)

"""Verification of trigonometry (ADR 0016).

- **convert:** the independent evaluator reads the angle again; the answer must
  be the same angle (in 30 digits), and, for rational multiples of π, the same
  exact fraction of a turn.
- **reduce:** each value is evaluated again from the original angle by the
  independent evaluator; the reduction ±f(reference) is checked exactly; the signs must
  be those of the quadrant; the first determination must differ from the angle
  by whole turns.
- **identity:** a proof by another route (sine and cosine written with
  exponentials, Euler's formula) and the independent evaluator at sample points;
  a counterexample is evaluated again, and the sides must differ.
- **triangle:** the triangle is built on a plane (C at the origin, B on the x
  axis) and measured there: distances and angles by the dot product. The sum of
  the angles and the law of cosines are checked exactly; in the ambiguous case,
  the law of cosines gives a quadratic whose positive roots count the triangles.
"""

import sympy as sp
from mpmath import mp, mpf

from app.formatting.expressions import plain
from app.math_engine.trigonometry import (
    FUNCTIONS,
    SIDES,
    ConversionOutcome,
    IdentityOutcome,
    ReductionOutcome,
    Triangle,
    TriangleOutcome,
    TrigonometryOutcome,
)
from app.models.result import CheckKind, ReasonCode, VerificationCheck, VerificationReport
from app.models.result import VerificationStatus as Status
from app.parsing.ast import Call
from app.verification.algebra import REQUIRED_POINTS, describe, points, try_evaluate
from app.verification.deadline import StepTimeout, time_limit
from app.verification.numeric import BASE_PRECISION, agrees, decimal, to_mpf
from app.verification.reports import failure, inconclusive, passed, report, show
from app.verification.symbolic import reduces_to_zero

COMPARISON_SECONDS = 1.5
_ANGLES = {"a": "A", "b": "B", "c": "C"}


def verify_trigonometry(outcome: TrigonometryOutcome) -> VerificationReport:
    match outcome:
        case ConversionOutcome():
            return _verify_conversion(outcome)
        case ReductionOutcome():
            return _verify_reduction(outcome)
        case IdentityOutcome():
            return _verify_identity(outcome)
        case TriangleOutcome():
            return _verify_triangle(outcome)


def _close(a: mpf, b: mpf) -> bool:
    with mp.workdps(BASE_PRECISION):
        return bool(abs(a - b) <= mpf("1e-30") * max(1, abs(a), abs(b)))


# -- convert ---------------------------------------------------------------------------------------


def _verify_conversion(outcome: ConversionOutcome) -> VerificationReport:
    read = try_evaluate(outcome.tree, {})
    answer = to_mpf(outcome.degrees * sp.pi / 180 if outcome.to_degrees else outcome.radians)
    if read is None or answer is None or not agrees(read, answer):
        return failure(CheckKind.NUMERIC, "O avaliador independente lê outro ângulo na entrada.")
    checks = [
        passed(
            CheckKind.NUMERIC,
            f"O avaliador independente lê o ângulo como {show(read.value)} rad, o mesmo do "
            "resultado em 30 algarismos.",
        )
    ]
    turn = outcome.radians / (2 * sp.pi)
    if not turn.is_Rational:
        return report(Status.VERIFIED_NUMERIC, checks)
    if not (outcome.degrees.is_Rational and outcome.degrees == turn * 360):
        return failure(CheckKind.COMPARISON, "A fração de volta em graus e em radianos difere.")
    checks.append(
        passed(
            CheckKind.COMPARISON,
            f"O ângulo é {plain(turn)} de volta: {plain(turn)} · 360° = {plain(outcome.degrees)}° "
            f"e {plain(turn)} · 2π = {plain(outcome.radians)} rad, exatamente.",
        )
    )
    return report(Status.VERIFIED_SYMBOLIC, checks)


# -- reduce to the first quadrant ---------------------------------------------------------------


def _verify_reduction(outcome: ReductionOutcome) -> VerificationReport:
    checks: list[VerificationCheck] = []
    angle, first, reference = outcome.angle, outcome.first, outcome.reference
    if (
        reduces_to_zero(angle - first - 2 * sp.pi * outcome.turns) is None
        or not (sp.Integer(0) <= first < 2 * sp.pi)
        or not (sp.Integer(0) <= reference <= sp.pi / 2)
    ):
        return failure(
            CheckKind.SYMBOLIC, "A primeira determinação ou o ângulo de referência está errado."
        )
    checks.append(
        passed(
            CheckKind.SYMBOLIC,
            f"{plain(first)} está em [0, 2π) e difere do ângulo por {outcome.turns} volta(s) "
            f"inteira(s); o ângulo de referência {plain(reference)} está em [0, π/2].",
        )
    )

    exact = True
    for name, value in outcome.values.items():
        if value is None:
            # Undefined: the cosine (tan, sec) or the sine (cot, csc) is 0 there.
            base = "cos" if name in ("tan", "sec") else "sin"
            zero = try_evaluate(Call(base, (outcome.angle_node,), 0), {})
            if zero is None or abs(zero.value) > zero.error_bound + mpf("1e-30"):
                return failure(CheckKind.NUMERIC, f"{name} tem valor nesse ângulo.")
            continue
        evaluated = try_evaluate(Call(name, (outcome.angle_node,), 0), {})
        number = to_mpf(value)
        if evaluated is None or number is None or not agrees(evaluated, number):
            return failure(
                CheckKind.NUMERIC, f"O avaliador independente obtém outro valor para {name}."
            )
        sign = outcome.signs[name]
        reduced = sign * FUNCTIONS[name](reference) if sign else value
        reduced_number = to_mpf(reduced)
        if reduced_number is None or not agrees(evaluated, reduced_number):
            return failure(
                CheckKind.NUMERIC,
                f"O avaliador independente não confirma {name} = ± {name} do ângulo de "
                "referência com o sinal do quadrante.",
            )
        if reduces_to_zero(reduced - value) is None:
            exact = False
    checks.append(
        passed(
            CheckKind.NUMERIC,
            "O avaliador independente calcula sin, cos e tan direto do ângulo original e obtém "
            "os mesmos valores, com os sinais do quadrante.",
        )
    )
    if not exact:
        checks.append(
            inconclusive(
                CheckKind.SYMBOLIC,
                "A igualdade exata com ± a função do ângulo de referência não foi decidida.",
            )
        )
        return report(Status.VERIFIED_NUMERIC, checks)
    checks.append(
        passed(
            CheckKind.SYMBOLIC,
            "Cada valor é exatamente ± a mesma função no ângulo de referência, com o sinal "
            "do quadrante.",
        )
    )
    return report(Status.VERIFIED_SYMBOLIC, checks)


# -- identities ------------------------------------------------------------------------------------


def _verify_identity(outcome: IdentityOutcome) -> VerificationReport:
    if not outcome.holds:
        return _verify_counterexample(outcome)

    checked = 0
    for point in points(outcome.parsed.canonical, list(outcome.names)):
        left = try_evaluate(outcome.equation.left, point)
        right = try_evaluate(outcome.equation.right, point)
        if left is None or right is None:
            continue  # outside the domain of one side
        if not agrees(left, right.value, right.error_bound):
            return failure(
                CheckKind.NUMERIC,
                f"Em {describe(point)}, o lado esquerdo vale {show(left.value)} e o direito "
                f"{show(right.value)}.",
            )
        checked += 1
        if checked == REQUIRED_POINTS:
            break
    if checked == 0:
        return report(
            Status.UNVERIFIED,
            [
                inconclusive(
                    CheckKind.NUMERIC, "Nenhum ponto sorteado está no domínio dos dois lados."
                )
            ],
            ReasonCode.FEW_POINTS,
        )
    numeric = passed(
        CheckKind.NUMERIC,
        f"O avaliador independente obtém lados iguais em {checked} pontos sorteados.",
    )
    if _euler(outcome.left - outcome.right):
        checks = [
            passed(
                CheckKind.COMPARISON,
                "Por outro caminho, escrevendo seno e cosseno com exponenciais (fórmula de "
                "Euler), a diferença entre os lados também se anula.",
            ),
            numeric,
        ]
        return report(Status.VERIFIED_SYMBOLIC, checks)
    if outcome.proved:
        return report(
            Status.VERIFIED_NUMERIC,
            [
                numeric,
                inconclusive(
                    CheckKind.COMPARISON,
                    "A simplificação prova a identidade, mas o segundo caminho (exponenciais) "
                    "não chegou a 0 a tempo.",
                ),
            ],
        )
    return report(
        Status.PARTIAL,
        [
            numeric,
            inconclusive(
                CheckKind.SYMBOLIC,
                "Nenhum ponto distingue os lados, mas a igualdade não foi provada.",
            ),
        ],
        ReasonCode.NUMERIC_EVIDENCE_ONLY,
    )


def _euler(difference: sp.Expr) -> bool:
    try:
        with time_limit(COMPARISON_SECONDS, step=True):
            rewritten = difference.rewrite(sp.exp)
            return bool(sp.simplify(sp.expand(rewritten)) == 0)
    except StepTimeout:
        return False


def _verify_counterexample(outcome: IdentityOutcome) -> VerificationReport:
    point = outcome.counterexample or {}
    at = {name: decimal(value) for name, value in point.items()}
    shown = ", ".join(f"{name} = {plain(value)}" for name, value in point.items())
    left = try_evaluate(outcome.equation.left, at)
    right = try_evaluate(outcome.equation.right, at)
    if left is None or right is None:
        return failure(CheckKind.DOMAIN, f"Em {shown}, um dos lados não é definido.")
    if agrees(left, right.value, right.error_bound):
        return failure(CheckKind.NUMERIC, f"Em {shown}, os dois lados são iguais.")
    checks = [
        passed(
            CheckKind.NUMERIC,
            f"Em {shown}, o avaliador independente obtém {show(left.value)} à esquerda e "
            f"{show(right.value)} à direita: os lados diferem.",
        )
    ]
    left_value, right_value = outcome.left_value, outcome.right_value
    if (
        left_value is not None
        and right_value is not None
        and (left_value - right_value).is_zero is False
    ):
        checks.append(
            passed(
                CheckKind.SYMBOLIC,
                f"Exatamente, os lados valem {plain(left_value)} e {plain(right_value)}, "
                "números diferentes.",
            )
        )
        return report(Status.VERIFIED_SYMBOLIC, checks)
    return report(Status.VERIFIED_NUMERIC, checks)


# -- triangles ------------------------------------------------------------------------------------


def _verify_triangle(outcome: TriangleOutcome) -> VerificationReport:
    checks: list[VerificationCheck] = []
    exact = True
    for number, triangle in enumerate(outcome.triangles, start=1):
        label = f"No triângulo {number}, " if len(outcome.triangles) > 1 else ""
        values = {**triangle.sides, **triangle.angles}
        if any(values[name] != value for name, value in outcome.given.items()):
            return failure(CheckKind.COMPARISON, f"{label}as medidas informadas foram trocadas.")
        problem = _measure_on_a_plane(triangle)
        if problem is not None:
            return failure(CheckKind.NUMERIC, label + problem)
        if not _exact_laws(triangle):
            exact = False
    count = len(outcome.triangles)
    checks.append(
        passed(
            CheckKind.NUMERIC,
            "Montando "
            + ("cada triângulo" if count > 1 else "o triângulo")
            + " num plano (C na origem, B no eixo x), as distâncias e os ângulos medidos pelo "
            "produto escalar dão os mesmos valores, em 30 algarismos.",
        )
    )
    if outcome.case == "LLA":
        counted = _ambiguous_count(outcome)
        if counted != count:
            return failure(
                CheckKind.COMPLETENESS,
                f"Pela lei dos cossenos, há {counted} triângulo(s) com essas medidas, e não "
                f"{count}.",
                *checks,
            )
        checks.append(
            passed(
                CheckKind.COMPLETENESS,
                "Pela lei dos cossenos, o lado que falta é raiz positiva de uma equação do 2º "
                f"grau, que tem exatamente {count} raiz(es) positiva(s): "
                + ("são os dois triângulos." if count == 2 else "não há outro triângulo."),
            )
        )
    if exact:
        checks.append(
            passed(
                CheckKind.SYMBOLIC,
                "Exatamente, os ângulos somam π (180°) e a lei dos cossenos vale para os três "
                "lados.",
            )
        )
        return report(Status.VERIFIED_SYMBOLIC, checks)
    checks.append(
        inconclusive(
            CheckKind.SYMBOLIC,
            "A soma dos ângulos e a lei dos cossenos não foram decididas de forma exata.",
        )
    )
    return report(Status.VERIFIED_NUMERIC, checks)


def _measure_on_a_plane(triangle: Triangle) -> str | None:
    """None if the triangle built from a, b and C has the other three measures."""
    values = {name: to_mpf(value) for name, value in {**triangle.sides, **triangle.angles}.items()}
    if any(value is None for value in values.values()):
        return "uma medida não é um número real."
    with mp.workdps(BASE_PRECISION):
        a, b, angle_c = values["a"], values["b"], values["C"]
        point_a = (b * mp.cos(angle_c), b * mp.sin(angle_c))
        point_b = (a, mpf(0))
        point_c = (mpf(0), mpf(0))
        measured = {
            "c": mp.sqrt((point_a[0] - point_b[0]) ** 2 + (point_a[1] - point_b[1]) ** 2),
            "A": _angle_at(point_a, point_b, point_c),
            "B": _angle_at(point_b, point_a, point_c),
        }
    for name, value in measured.items():
        expected = values[name]
        if expected is None or not _close(value, expected):
            return f"medindo no plano, {name} ≈ {mp.nstr(value, 12)}."
    return None


def _angle_at(vertex: tuple[mpf, mpf], p: tuple[mpf, mpf], q: tuple[mpf, mpf]) -> mpf:
    u = (p[0] - vertex[0], p[1] - vertex[1])
    v = (q[0] - vertex[0], q[1] - vertex[1])
    lengths = mp.sqrt(u[0] ** 2 + u[1] ** 2) * mp.sqrt(v[0] ** 2 + v[1] ** 2)
    cosine = (u[0] * v[0] + u[1] * v[1]) / lengths
    return mp.acos(max(mpf(-1), min(mpf(1), cosine)))


def _exact_laws(triangle: Triangle) -> bool:
    s, angles = triangle.sides, triangle.angles
    if not _sum_is_pi(list(angles.values())):
        return False
    for side in SIDES:
        others = [s[n] for n in SIDES if n != side]
        law = s[side] ** 2 - others[0] ** 2 - others[1] ** 2
        law += 2 * others[0] * others[1] * sp.cos(angles[_ANGLES[side]])
        if reduces_to_zero(law) is None:
            return False
    return True


def _sum_is_pi(angles: list[sp.Expr]) -> bool:
    """A + B + C = π. SymPy does not see acos(4/5) + acos(3/5) = π/2 directly, but
    cos(S) = −1 and sin(S) = 0 with each angle in (0, π) leave only S = π."""
    total = sum(angles, sp.Integer(0))
    if reduces_to_zero(total - sp.pi) is not None:
        return True
    inside = all(0 < value < mpf(decimal(sp.pi)) for value in (to_mpf(a) for a in angles) if value)
    return (
        inside
        and reduces_to_zero(sp.expand_trig(sp.cos(total)) + 1) is not None
        and reduces_to_zero(sp.expand_trig(sp.sin(total))) is not None
    )


def _ambiguous_count(outcome: TriangleOutcome) -> int:
    """Positive roots x of k² = o² + x² − 2·o·x·cos K (k is opposite the angle K given)."""
    (angle,) = [n for n in outcome.given if n.isupper()]
    known = angle.lower()
    (other,) = [n for n in outcome.given if n.islower() and n != known]
    with mp.workdps(BASE_PRECISION):
        k, o = to_mpf(outcome.given[known]), to_mpf(outcome.given[other])
        cosine = mp.cos(to_mpf(outcome.given[angle]))
        # x² − 2·o·cos K·x + (o² − k²) = 0
        b, c = -2 * o * cosine, o**2 - k**2
        discriminant = b**2 - 4 * c
        if discriminant < -mpf("1e-40"):
            return 0
        root = mp.sqrt(max(discriminant, mpf(0)))
        roots = {(-b + root) / 2, (-b - root) / 2}
        return sum(1 for x in roots if x > mpf("1e-40"))

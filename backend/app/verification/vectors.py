"""Verification of vector results (ADR 0013).

The vectors are evaluated again from the parser's tree without SymPy: with
fractions when every number is rational, otherwise with mpmath at 60 digits
(the same re-evaluators as matrices). Then each operation is checked by
another route:

- norm: ‖u‖² equals u·u (recomputed) and ‖u‖ ≥ 0;
- unit vector: ‖û‖ = 1 and û·‖u‖ = u (same direction and sense);
- dot product: the sum of products, recomputed;
- cross product: the formula recomputed, w ⟂ u and w ⟂ v, and Lagrange's
  identity ‖u×v‖² = ‖u‖²‖v‖² − (u·v)²;
- angle: cos θ = u·v / (‖u‖‖v‖) with 0 ≤ θ ≤ π, exactly when it can be shown,
  and numerically always.
"""

from collections.abc import Sequence
from fractions import Fraction

import mpmath
import sympy as sp
from mpmath import mp, mpf

from app.formatting.expressions import plain
from app.math_engine.matrices import VectorValue
from app.math_engine.vectors import VectorOutcome
from app.models.result import (
    CheckKind,
    ReasonCode,
    VerificationCheck,
    VerificationReport,
    VerificationStatus,
)
from app.verification.matrices import (
    OutOfExactScope,
    as_grid,
    close,
    exact_linear,
    matrix_close,
    numeric_linear,
)
from app.verification.numeric import BASE_PRECISION, OutsideDomain, TooLarge, to_mpf
from app.verification.reports import failure, inconclusive, passed, report, unverified
from app.verification.symbolic import compare_constants

type Exact = list[Fraction]


def _rational(value: Fraction) -> sp.Rational:
    return sp.Rational(value.numerator, value.denominator)


def _mpf(value: Fraction) -> mpf:
    """At the working precision (call it inside ``mp.workdps``)."""
    return mpf(value.numerator) / value.denominator


def _dot(u: Sequence[Fraction], v: Sequence[Fraction]) -> Fraction:
    return sum((a * b for a, b in zip(u, v, strict=True)), Fraction(0))


def _cross(u: Exact, v: Exact) -> Exact:
    return [
        u[1] * v[2] - u[2] * v[1],
        u[2] * v[0] - u[0] * v[2],
        u[0] * v[1] - u[1] * v[0],
    ]


def verify_vectors(outcome: VectorOutcome) -> VerificationReport:
    try:
        grids = [exact_linear(item) for item in outcome.items]
    except OutOfExactScope, ZeroDivisionError:
        return _verify_numerically(outcome)
    if not all(isinstance(grid, list) for grid in grids):
        raise AssertionError("the engine only accepts vectors here")
    vectors = [[row[0] for row in grid] for grid in grids if isinstance(grid, list)]
    return _verify_exactly(outcome, vectors)


# -- exact mode ---------------------------------------------------------------------------------


def _verify_exactly(outcome: VectorOutcome, vectors: list[Exact]) -> VerificationReport:
    engine = [as_grid(vector.column) for vector in outcome.vectors]
    if engine != [[[x] for x in vector] for vector in vectors]:
        return failure(
            CheckKind.COMPARISON,
            "Recalculando os vetores com frações exatas (sem o SymPy), eles não são os mesmos.",
        )
    checks: list[VerificationCheck] = [
        passed(
            CheckKind.COMPARISON,
            "Os vetores, recalculados com frações exatas e álgebra própria (sem o SymPy), são "
            "os mesmos.",
        )
    ]
    result = outcome.result
    u = vectors[0]
    match outcome.operation:
        case "evaluate":
            return report(VerificationStatus.VERIFIED_SYMBOLIC, checks)
        case "norm":
            if isinstance(result, VectorValue):
                raise AssertionError("a norm is a number")
            squares = _dot(u, u)
            verdict = compare_constants(result**2, _rational(squares))
            if verdict.equal is False or result.is_negative:
                return failure(CheckKind.SYMBOLIC, f"‖u‖² deveria ser u·u = {squares}.", *checks)
            if verdict.equal is None:
                checks.append(
                    inconclusive(CheckKind.SYMBOLIC, "Não foi possível igualar ‖u‖² a u·u.")
                )
                return report(VerificationStatus.VERIFIED_NUMERIC, checks)
            checks.append(
                passed(
                    CheckKind.SYMBOLIC,
                    f"‖u‖² = u·u = {squares}, refeito com frações, e ‖u‖ ≥ 0.",
                )
            )
        case "unit":
            if not isinstance(result, VectorValue):
                raise AssertionError("a unit vector is a vector")
            length = sp.sqrt(_rational(_dot(u, u)))
            unit_length = compare_constants(sum(x**2 for x in result.entries), sp.Integer(1))
            same = [
                compare_constants(x * length, _rational(a))
                for x, a in zip(result.entries, u, strict=True)
            ]
            if unit_length.equal is False or any(v.equal is False for v in same):
                return failure(
                    CheckKind.SYMBOLIC,
                    "O vetor obtido não tem norma 1 ou não tem a direção e o sentido de u.",
                    *checks,
                )
            if unit_length.equal is None or any(v.equal is None for v in same):
                checks.append(
                    inconclusive(CheckKind.SYMBOLIC, "Não foi possível provar ‖û‖ = 1 exatamente.")
                )
                return report(VerificationStatus.VERIFIED_NUMERIC, checks)
            checks.append(
                passed(
                    CheckKind.SYMBOLIC,
                    "‖û‖ = 1 e û·‖u‖ = u, componente por componente: mesma direção e sentido.",
                )
            )
        case "dot":
            own = _dot(u, vectors[1])
            if _rational(own) != result:
                return failure(
                    CheckKind.COMPARISON,
                    f"Somando os produtos com frações, u·v = {own}, e não {result}.",
                    *checks,
                )
            checks.append(
                passed(
                    CheckKind.COMPARISON,
                    "A soma dos produtos dos componentes, refeita com frações, é a mesma.",
                )
            )
        case "cross":
            problem = _check_cross(u, vectors[1], result)
            if problem is not None:
                return failure(CheckKind.SYMBOLIC, problem, *checks)
            checks += [
                passed(
                    CheckKind.COMPARISON,
                    "Os três componentes, refeitos pela fórmula com frações, são os mesmos.",
                ),
                passed(
                    CheckKind.SYMBOLIC,
                    "u×v é perpendicular a u e a v (os dois produtos escalares dão 0), e "
                    "‖u×v‖² = ‖u‖²‖v‖² − (u·v)² (identidade de Lagrange).",
                ),
            ]
        case "angle":
            return _verify_angle(outcome, u, vectors[1], checks)
    return report(VerificationStatus.VERIFIED_SYMBOLIC, checks)


def _check_cross(u: Exact, v: Exact, result: sp.Expr | VectorValue) -> str | None:
    if not isinstance(result, VectorValue):
        raise AssertionError("a cross product is a vector")
    w = _cross(u, v)
    if [_rational(x) for x in w] != result.entries:
        return f"Pela fórmula, u×v = {[str(x) for x in w]}."
    if _dot(w, u) != 0 or _dot(w, v) != 0:
        return "u×v não é perpendicular a u e a v."
    if _dot(w, w) != _dot(u, u) * _dot(v, v) - _dot(u, v) ** 2:
        return "A identidade de Lagrange não vale."
    return None


def _verify_angle(
    outcome: VectorOutcome, u: Exact, v: Exact, checks: list[VerificationCheck]
) -> VerificationReport:
    theta = outcome.result
    if isinstance(theta, VectorValue):
        raise AssertionError("an angle is a number")
    cosine = _rational(_dot(u, v)) / sp.sqrt(_rational(_dot(u, u) * _dot(v, v)))
    with mp.workdps(BASE_PRECISION):
        expected = mpmath.acos(_mpf(_dot(u, v)) / mpmath.sqrt(_mpf(_dot(u, u) * _dot(v, v))))
        value = to_mpf(theta)
        if value is None or not close(expected, value, mpf(1)):
            return failure(
                CheckKind.NUMERIC,
                f"Pelo mpmath, o ângulo é {mpmath.nstr(expected, 15)} rad.",
                *checks,
            )
    checks.append(
        passed(
            CheckKind.NUMERIC,
            "O ângulo, refeito com o mpmath a partir de u·v e das normas (frações exatas), "
            "coincide em 30 algarismos.",
        )
    )
    in_range = theta.is_nonnegative and (sp.pi - theta).is_nonnegative
    verdict = compare_constants(sp.cos(theta), cosine)
    if verdict.equal and in_range:
        checks.append(
            passed(
                CheckKind.SYMBOLIC,
                f"cos θ = u·v / (‖u‖‖v‖) = {plain(cosine)}, exatamente, com θ entre 0 e π.",
            )
        )
        return report(VerificationStatus.VERIFIED_SYMBOLIC, checks)
    checks.append(
        inconclusive(
            CheckKind.SYMBOLIC, "Não foi possível provar exatamente que cos θ = u·v/(‖u‖‖v‖)."
        )
    )
    return report(VerificationStatus.VERIFIED_NUMERIC, checks)


# -- numeric mode ---------------------------------------------------------------------------------


def _verify_numerically(outcome: VectorOutcome) -> VerificationReport:
    with mp.workdps(BASE_PRECISION):
        try:
            columns = [numeric_linear(item) for item in outcome.items]
        except OutsideDomain, TooLarge, ZeroDivisionError:
            return unverified(
                ReasonCode.INCONCLUSIVE,
                CheckKind.NUMERIC,
                "O avaliador independente não conseguiu recalcular os vetores.",
            )
        for column, vector in zip(columns, outcome.vectors, strict=True):
            if not isinstance(column, mpmath.matrix) or not matrix_close(column, vector.column):
                return failure(
                    CheckKind.NUMERIC,
                    "Recalculando os vetores com o avaliador independente (mpmath), eles não "
                    "são os mesmos.",
                )
        checks: list[VerificationCheck] = [
            passed(
                CheckKind.NUMERIC,
                "Os vetores, recalculados pelo avaliador independente (mpmath, 60 dígitos), "
                "coincidem em 30 algarismos significativos.",
            )
        ]
        problem = _numeric_operation(outcome, [list(column) for column in columns])
    if problem is not None:
        return failure(CheckKind.NUMERIC, problem, *checks)
    if outcome.operation != "evaluate":
        checks.append(
            passed(
                CheckKind.NUMERIC,
                "A operação, refeita com o mpmath a partir dos vetores, confere com o resultado.",
            )
        )
    return report(VerificationStatus.VERIFIED_NUMERIC, checks)


def _numeric_operation(outcome: VectorOutcome, vectors: list[list[mpf]]) -> str | None:
    result = outcome.result
    u = vectors[0]
    scale = max([abs(x) for vector in vectors for x in vector] + [mpf(1)])

    def dot(a: list[mpf], b: list[mpf]) -> mpf:
        return mpmath.fsum(x * y for x, y in zip(a, b, strict=True))

    if isinstance(result, VectorValue):
        values = [to_mpf(entry) for entry in result.entries]
        if any(value is None for value in values):
            return "O resultado tem um componente que não é um número real."
        match outcome.operation:
            case "evaluate":
                return None
            case "unit":
                length = mpmath.sqrt(dot(u, u))
                expected = [x / length for x in u]
            case _:  # cross
                v = vectors[1]
                expected = [
                    u[1] * v[2] - u[2] * v[1],
                    u[2] * v[0] - u[0] * v[2],
                    u[0] * v[1] - u[1] * v[0],
                ]
        if not all(
            close(e, a, scale**2) for e, a in zip(expected, values, strict=True) if a is not None
        ):
            return "Refeito com o mpmath, o vetor resultante é diferente."
        return None

    value = to_mpf(result)
    if value is None:
        return "O resultado não é um número real."
    match outcome.operation:
        case "norm":
            expected_number = mpmath.sqrt(dot(u, u))
        case "dot":
            expected_number = dot(u, vectors[1])
        case _:  # angle
            v = vectors[1]
            expected_number = mpmath.acos(dot(u, v) / mpmath.sqrt(dot(u, u) * dot(v, v)))
    if not close(expected_number, value, scale**2):
        return f"Refeito com o mpmath, o valor é {mpmath.nstr(expected_number, 15)}."
    return None

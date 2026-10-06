from collections.abc import Iterator, Mapping

import sympy as sp

from app.formatting.expressions import plain
from app.math_engine.algebra import EquationOutcome, SimplifyOutcome, SolutionKind
from app.models.result import VerificationReport, VerificationStatus
from app.parsing.ast import Node, variables
from app.parsing.build import symbol
from app.verification.numeric import (
    Evaluation,
    OutsideDomain,
    Point,
    TooLarge,
    agrees,
    decimal,
    evaluate,
    sample_points,
    to_mpf,
)
from app.verification.reports import report, show

REQUIRED_POINTS = 6
MAX_ATTEMPTS = 40


def _points(key: str, names: list[str]) -> Iterator[dict[str, str]]:
    for attempt, point in enumerate(sample_points(key, names)):
        if attempt >= MAX_ATTEMPTS:
            return
        yield point


def _describe(point: Mapping[str, str]) -> str:
    return ", ".join(f"{name} = {value}" for name, value in point.items())


def _try_evaluate(node: Node, point: Point) -> Evaluation | None:
    try:
        return evaluate(node, point)
    except OutsideDomain, TooLarge:
        return None


# -- simplify ---------------------------------------------------------------------


def verify_simplify(outcome: SimplifyOutcome) -> VerificationReport:
    names = sorted(variables(outcome.tree))
    needed = REQUIRED_POINTS if names else 1
    agreeing = 0
    for point in _points(outcome.parsed.canonical, names):
        expected = _try_evaluate(outcome.tree, point)
        if expected is None:
            continue  # outside the original's domain: nothing to compare
        actual = to_mpf(outcome.result, {symbol(n): v for n, v in point.items()})
        if actual is None or not agrees(expected, actual):
            where = f"Em {_describe(point)}, a" if names else "A"
            got = "não tem valor real" if actual is None else f"vale {show(actual)}"
            return report(
                VerificationStatus.FAILED,
                "independent_numeric",
                [f"{where} expressão original vale {show(expected.value)} e o resultado {got}."],
            )
        agreeing += 1
        if agreeing == needed:
            break

    if agreeing < needed:
        return report(
            VerificationStatus.UNVERIFIED,
            "independent_numeric",
            [f"Só {agreeing} ponto(s) do domínio foram encontrados para comparar."],
        )

    checks = [
        "Avaliador independente: a expressão original e o resultado coincidem em "
        f"{agreeing} ponto(s)" + (" sorteados." if names else ".")
    ]
    if sp.simplify(outcome.original - outcome.result) == 0:
        checks.append("A diferença entre a expressão original e o resultado simplifica para 0.")
        return report(VerificationStatus.VERIFIED_SYMBOLIC, "symbolic+numeric", checks)
    return report(VerificationStatus.VERIFIED_NUMERIC, "independent_numeric", checks)


# -- equations ----------------------------------------------------------------------


def verify_equation(outcome: EquationOutcome) -> VerificationReport:
    match outcome.kind:
        case SolutionKind.UNIQUE:
            return _verify_unique(outcome)
        case SolutionKind.NONE:
            return _verify_identity(outcome, should_hold=False)
        case SolutionKind.ALL_REALS:
            return _verify_identity(outcome, should_hold=True)


def _sides(outcome: EquationOutcome, point: Point) -> tuple[Evaluation, Evaluation] | None:
    left = _try_evaluate(outcome.equation.left, point)
    right = _try_evaluate(outcome.equation.right, point)
    if left is None or right is None:
        return None
    return left, right


def _equal(sides: tuple[Evaluation, Evaluation]) -> bool:
    left, right = sides
    return agrees(left, right.value, right.error_bound)


def _verify_unique(outcome: EquationOutcome) -> VerificationReport:
    var, solution = outcome.variable, outcome.solution
    if solution is None:
        raise AssertionError("a unique solution must be present")
    name = var.name
    shown = f"{name} = {plain(solution)}"

    symbolic = sp.simplify(outcome.left.subs(var, solution) - outcome.right.subs(var, solution))
    if symbolic != 0:
        return report(
            VerificationStatus.FAILED,
            "substitution",
            [f"Substituindo {shown}, a diferença entre os lados é {plain(symbolic)}, não 0."],
        )

    sides = _sides(outcome, {name: decimal(solution)})
    if sides is None:
        return report(
            VerificationStatus.FAILED,
            "substitution",
            [f"A equação original não tem valor real em {shown}."],
        )
    if not _equal(sides):
        left, right = sides
        return report(
            VerificationStatus.FAILED,
            "substitution",
            [
                f"Em {shown}, o avaliador independente obteve "
                f"{show(left.value)} ≠ {show(right.value)}."
            ],
        )

    # Completeness: a nonzero coefficient on x means degree 1, so at most one root.
    coefficient = sp.Poly(sp.expand(outcome.left - outcome.right), var).coeff_monomial(var)
    if sp.simplify(coefficient) == 0:
        return report(
            VerificationStatus.FAILED,
            "substitution",
            [f"O coeficiente de {name} é 0, então a solução não poderia ser única."],
        )
    return report(
        VerificationStatus.VERIFIED_SYMBOLIC,
        "substitution",
        [
            f"Substituindo {shown} na equação original, os dois lados ficam iguais.",
            f"O avaliador independente confirma: os dois lados valem {show(sides[0].value)}.",
            f"A equação é do 1º grau (coeficiente de {name}: {plain(coefficient)}), "
            "então não existem outras soluções.",
        ],
    )


def _verify_identity(outcome: EquationOutcome, *, should_hold: bool) -> VerificationReport:
    """No solution: the sides always differ. Every real: the sides always agree."""
    name = outcome.variable.name
    difference = sp.expand(outcome.left - outcome.right)
    if difference.free_symbols or (difference == 0) != should_hold:
        return report(
            VerificationStatus.FAILED,
            "symbolic",
            [f"A diferença entre os lados é {plain(difference)}, o que não confirma o resultado."],
        )

    checked = 0
    for point in _points(outcome.parsed.canonical, [name]):
        sides = _sides(outcome, point)
        if sides is None:
            continue
        if _equal(sides) != should_hold:
            left, right = sides
            return report(
                VerificationStatus.FAILED,
                "symbolic+numeric",
                [
                    f"Em {_describe(point)}, o lado esquerdo vale {show(left.value)} "
                    f"e o direito {show(right.value)}."
                ],
            )
        checked += 1
        if checked == REQUIRED_POINTS:
            break

    if should_hold:
        first = "Os dois lados são idênticos: a diferença entre eles é 0."
    else:
        first = f"Os termos com {name} se cancelam e sobra {plain(difference)} = 0, que é falso."
    return report(
        VerificationStatus.VERIFIED_SYMBOLIC,
        "symbolic+numeric",
        [first, f"O avaliador independente confirma em {checked} pontos sorteados."],
    )

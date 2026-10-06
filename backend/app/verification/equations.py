"""Verification of equations and linear systems (ADR 0003).

Every solution is substituted into the **original** equation twice: symbolically
and with the independent evaluator (which also catches roots outside the
domain, such as an extraneous root of a radical equation). Completeness, that
is, "there are no other solutions", is proved only when an independent method
allows it; otherwise the status is ``partial``.
"""

import sympy as sp

from app.formatting.expressions import plain
from app.math_engine.equations import EquationOutcome, SolutionKind
from app.math_engine.polynomials import Shape, count_distinct_real_roots
from app.math_engine.systems import SystemKind, SystemOutcome
from app.models.result import VerificationReport, VerificationStatus
from app.parsing.ast import Equation
from app.parsing.build import symbol
from app.verification.algebra import REQUIRED_POINTS, describe, points, try_evaluate
from app.verification.numeric import Evaluation, Point, agrees, decimal, rational
from app.verification.reports import report, show

# -- shared -------------------------------------------------------------------------------


def _sides(equation: Equation, point: Point) -> tuple[Evaluation, Evaluation] | None:
    left = try_evaluate(equation.left, point)
    right = try_evaluate(equation.right, point)
    if left is None or right is None:
        return None
    return left, right


def _equal(sides: tuple[Evaluation, Evaluation]) -> bool:
    left, right = sides
    return agrees(left, right.value, right.error_bound)


def _vanishes(expr: sp.Expr) -> bool:
    return sp.simplify(expr) == 0


# -- one equation -----------------------------------------------------------------------------


def verify_equation(outcome: EquationOutcome) -> VerificationReport:
    match outcome.kind:
        case SolutionKind.FINITE:
            return _verify_finite(outcome)
        case SolutionKind.NONE:
            return _verify_none(outcome)
        case SolutionKind.ALL_REALS:
            return _verify_all_reals(outcome)


def _verify_finite(outcome: EquationOutcome) -> VerificationReport:
    var, name = outcome.variable, outcome.variable.name
    checks: list[str] = []
    for solution in outcome.solutions:
        shown = f"{name} = {plain(solution)}"
        difference = outcome.left.subs(var, solution) - outcome.right.subs(var, solution)
        if not _vanishes(difference):
            return report(
                VerificationStatus.FAILED,
                "substitution",
                [f"Substituindo {shown}, a diferença entre os lados não se anula."],
            )
        sides = _sides(outcome.equation, {name: decimal(solution)})
        if sides is None:
            return report(
                VerificationStatus.FAILED,
                "substitution",
                [f"A equação original não tem valor real em {shown}."],
            )
        if not _equal(sides):
            return report(
                VerificationStatus.FAILED,
                "substitution",
                [
                    f"Em {shown}, o avaliador independente obteve "
                    f"{show(sides[0].value)} ≠ {show(sides[1].value)}."
                ],
            )
    count = len(outcome.solutions)
    checks.append(
        "Substituindo "
        + ("a solução" if count == 1 else f"cada uma das {count} soluções")
        + " na equação original, os dois lados ficam iguais (de forma exata e pelo "
        "avaliador independente)."
    )
    if outcome.rejected:
        rejected = ", ".join(plain(r) for r in outcome.rejected)
        checks.append(f"Descartado por zerar um denominador: {name} = {rejected}.")

    poly = outcome.candidates
    if poly is not None:
        total = count_distinct_real_roots(poly)  # Sturm: independent of real_roots
        found = len(outcome.solutions) + len(outcome.rejected)
        if total != found:
            return _contradiction(
                f"Pelo teorema de Sturm, o polinômio tem {total} raiz(es) real(is) distinta(s), "
                f"mas {found} foram consideradas."
            )

    completeness = _completeness(outcome)
    if completeness is None:
        checks.append("Não foi provado que não existem outras soluções.")
        return report(VerificationStatus.PARTIAL, "substitution", checks)
    checks.append(completeness)
    return report(VerificationStatus.VERIFIED_SYMBOLIC, "substitution+sturm", checks)


def _completeness(outcome: EquationOutcome) -> str | None:
    """Why no solution is missing, or None if that cannot be proved."""
    poly = outcome.candidates
    if poly is not None:  # the root count was already checked against Sturm
        return (
            f"Pelo teorema de Sturm, o polinômio {plain(poly.as_expr())} tem exatamente "
            f"{count_distinct_real_roots(poly)} raiz(es) real(is) distinta(s), e todas "
            "foram consideradas."
        )
    if outcome.shape is Shape.POLYNOMIAL and len(outcome.solutions) == 1:
        # Any coefficients (even irrational): degree 1 means at most one root.
        poly = sp.Poly(sp.expand(outcome.left - outcome.right), outcome.variable)
        if poly.degree() == 1:
            coefficient = poly.coeff_monomial(outcome.variable)
            return (
                f"A equação é do 1º grau (coeficiente de {outcome.variable.name}: "
                f"{plain(coefficient)}), então não existem outras soluções."
            )
    return None


def _verify_none(outcome: EquationOutcome) -> VerificationReport:
    name = outcome.variable.name
    difference = sp.expand(outcome.left - outcome.right)

    if outcome.shape is Shape.POLYNOMIAL and not difference.free_symbols:
        if difference == 0:
            return _contradiction(f"A diferença entre os lados é 0, então {name} não some.")
        return report(
            VerificationStatus.VERIFIED_SYMBOLIC,
            "symbolic",
            [f"Os termos com {name} se cancelam e sobra {plain(difference)} = 0, que é falso."],
        )

    poly = outcome.candidates
    if poly is not None:
        total = count_distinct_real_roots(poly)
        if total != len(outcome.rejected):
            return _contradiction(
                f"Pelo teorema de Sturm, o polinômio tem {total} raiz(es) real(is), "
                "que não foram todas consideradas."
            )
        checks = [
            f"Pelo teorema de Sturm, o polinômio {plain(poly.as_expr())} tem "
            f"{total} raiz(es) real(is) distinta(s)."
        ]
        if outcome.rejected:
            rejected = ", ".join(plain(r) for r in outcome.rejected)
            checks.append(f"Todas zeram um denominador e foram descartadas: {name} = {rejected}.")
        return report(VerificationStatus.VERIFIED_SYMBOLIC, "sturm", checks)

    if outcome.shape is Shape.RATIONAL:
        numerator, _ = sp.fraction(sp.together(outcome.left - outcome.right))
        if not sp.expand(numerator).free_symbols and sp.expand(numerator) != 0:
            return report(
                VerificationStatus.VERIFIED_SYMBOLIC,
                "symbolic",
                [
                    f"Juntando as frações, o numerador é {plain(sp.expand(numerator))}, "
                    "que nunca é 0."
                ],
            )

    return report(
        VerificationStatus.PARTIAL,
        "none_found",
        ["Nenhuma solução real foi encontrada, mas não foi provado que não existe."],
    )


def _verify_all_reals(outcome: EquationOutcome) -> VerificationReport:
    name = outcome.variable.name
    difference = sp.expand(outcome.left - outcome.right)
    if outcome.shape is Shape.RATIONAL:
        numerator, _ = sp.fraction(sp.together(outcome.left - outcome.right))
        identity = sp.expand(numerator) == 0
    else:
        identity = difference == 0

    checked = 0
    for point in points(outcome.parsed.canonical, [name]):
        sides = _sides(outcome.equation, point)
        if sides is None:
            continue
        if not _equal(sides):
            return report(
                VerificationStatus.FAILED,
                "numeric",
                [
                    f"Em {describe(point)}, o lado esquerdo vale {show(sides[0].value)} "
                    f"e o direito {show(sides[1].value)}."
                ],
            )
        checked += 1
        if checked == REQUIRED_POINTS:
            break

    numeric = f"O avaliador independente confirma a igualdade em {checked} pontos sorteados."
    if not identity:
        return report(VerificationStatus.PARTIAL, "numeric", [numeric])
    first = "Os dois lados são idênticos: a diferença entre eles se reduz a 0."
    checks = [first, numeric]
    if outcome.excluded:
        excluded = ", ".join(plain(e) for e in outcome.excluded)
        checks.append(f"Exceto onde a equação não é definida: {name} = {excluded}.")
    return report(VerificationStatus.VERIFIED_SYMBOLIC, "symbolic+numeric", checks)


def _contradiction(reason: str) -> VerificationReport:
    return report(VerificationStatus.FAILED, "symbolic", [reason])


# -- linear systems --------------------------------------------------------------------------


def verify_system(outcome: SystemOutcome) -> VerificationReport:
    matrix, constants = sp.linear_eq_to_matrix(list(outcome.differences), list(outcome.variables))
    rank = matrix.rank()
    augmented_rank = matrix.row_join(constants).rank()
    unknowns = len(outcome.variables)

    if outcome.kind is SystemKind.NONE:
        if rank < augmented_rank:
            return report(
                VerificationStatus.VERIFIED_SYMBOLIC,
                "rank",
                [
                    f"O sistema é incompatível: o posto da matriz dos coeficientes é {rank}, "
                    f"menor que o posto da matriz ampliada ({augmented_rank})."
                ],
            )
        return _contradiction("Os postos das matrizes não indicam um sistema incompatível.")

    solution = outcome.solution
    if solution is None:
        raise AssertionError("a compatible system must have a solution")
    mapping = dict(zip(outcome.variables, solution, strict=True))

    for difference in outcome.differences:
        if not _vanishes(difference.subs(mapping)):
            return _contradiction("Substituindo a solução, uma equação não é satisfeita.")

    checked = _check_system_numerically(outcome, mapping)
    if checked is None:
        return report(
            VerificationStatus.FAILED,
            "independent_numeric",
            ["O avaliador independente encontrou uma equação não satisfeita."],
        )

    checks = [
        "Substituindo a solução em cada equação original, os dois lados ficam iguais.",
        f"O avaliador independente confirma em {checked} ponto(s).",
    ]
    if outcome.kind is SystemKind.UNIQUE:
        if rank != unknowns:
            return _contradiction(
                f"O posto da matriz é {rank}, menor que o número de incógnitas ({unknowns})."
            )
        checks.append(
            f"O posto da matriz dos coeficientes é {rank}, igual ao número de incógnitas, "
            "então a solução é única."
        )
    else:
        if not (rank == augmented_rank and unknowns - rank == len(outcome.free)):
            return _contradiction("Os postos das matrizes não confirmam a família de soluções.")
        checks.append(
            f"O posto é {rank} com {unknowns} incógnitas: sobram {len(outcome.free)} "
            "variável(is) livre(s), então essa família descreve todas as soluções."
        )
    return report(VerificationStatus.VERIFIED_SYMBOLIC, "substitution+rank", checks)


def _check_system_numerically(
    outcome: SystemOutcome, mapping: dict[sp.Symbol, sp.Expr]
) -> int | None:
    """Evaluates every original equation with the independent evaluator."""
    free_names = [var.name for var in outcome.free]
    samples = points(outcome.parsed.canonical, free_names) if free_names else iter([{}])
    checked = 0
    for free_values in samples:
        substitution = {symbol(n): rational(v) for n, v in free_values.items()}
        point = {var.name: decimal(value.subs(substitution)) for var, value in mapping.items()}
        for equation in outcome.system.equations:
            sides = _sides(equation, point)
            if sides is None or not _equal(sides):
                return None
        checked += 1
        if checked == (REQUIRED_POINTS if free_names else 1):
            break
    return checked

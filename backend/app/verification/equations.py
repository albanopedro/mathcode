"""Verification of equations and linear systems (ADR 0003, ADR 0010).

Every solution is substituted into the **original** equation twice: exactly and
with the independent evaluator (which also catches roots outside the domain,
such as an extraneous root of a radical equation). Completeness, that is,
"there are no other solutions", is proved only when an independent method
allows it; otherwise the status is ``partial``.

An algebraic root that has no radical form (``CRootOf``) is substituted by
divisibility: it is a root of an irreducible polynomial Q, so it makes the
equation true exactly when Q divides the equation's numerator (and not its
denominator). That is exact and fast, where simplifying the substituted
expression can take minutes.
"""

import sympy as sp

from app.formatting.expressions import plain
from app.math_engine.equations import EquationOutcome, SolutionKind
from app.math_engine.polynomials import Shape, count_distinct_real_roots
from app.math_engine.systems import SystemKind, SystemOutcome
from app.models.result import (
    CheckKind,
    ReasonCode,
    VerificationCheck,
    VerificationReport,
    VerificationStatus,
)
from app.parsing.ast import Equation
from app.parsing.build import symbol
from app.verification.algebra import REQUIRED_POINTS, describe, points, try_evaluate
from app.verification.numeric import Evaluation, Point, agrees, decimal, rational
from app.verification.reports import failure, inconclusive, passed, report, show
from app.verification.symbolic import reduces_to_zero

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


def _substitutes_exactly(outcome: EquationOutcome, solution: sp.Expr) -> bool | None:
    """True: the solution satisfies the equation exactly; False: it does not; None: unknown."""
    var = outcome.variable
    difference = outcome.left - outcome.right
    if isinstance(solution, sp.CRootOf):
        factor = sp.Poly(solution.poly.as_expr().xreplace({solution.poly.gen: var}), var)
        numerator, denominator = sp.fraction(sp.together(difference))
        try:
            top = sp.Poly(numerator, var)
            bottom = sp.Poly(denominator, var)
        except sp.PolynomialError:
            top = None
        if top is not None and factor.is_irreducible:
            vanishes = top.rem(factor).is_zero
            defined = sp.gcd(bottom, factor).degree() == 0
            return vanishes and defined
    if reduces_to_zero(difference.subs(var, solution)) is not None:
        return True
    return None


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
    name = outcome.variable.name
    unproved: list[str] = []  # solutions whose exact substitution was not decided
    for solution in outcome.solutions:
        shown = f"{name} = {plain(solution)}"
        exact = _substitutes_exactly(outcome, solution)
        if exact is False:
            return failure(
                CheckKind.SUBSTITUTION,
                f"Substituindo {shown}, a diferença entre os lados não se anula.",
            )
        sides = _sides(outcome.equation, {name: decimal(solution)})
        if sides is None:
            return failure(CheckKind.DOMAIN, f"A equação original não tem valor real em {shown}.")
        if not _equal(sides):
            return failure(
                CheckKind.NUMERIC,
                f"Em {shown}, o avaliador independente obteve "
                f"{show(sides[0].value)} ≠ {show(sides[1].value)}.",
            )
        if exact is None:
            unproved.append(shown)

    count = len(outcome.solutions)
    which = "a solução" if count == 1 else f"cada uma das {count} soluções"
    checks: list[VerificationCheck] = []
    if unproved:
        checks.append(
            passed(
                CheckKind.NUMERIC,
                f"Substituindo {which} na equação original, o avaliador independente obtém "
                "lados iguais em 30 algarismos.",
            )
        )
        checks.append(
            inconclusive(
                CheckKind.SUBSTITUTION,
                "A substituição exata não foi decidida (a diferença não se reduziu a 0) em "
                + ", ".join(unproved)
                + ".",
            )
        )
    else:
        checks.append(
            passed(
                CheckKind.SUBSTITUTION,
                f"Substituindo {which} na equação original, os dois lados ficam iguais (de "
                "forma exata e pelo avaliador independente).",
            )
        )
    if outcome.rejected:
        rejected = ", ".join(plain(r) for r in outcome.rejected)
        checks.append(
            passed(CheckKind.DOMAIN, f"Descartado por zerar um denominador: {name} = {rejected}.")
        )

    poly = outcome.candidates
    if poly is not None:
        total = count_distinct_real_roots(poly)  # Sturm: independent of real_roots
        found = len(outcome.solutions) + len(outcome.rejected)
        if total != found:
            return failure(
                CheckKind.COMPLETENESS,
                f"Pelo teorema de Sturm, o polinômio tem {total} raiz(es) real(is) distinta(s), "
                f"mas {found} foram consideradas.",
                *checks,
            )

    completeness = _completeness(outcome)
    if completeness is None:
        checks.append(
            inconclusive(CheckKind.COMPLETENESS, "Não foi provado que não existem outras soluções.")
        )
        return report(VerificationStatus.PARTIAL, checks, ReasonCode.COMPLETENESS_NOT_PROVED)
    checks.append(passed(CheckKind.COMPLETENESS, completeness))
    if unproved:
        return report(VerificationStatus.VERIFIED_NUMERIC, checks)
    return report(VerificationStatus.VERIFIED_SYMBOLIC, checks)


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
            return failure(
                CheckKind.SYMBOLIC, f"A diferença entre os lados é 0, então {name} não some."
            )
        return report(
            VerificationStatus.VERIFIED_SYMBOLIC,
            [
                passed(
                    CheckKind.SYMBOLIC,
                    f"Os termos com {name} se cancelam e sobra {plain(difference)} = 0, que é "
                    "falso.",
                )
            ],
        )

    poly = outcome.candidates
    if poly is not None:
        total = count_distinct_real_roots(poly)
        if total != len(outcome.rejected):
            return failure(
                CheckKind.COMPLETENESS,
                f"Pelo teorema de Sturm, o polinômio tem {total} raiz(es) real(is), "
                "que não foram todas consideradas.",
            )
        checks = [
            passed(
                CheckKind.COMPLETENESS,
                f"Pelo teorema de Sturm, o polinômio {plain(poly.as_expr())} tem "
                f"{total} raiz(es) real(is) distinta(s).",
            )
        ]
        if outcome.rejected:
            rejected = ", ".join(plain(r) for r in outcome.rejected)
            checks.append(
                passed(
                    CheckKind.DOMAIN,
                    f"Todas zeram um denominador e foram descartadas: {name} = {rejected}.",
                )
            )
        return report(VerificationStatus.VERIFIED_SYMBOLIC, checks)

    if outcome.shape is Shape.RATIONAL:
        numerator, _ = sp.fraction(sp.together(outcome.left - outcome.right))
        if not sp.expand(numerator).free_symbols and sp.expand(numerator) != 0:
            return report(
                VerificationStatus.VERIFIED_SYMBOLIC,
                [
                    passed(
                        CheckKind.SYMBOLIC,
                        f"Juntando as frações, o numerador é {plain(sp.expand(numerator))}, "
                        "que nunca é 0.",
                    )
                ],
            )

    return report(
        VerificationStatus.UNVERIFIED,
        [
            inconclusive(
                CheckKind.COMPLETENESS,
                "Nenhuma solução real foi encontrada, mas não foi provado que não existe.",
            )
        ],
        ReasonCode.COMPLETENESS_NOT_PROVED,
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
            return failure(
                CheckKind.NUMERIC,
                f"Em {describe(point)}, o lado esquerdo vale {show(sides[0].value)} "
                f"e o direito {show(sides[1].value)}.",
            )
        checked += 1
        if checked == REQUIRED_POINTS:
            break

    numeric = passed(
        CheckKind.NUMERIC,
        f"O avaliador independente confirma a igualdade em {checked} pontos sorteados.",
    )
    if not identity:
        return report(
            VerificationStatus.PARTIAL,
            [
                numeric,
                inconclusive(
                    CheckKind.SYMBOLIC,
                    "Não foi provado que os dois lados são iguais para todo valor.",
                ),
            ],
            ReasonCode.NUMERIC_EVIDENCE_ONLY,
        )
    checks = [
        passed(
            CheckKind.SYMBOLIC, "Os dois lados são idênticos: a diferença entre eles se reduz a 0."
        ),
        numeric,
    ]
    if outcome.excluded:
        excluded = ", ".join(plain(e) for e in outcome.excluded)
        checks.append(
            passed(CheckKind.DOMAIN, f"Exceto onde a equação não é definida: {name} = {excluded}.")
        )
    return report(VerificationStatus.VERIFIED_SYMBOLIC, checks)


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
                [
                    passed(
                        CheckKind.COMPLETENESS,
                        "O sistema é incompatível: o posto da matriz dos coeficientes é "
                        f"{rank}, menor que o posto da matriz ampliada ({augmented_rank}).",
                    )
                ],
            )
        return failure(
            CheckKind.COMPLETENESS, "Os postos das matrizes não indicam um sistema incompatível."
        )

    solution = outcome.solution
    if solution is None:
        raise AssertionError("a compatible system must have a solution")
    mapping = dict(zip(outcome.variables, solution, strict=True))

    # Undecided is not a failure (irrational coefficients may resist expanding);
    # the independent evaluator below decides whether an equation fails.
    exact = all(
        reduces_to_zero(difference.subs(mapping)) is not None for difference in outcome.differences
    )
    checked = _check_system_numerically(outcome, mapping)
    if checked is None:
        return failure(
            CheckKind.NUMERIC, "O avaliador independente encontrou uma equação não satisfeita."
        )
    substitution = (
        passed(
            CheckKind.SUBSTITUTION,
            "Substituindo a solução em cada equação original, os dois lados ficam iguais.",
        )
        if exact
        else inconclusive(
            CheckKind.SUBSTITUTION,
            "A substituição exata não foi decidida: a diferença não se reduziu a 0.",
        )
    )
    checks = [
        substitution,
        passed(CheckKind.NUMERIC, f"O avaliador independente confirma em {checked} ponto(s)."),
    ]
    if outcome.kind is SystemKind.UNIQUE:
        if rank != unknowns:
            return failure(
                CheckKind.COMPLETENESS,
                f"O posto da matriz é {rank}, menor que o número de incógnitas ({unknowns}).",
                *checks,
            )
        checks.append(
            passed(
                CheckKind.COMPLETENESS,
                f"O posto da matriz dos coeficientes é {rank}, igual ao número de incógnitas, "
                "então a solução é única.",
            )
        )
    else:
        if not (rank == augmented_rank and unknowns - rank == len(outcome.free)):
            return failure(
                CheckKind.COMPLETENESS,
                "Os postos das matrizes não confirmam a família de soluções.",
                *checks,
            )
        checks.append(
            passed(
                CheckKind.COMPLETENESS,
                f"O posto é {rank} com {unknowns} incógnitas: sobram {len(outcome.free)} "
                "variável(is) livre(s), então essa família descreve todas as soluções.",
            )
        )
    status = VerificationStatus.VERIFIED_SYMBOLIC if exact else VerificationStatus.VERIFIED_NUMERIC
    return report(status, checks)


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

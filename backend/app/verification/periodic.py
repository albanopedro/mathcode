"""Verification of periodic solutions, as in sin(x) = 1/2 (ADR 0016).

Three independent checks, none of which uses ``solveset``:

- **substitution:** the general solution offset + k·period, with k an integer
  symbol, is put into the original equation and the difference reduces to 0 (the
  periodicity is SymPy's knowledge of sin(2kπ + t) = sin(t)); the independent
  evaluator confirms it for k = −1, 0, 1 and 2;
- **completeness by reduction:** when the equation is a polynomial in a single
  trigonometric function of a single argument a·x + b (sec, csc and cot are
  1/cos, 1/sin and 1/tan; sin² = 1 − cos² when one of them appears only in
  even powers), u = sin(a·x + b) turns it into a polynomial P(u) with rational
  coefficients. Its real roots are exact and counted by Sturm's theorem, and
  each root gives its families by asin, acos or atan. Those families must be
  exactly the answer, compared point by point over a common period;
- otherwise, a **numeric scan** of one period looks for sign changes, refined by
  bisection: a root that the answer misses is a failure, but finding none is
  only evidence, so the status is "partial".
"""

from collections.abc import Callable, Iterator
from dataclasses import dataclass

import sympy as sp
from mpmath import mp, mpf

from app.formatting.expressions import plain
from app.math_engine.equations import EquationOutcome
from app.math_engine.periodic import (
    Family,
    Interval,
    contains,
    describe,
    merge,
    normalize,
    same,
)
from app.math_engine.polynomials import (
    count_distinct_real_roots,
    has_rational_coefficients,
    real_roots_with_multiplicity,
)
from app.models.result import CheckKind, ReasonCode, VerificationCheck, VerificationReport
from app.models.result import VerificationStatus as Status
from app.parsing.ast import Equation
from app.verification.algebra import try_evaluate
from app.verification.numeric import agrees, decimal
from app.verification.reports import failure, inconclusive, passed, report, show
from app.verification.symbolic import reduces_to_zero

# Points compared over a common period, and samples of the numeric scan.
MAX_COMPARED = 400
SCAN_SAMPLES = 720

_FUNCTIONS = (sp.sin, sp.cos, sp.tan, sp.sec, sp.csc, sp.cot)


class _Mismatch(Exception):
    def __init__(self, kind: CheckKind, message: str) -> None:
        super().__init__(message)
        self.kind = kind
        self.message = message


# -- the reduction to a polynomial ----------------------------------------------------------------


@dataclass(frozen=True)
class Reduction:
    """u = f(a·x + b) turns the equation into P(u) = 0 (``identity`` when P is zero)."""

    function: str  # "sin", "cos" or "tan"
    argument: sp.Expr
    polynomial: sp.Poly
    rewritten: bool  # sin² = 1 − cos² (or the reverse) was used

    @property
    def identity(self) -> bool:
        return self.polynomial.is_zero

    def describe(self) -> str:
        text = f"Com u = {self.function}({plain(self.argument)})"
        if self.rewritten:
            other = "cos" if self.function == "sin" else "sin"
            text += f" e {other}² = 1 − {self.function}²"
        return text

    def roots(self) -> list[sp.Expr]:
        """The distinct real roots of P: exact (``real_roots``), or −b/a in degree 1."""
        if self.polynomial.degree() == 1 and not has_rational_coefficients(self.polynomial):
            a, b = self.polynomial.all_coeffs()
            return [sp.simplify(-b / a)]
        return [root for root, _ in real_roots_with_multiplicity(self.polynomial)]

    def counted(self) -> int:
        """How many distinct real roots P has, by another method (Sturm; degree 1: one)."""
        if self.polynomial.degree() == 1:
            return 1
        return count_distinct_real_roots(self.polynomial)

    def families(self, var: sp.Symbol) -> tuple[list[sp.Expr], list[Family]]:
        """The real roots u, and the families of x they give (all of them)."""
        roots = self.roots()
        a = self.argument.coeff(var)
        b = self.argument.subs(var, 0)
        families: list[Family] = []
        for u in roots:
            match self.function:
                case "sin" | "cos":
                    if (u - 1).is_positive or (u + 1).is_negative:
                        continue  # no angle has this sine or cosine
                    first = sp.asin(u) if self.function == "sin" else sp.acos(u)
                    second = sp.pi - first if self.function == "sin" else -first
                    angles, period = [first, second], 2 * sp.pi
                case _:
                    angles, period = [sp.atan(u)], sp.pi
            for angle in angles:
                x_period = period / abs(a)
                families.append(Family(normalize((angle - b) / a, x_period), x_period))
        return roots, merge(families)


def reduce_to_polynomial(expr: sp.Expr, var: sp.Symbol) -> Reduction | None:
    atoms = expr.atoms(*_FUNCTIONS)
    arguments = {atom.args[0] for atom in atoms}
    if len(arguments) != 1:
        return None
    (argument,) = arguments
    try:
        linear = sp.Poly(argument, var)
    except sp.PolynomialError:
        return None
    if linear.degree() != 1 or not all(c.is_number for c in linear.all_coeffs()):
        return None

    kinds = {type(atom) for atom in atoms}
    u, s, c = sp.Symbol("u"), sp.Dummy("s"), sp.Dummy("c")
    t = argument
    if kinds <= {sp.tan, sp.cot}:
        function, mapping = "tan", {sp.tan(t): u, sp.cot(t): 1 / u}
    elif kinds <= {sp.sin, sp.csc}:
        function, mapping = "sin", {sp.sin(t): u, sp.csc(t): 1 / u}
    elif kinds <= {sp.cos, sp.sec}:
        function, mapping = "cos", {sp.cos(t): u, sp.sec(t): 1 / u}
    elif kinds <= {sp.sin, sp.cos, sp.csc, sp.sec}:
        function, mapping = "", {sp.sin(t): s, sp.csc(t): 1 / s, sp.cos(t): c, sp.sec(t): 1 / c}
    else:
        return None
    replaced = expr.xreplace(mapping)
    if var in replaced.free_symbols:
        return None  # the variable also appears outside the functions
    numerator = sp.expand(sp.fraction(sp.together(replaced))[0])

    rewritten = False
    if not function:  # sin and cos together: one of them only in even powers
        try:
            mixed = sp.Poly(numerator, s, c)
        except sp.PolynomialError:
            return None
        if all(i % 2 == 0 for i, _ in mixed.monoms()):
            function, numerator = "cos", _rewrite(mixed, lambda i, j: (1 - u**2) ** (i // 2) * u**j)
        elif all(j % 2 == 0 for _, j in mixed.monoms()):
            function, numerator = "sin", _rewrite(mixed, lambda i, j: u**i * (1 - u**2) ** (j // 2))
        else:
            return None
        rewritten = True
    try:
        polynomial = sp.Poly(numerator, u)
    except sp.PolynomialError:
        return None
    exact_roots = polynomial.degree() <= 1 and all(
        coeff.is_number and coeff.is_extended_real for coeff in polynomial.all_coeffs()
    )
    if not (polynomial.is_zero or exact_roots or has_rational_coefficients(polynomial)):
        return None
    return Reduction(function, argument, polynomial, rewritten)


def _rewrite(mixed: sp.Poly, monomial: Callable[[int, int], sp.Expr]) -> sp.Expr:
    terms = zip(mixed.monoms(), mixed.coeffs(), strict=True)
    return sp.expand(sum(coeff * monomial(i, j) for (i, j), coeff in terms))


# -- comparing families ---------------------------------------------------------------------------


def _common_period(families: list[Family]) -> sp.Expr | None:
    """The least common multiple of the periods: rational multiples of π (or of 1)."""
    for base in (sp.pi, sp.Integer(1)):
        ratios = [family.period / base for family in families]
        if all(ratio.is_Rational for ratio in ratios):
            numerator, denominator = 1, 0
            for ratio in ratios:
                numerator = sp.ilcm(numerator, int(ratio.p))
                denominator = sp.igcd(denominator, int(ratio.q))
            return sp.Rational(numerator, denominator) * base
    return None


def _points(families: list[Family], length: sp.Expr) -> list[sp.Expr] | None:
    points: list[sp.Expr] = []
    for family in families:
        repeats = length / family.period
        if not repeats.is_Integer or len(points) + int(repeats) > MAX_COMPARED:
            return None
        points.extend(family.at(k) for k in range(int(repeats)))
    return sorted(points, key=lambda p: float(sp.N(p, 30)))


def _same_points(ours: list[sp.Expr], theirs: list[sp.Expr]) -> bool:
    return len(ours) == len(theirs) and all(same(a, b) for a, b in zip(ours, theirs, strict=True))


# -- the verification -----------------------------------------------------------------------------


def verify_periodic(outcome: EquationOutcome) -> VerificationReport:
    try:
        checks, exact = _substitution(outcome)
        checks.append(_listing(outcome))
        completeness = _completeness(outcome)
    except _Mismatch as mismatch:
        return failure(mismatch.kind, mismatch.message)
    if outcome.rejected_families:
        k = _integer_symbol(outcome)
        discarded = " ou ".join(
            f"{outcome.variable.name} = {describe(f, k)}" for f in outcome.rejected_families
        )
        checks.append(
            passed(
                CheckKind.DOMAIN,
                f"Descartado por estar fora do domínio da equação original: {discarded}.",
            )
        )
    checks.extend(completeness)
    if any(check.outcome == "inconclusive" for check in completeness):
        return report(Status.PARTIAL, checks, ReasonCode.COMPLETENESS_NOT_PROVED)
    return report(Status.VERIFIED_SYMBOLIC if exact else Status.VERIFIED_NUMERIC, checks)


def _integer_symbol(outcome: EquationOutcome) -> sp.Symbol:
    return sp.Symbol("n" if outcome.variable.name == "k" else "k", integer=True)


# Sub-families tried at most, so that every argument moves by multiples of 2π.
MAX_SPLIT = 12


def _substitutes(difference: sp.Expr, var: sp.Symbol, family: Family, k: sp.Symbol) -> bool:
    """The general solution makes the difference 0, for every integer k.

    SymPy gets tan(2kπ + 2π/3) wrong (√3/3, instead of −√3), while sin and cos
    of t + 2kπ are right. So tan, cot, sec and csc are first written with sin
    and cos, and the family is split into N sub-families
    offset + j·period + N·period·k, with N the smallest number for which every
    argument a·x + b moves by a multiple of 2π.
    """
    difference = (
        difference.replace(sp.tan, lambda t: sp.sin(t) / sp.cos(t))
        .replace(sp.cot, lambda t: sp.cos(t) / sp.sin(t))
        .replace(sp.sec, lambda t: 1 / sp.cos(t))
        .replace(sp.csc, lambda t: 1 / sp.sin(t))
    )
    split = 1
    for atom in difference.atoms(*_FUNCTIONS):
        shift = atom.args[0].diff(var) * family.period / (2 * sp.pi)
        if not shift.is_Rational:
            return False
        split = sp.ilcm(split, int(shift.q))
    if split > MAX_SPLIT:
        return False
    return all(
        reduces_to_zero(
            difference.subs(var, family.offset + j * family.period + split * family.period * k)
        )
        is not None
        for j in range(split)
    )


def _sides_agree(equation: Equation, name: str, value: sp.Expr) -> None:
    left = try_evaluate(equation.left, {name: decimal(value)})
    right = try_evaluate(equation.right, {name: decimal(value)})
    shown = f"{name} = {plain(value)}"
    if left is None or right is None:
        raise _Mismatch(CheckKind.DOMAIN, f"A equação original não tem valor real em {shown}.")
    if not agrees(left, right.value, right.error_bound):
        raise _Mismatch(
            CheckKind.NUMERIC,
            f"Em {shown}, o avaliador independente obteve {show(left.value)} ≠ "
            f"{show(right.value)}.",
        )


def _substitution(outcome: EquationOutcome) -> tuple[list[VerificationCheck], bool]:
    name, var = outcome.variable.name, outcome.variable
    k = _integer_symbol(outcome)
    difference = outcome.left - outcome.right
    unproved: list[str] = []
    for family in outcome.families:
        for index in (-1, 0, 1, 2):
            _sides_agree(outcome.equation, name, family.at(index))
        if not _substitutes(difference, var, family, k):
            unproved.append(f"{name} = {describe(family, k)}")
    for value in outcome.isolated:
        _sides_agree(outcome.equation, name, value)
        if reduces_to_zero(difference.subs(var, value)) is None:
            unproved.append(f"{name} = {plain(value)}")

    general = " ou ".join(f"{name} = {describe(f, k)}" for f in outcome.families)
    numeric = passed(
        CheckKind.NUMERIC,
        f"O avaliador independente confirma a igualdade dos lados em {k} = −1, 0, 1 e 2 de "
        "cada família" + (" e em cada solução isolada." if outcome.isolated else "."),
    )
    if unproved:
        return [
            numeric,
            inconclusive(
                CheckKind.SUBSTITUTION,
                "A substituição exata não foi decidida em " + ", ".join(unproved) + ".",
            ),
        ], False
    return [
        passed(
            CheckKind.SUBSTITUTION,
            f"Substituindo a solução geral {general} ({k} inteiro qualquer) na equação "
            "original, a diferença entre os lados se reduz a 0.",
        ),
        numeric,
    ], True


def _listing(outcome: EquationOutcome) -> VerificationCheck:
    """The list inside the interval, recounted family by family with mpmath."""
    interval = outcome.interval
    if interval is None:
        raise _Mismatch(CheckKind.COMPARISON, "Falta o intervalo da lista de soluções.")
    with mp.workdps(60):
        lower, upper = mpf(decimal(interval.lower)), mpf(decimal(interval.upper))
        total = sum(_count(family, lower, upper, interval) for family in outcome.families)
        total += sum(
            1
            for value in outcome.isolated
            if _inside(mpf(decimal(value)), lower, upper, interval)
            and not any(contains(f, value) for f in outcome.families)
        )
        for value in outcome.solutions:
            if not _inside(mpf(decimal(value)), lower, upper, interval):
                raise _Mismatch(
                    CheckKind.COMPARISON, f"{plain(value)} está fora do intervalo da lista."
                )
    if total != outcome.listed_total:
        raise _Mismatch(
            CheckKind.COMPARISON,
            f"Contando de novo, há {total} soluções no intervalo, e não {outcome.listed_total}.",
        )
    return passed(
        CheckKind.COMPARISON,
        f"A lista do intervalo foi refeita contando, em cada família, os inteiros k que caem "
        f"nele: {total} solução(ões).",
    )


def _count(family: Family, lower: mpf, upper: mpf, interval: Interval) -> int:
    """How many integers k put offset + k·period inside the interval."""
    offset, period = mpf(decimal(family.offset)), mpf(decimal(family.period))
    tolerance = mpf("1e-40")
    first = int(mp.ceil((lower - offset) / period - tolerance))
    last = int(mp.floor((upper - offset) / period + tolerance))
    if not interval.closed and abs(offset + last * period - upper) < tolerance:
        last -= 1  # [lower, upper): the upper end is out
    return max(0, last - first + 1)


def _inside(value: mpf, lower: mpf, upper: mpf, interval: Interval) -> bool:
    tolerance = mpf("1e-40")
    if value < lower - tolerance:
        return False
    return value <= upper + tolerance if interval.closed else value < upper - tolerance


def _completeness(outcome: EquationOutcome) -> list[VerificationCheck]:
    var = outcome.variable
    reduction = reduce_to_polynomial(outcome.left - outcome.right, var)
    if reduction is not None and not reduction.identity and not outcome.isolated:
        return [_by_reduction(outcome, reduction)]
    return _by_scan(outcome)


def _by_reduction(outcome: EquationOutcome, reduction: Reduction) -> VerificationCheck:
    var = outcome.variable
    roots, expected = reduction.families(var)
    if reduction.counted() != len(roots):
        raise _Mismatch(CheckKind.COMPLETENESS, "O teorema de Sturm contou outras raízes de P(u).")
    expected = [f for f in expected if not undefined_at(outcome, f.offset)]
    answer = [*outcome.families]
    length = _common_period([*answer, *expected]) if expected else None
    ours = _points(answer, length) if length is not None else None
    theirs = _points(expected, length) if length is not None else None
    if ours is None or theirs is None:
        return inconclusive(
            CheckKind.COMPLETENESS,
            f"{reduction.describe()}, a equação vira um polinômio, mas as famílias não puderam "
            "ser comparadas num período comum.",
        )
    shown_roots = ", ".join(f"u = {plain(r)}" for r in roots) or "nenhuma"
    if not _same_points(ours, theirs):
        raise _Mismatch(
            CheckKind.COMPLETENESS,
            f"{reduction.describe()}, há {len(theirs)} soluções em [0, {plain(length)}), mas "
            f"a resposta tem {len(ours)}.",
        )
    return passed(
        CheckKind.COMPLETENESS,
        f"{reduction.describe()}, a equação vira o polinômio "
        f"{plain(reduction.polynomial.as_expr())} = 0, cujas raízes reais ({shown_roots}) "
        f"são todas as que o teorema de Sturm conta. Elas dão exatamente as {len(theirs)} "
        f"soluções da resposta em [0, {plain(length)}): nenhuma falta.",
    )


def undefined_at(outcome: EquationOutcome, value: sp.Expr) -> bool:
    """Whether the original equation has no real value at ``value``."""
    for side in (outcome.left, outcome.right):
        at = side.subs(outcome.variable, value)
        if at.has(sp.zoo, sp.nan, sp.oo, -sp.oo):
            return True
    return False


def _by_scan(outcome: EquationOutcome) -> list[VerificationCheck]:
    """Sign changes over one period, refined by bisection: a missed root is a failure."""
    length = _common_period(list(outcome.families))
    missing = inconclusive(
        CheckKind.COMPLETENESS,
        "Não foi provado que não existem outras soluções: a equação não é um polinômio em "
        "uma única função trigonométrica.",
    )
    if length is None or outcome.isolated:
        return [missing]
    name = outcome.variable.name
    found = 0
    with mp.workdps(60):
        width = mpf(decimal(length))
        for root in _scan_roots(outcome, width):
            found += 1
            if not any(_near(f, root) for f in outcome.families):
                raise _Mismatch(
                    CheckKind.COMPLETENESS,
                    f"A varredura numérica encontrou uma solução perto de {name} ≈ "
                    f"{mp.nstr(root, 12)} que a resposta não inclui.",
                )
    return [
        passed(
            CheckKind.NUMERIC,
            f"Uma varredura numérica de um período ([0, {plain(length)}), {SCAN_SAMPLES} "
            f"pontos) achou {found} troca(s) de sinal, todas em soluções da resposta.",
        ),
        missing,
    ]


type _Function = Callable[[mpf], mpf | None]


def _near(family: Family, root: mpf) -> bool:
    """Whether a root found by bisection (about 38 digits) is in the family."""
    k = (root - mpf(decimal(family.offset))) / mpf(decimal(family.period))
    return bool(abs(k - mp.nint(k)) < mpf("1e-20"))


def _scan_roots(outcome: EquationOutcome, width: mpf) -> Iterator[mpf]:
    name = outcome.variable.name

    def f(x: mpf) -> mpf | None:
        left = try_evaluate(outcome.equation.left, {name: mp.nstr(x, 50)})
        right = try_evaluate(outcome.equation.right, {name: mp.nstr(x, 50)})
        return None if left is None or right is None else left.value - right.value

    step = width / SCAN_SAMPLES
    previous_x, previous = mpf(0), f(mpf(0))
    for i in range(1, SCAN_SAMPLES + 1):
        x = step * i
        current = f(x)
        if previous is not None and current is not None and previous * current < 0:
            root = _bisect(f, previous_x, x, previous)
            if root is not None:
                yield root
        previous_x, previous = x, current


def _bisect(f: _Function, a: mpf, b: mpf, fa: mpf) -> mpf | None:
    """A root in (a, b), or None if the sign change is a pole (the values blow up)."""
    for _ in range(120):
        middle = (a + b) / 2
        fm = f(middle)
        if fm is None:
            return None
        if fm == 0:
            return middle
        if fa * fm < 0:
            b = middle
        else:
            a, fa = middle, fm
    fm = f((a + b) / 2)
    return (a + b) / 2 if fm is not None and abs(fm) < mpf("1e-20") else None

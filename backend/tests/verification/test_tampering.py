"""Every intent's verifier rejects a wrong result (ADR 0003, ADR 0010).

One tampered outcome per registered intent: a new intent without an entry here
makes ``test_every_intent_is_covered`` fail, so no verifier goes untested.
"""

from collections.abc import Callable
from dataclasses import replace
from typing import Any

import pytest
import sympy as sp

from app.interpreter.detect import interpret
from app.interpreter.registry import REGISTRY
from app.models.intents import IntentName
from app.models.result import VerificationStatus
from app.parsing.build import symbol

x, y = symbol("x"), symbol("y")

type Tamper = Callable[[Any], Any]

# intent -> (input, options, how to make its result wrong)
CASES: dict[IntentName, tuple[str, dict[str, str | int] | None, Tamper]] = {
    IntentName.ARITHMETIC: ("2^10 + sqrt(2)", None, lambda o: replace(o, value=o.value + 1)),
    IntentName.SIMPLIFY: ("(x^2 - 1)/(x - 1)", None, lambda o: replace(o, result=o.result + 1)),
    IntentName.FACTOR: ("x^2 - 4", None, lambda o: replace(o, result=(x - 2) * (x + 3))),
    IntentName.EXPAND: ("(x + 1)^3", None, lambda o: replace(o, result=o.result + x)),
    IntentName.SOLVE_EQUATION: (
        "x^2 - 5x + 6 = 0",
        None,
        lambda o: replace(o, solutions=(sp.Integer(2), sp.Integer(4))),
    ),
    IntentName.SOLVE_SYSTEM: (
        "x + y = 3; x - y = 1",
        None,
        lambda o: replace(o, solution=(sp.Integer(2), sp.Integer(2))),
    ),
    IntentName.POLYNOMIAL_DIVISION: (
        "(x^3 - 1)/(x - 1)",
        None,
        lambda o: replace(o, quotient=o.quotient + 1),
    ),
    IntentName.DERIVATIVE: ("x^2 sin(x)", None, lambda o: replace(o, result=o.result + x)),
    IntentName.INTEGRAL: (
        "x^2",
        None,
        lambda o: replace(
            o, antiderivative=o.antiderivative + x, raw_antiderivative=o.raw_antiderivative + x
        ),
    ),
    IntentName.LIMIT: ("sin(x)/x", {"point": "0"}, lambda o: replace(o, value=sp.Integer(2))),
    IntentName.GRAPH: (
        "x^2 - 4x + 3",
        None,
        lambda o: replace(
            o, points=(replace(o.points[0], x_value=1.5, x_decimal="1.5"), *o.points[1:])
        ),
    ),
}


def run(intent: IntentName) -> tuple[Any, Any]:
    text, options, _ = CASES[intent]
    spec = REGISTRY[intent]
    request = interpret(text, intent.value, options)
    return spec, spec.execute(request.params)


def test_every_intent_is_covered() -> None:
    assert set(CASES) == set(REGISTRY)


@pytest.mark.parametrize("intent", list(CASES))
def test_the_right_result_passes(intent: IntentName) -> None:
    spec, outcome = run(intent)
    assert spec.verify(outcome).status is not VerificationStatus.FAILED


@pytest.mark.parametrize("intent", list(CASES))
def test_a_tampered_result_fails(intent: IntentName) -> None:
    spec, outcome = run(intent)
    tamper = CASES[intent][2]

    report = spec.verify(tamper(outcome))

    assert report.status is VerificationStatus.FAILED
    # The report says which check caught it (the model requires at least one).
    assert any(check.outcome == "failed" for check in report.checks)

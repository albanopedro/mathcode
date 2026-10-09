"""The assistant: a plan's steps, each verified, summed up in one result (ADR 0021)."""

from app.assistant import compose, summarize
from app.calculator import calculate
from app.interpreter.planner import ExecutionPlan, PlanStep
from app.models.intents import IntentName as I
from app.models.result import (
    CheckKind,
    Interpretation,
    MathResult,
    PlanStepResult,
    ReasonCode,
    VerificationStatus,
)

RULES = Interpretation(method="rules", intent=I.ASSISTANT, expression="f")


def step(title: str, text: str, intent: I | None = None) -> PlanStepResult:
    result = calculate(text, intent)
    return PlanStepResult(
        title=title, intent=result.intent or I.ARITHMETIC, input=text, result=result
    )


def test_a_plan_through_the_pipeline() -> None:
    result = calculate("raízes, vértice e gráfico de x^2 - 4x + 3")

    assert result.success and result.intent is I.ASSISTANT
    assert [s.title for s in result.plan] == ["Raízes", "Vértice", "Gráfico"]
    assert [s.result.result.plain for s in result.plan if s.result.result] == [
        "x = 1 ou x = 3",
        "V = (2, -1), mínimo",
        "y = x^2 - 4*x + 3",
    ]
    assert result.interpretation == Interpretation(
        method="rules", intent=I.ASSISTANT, expression="x^2 - 4x + 3"
    )
    assert result.result is not None
    assert result.result.latex == r"\text{3 de 3 passos calculados}"
    assert result.details == {"function": "x^2 - 4x + 3", "steps": 3, "calculated": 3}


def test_a_failed_step_does_not_stop_the_others() -> None:
    result = calculate("estude a função 1/x")

    assert result.success
    at_zero = result.plan[1]
    assert at_zero.title == "Valor em x = 0"
    assert not at_zero.result.success
    assert at_zero.result.error is not None and at_zero.result.error.code == "DIVISION_BY_ZERO"
    assert result.details["calculated"] == 4


def test_every_step_failed() -> None:
    plan = ExecutionPlan(
        (PlanStep("Um", I.ARITHMETIC, "1/0"), PlanStep("Dois", I.ARITHMETIC, "2/0")), "f", "list"
    )
    results = [calculate(s.input, s.intent) for s in plan.steps]
    result = compose("pedido", plan, results, RULES)

    assert not result.success and result.result is None
    assert result.error is not None and result.error.code == "DIVISION_BY_ZERO"
    assert len(result.plan) == 2


def test_the_weakest_verification_wins() -> None:
    report = summarize([step("Exata", "2 + 2"), step("Parcial", "e^x = 2", I.SOLVE_EQUATION)])

    assert report.status is VerificationStatus.PARTIAL
    assert report.reason is ReasonCode.COMPLETENESS_NOT_PROVED
    assert "Parcial" in report.message
    # Every check is kept, named by its step.
    assert report.checks[0].message.startswith("Exata: ")
    assert any(c.message.startswith("Parcial: ") for c in report.checks)


def test_a_graph_alone_counts_only_when_nothing_else_is_verified() -> None:
    graph = step("Gráfico", "1/x", I.GRAPH)
    assert graph.result.verification is not None
    assert graph.result.verification.status is VerificationStatus.NOT_APPLICABLE

    both = summarize([step("Conta", "2 + 2"), graph])
    alone = summarize([graph])
    assert both.status is VerificationStatus.VERIFIED_SYMBOLIC
    assert "com um resultado a conferir" in both.message
    assert alone.status is VerificationStatus.NOT_APPLICABLE


def test_all_symbolic() -> None:
    report = summarize([step("A", "2 + 2"), step("B", "x^2", I.DERIVATIVE)])
    assert report.status is VerificationStatus.VERIFIED_SYMBOLIC
    assert report.message == "Todos os passos foram verificados simbolicamente."
    assert CheckKind.COMPARISON in report.methods


def test_asking_for_the_assistant_without_a_plan() -> None:
    result = calculate("2 + 2", "assistant")
    assert not result.success and result.intent is I.ASSISTANT
    assert result.error is not None and "raízes, vértice e gráfico" in result.error.message


def test_the_assistant_is_never_a_step() -> None:
    result = calculate("x^2", "assistant", {"variable": "x"})
    assert not result.success
    assert result.error is not None and result.error.code == "UNSUPPORTED_INTENT"


def test_plan_steps_round_trip_through_json() -> None:
    result = calculate("derivada e integral de x^2")
    again = MathResult.model_validate_json(result.model_dump_json())
    assert again == result

"""POST /api/calculate with allow_ai, through real workers and a mock AI provider."""

from collections.abc import Callable, Iterator

import pytest
from fastapi.testclient import TestClient

from app.ai.base import AIError, IntentCandidate
from app.ai.mock import MockProvider
from app.ai.service import AIService
from app.models.result import MathResult

PHRASE = "quanto vale o dobro de sete"

type UseAI = Callable[[dict[str, IntentCandidate | AIError] | None], MockProvider | None]


@pytest.fixture
def use_ai(api: TestClient) -> Iterator[UseAI]:
    """Swap the server's AI service for one with a mock provider (None: no provider)."""
    state = api.app.state
    original = state.ai

    def install(answers: dict[str, IntentCandidate | AIError] | None) -> MockProvider | None:
        provider = None if answers is None else MockProvider(answers)
        state.ai = AIService(provider, timeout=10)
        return provider

    yield install
    state.ai = original


def post(api: TestClient, body: dict) -> MathResult:
    response = api.post("/api/calculate", json=body)
    assert response.status_code == 200
    return MathResult.model_validate(response.json())


def test_the_ai_interprets_and_the_engine_calculates(api: TestClient, use_ai: UseAI) -> None:
    mock = use_ai({PHRASE: IntentCandidate(intent="arithmetic", expression="2 * 7")})

    result = post(api, {"input": PHRASE, "allow_ai": True})

    assert mock is not None and mock.calls == [PHRASE]
    assert result.success
    assert result.input == PHRASE  # what was typed
    assert result.normalized_input == "2*7"  # what was calculated
    assert result.result is not None and result.result.plain == "14"
    assert result.verification is not None
    assert result.interpretation is not None
    assert result.interpretation.model_dump() == {
        "method": "ai",
        "intent": "arithmetic",
        "expression": "2 * 7",
        "options": {},
        "provider": "mock",
        "model": "mock",
    }


def test_options_from_the_ai_are_validated(api: TestClient, use_ai: UseAI) -> None:
    phrase = "a segunda derivada de x ao cubo"
    use_ai({phrase: IntentCandidate(intent="derivative", expression="x^3", options={"order": 2})})

    result = post(api, {"input": phrase, "allow_ai": True})

    assert result.success and result.intent == "derivative"
    assert result.result is not None and result.result.plain == "6*x"


def test_invalid_options_from_the_ai_are_an_error(api: TestClient, use_ai: UseAI) -> None:
    use_ai({PHRASE: IntentCandidate(intent="derivative", expression="x^3", options={"order": 99})})

    result = post(api, {"input": PHRASE, "allow_ai": True})

    assert not result.success
    assert result.error is not None and result.error.code == "INVALID_INPUT_FOR_INTENT"
    assert result.interpretation is not None and result.interpretation.method == "ai"


def test_an_answer_in_the_expression_does_not_get_through(api: TestClient, use_ai: UseAI) -> None:
    # The model calculated instead of translating: the parser refuses the text.
    use_ai({PHRASE: IntentCandidate(intent="derivative", expression="d/dx (x^2) = 2x")})

    result = post(api, {"input": PHRASE, "allow_ai": True})

    assert not result.success
    assert result.error is not None
    assert result.error.position is None  # it would point into the AI's text
    assert result.interpretation is not None
    assert result.interpretation.expression == "d/dx (x^2) = 2x"


def test_a_wrong_number_from_the_ai_is_not_used(api: TestClient, use_ai: UseAI) -> None:
    use_ai({PHRASE: IntentCandidate(intent="solve_equation", expression="x = 2 * 7 + 1")})

    result = post(api, {"input": PHRASE, "allow_ai": True})

    # The engine solves what it was given; the interpretation shows what that was.
    assert result.result is not None and result.result.plain == "x = 15"
    assert result.interpretation is not None
    assert result.interpretation.expression == "x = 2 * 7 + 1"


def test_a_question_from_the_ai(api: TestClient, use_ai: UseAI) -> None:
    use_ai({PHRASE: IntentCandidate(intent=None, clarification="Qual é a conta?")})

    result = post(api, {"input": PHRASE, "allow_ai": True})

    assert not result.success
    assert result.error is not None
    assert result.error.code == "AMBIGUOUS_INPUT"
    assert result.error.message == "Qual é a conta?"
    assert result.interpretation is not None and result.interpretation.intent is None


def test_an_intent_with_a_question_still_asks(api: TestClient, use_ai: UseAI) -> None:
    use_ai(
        {
            PHRASE: IntentCandidate(
                intent="arithmetic", expression="2 * 7", clarification="Dobro de 7?"
            )
        }
    )

    result = post(api, {"input": PHRASE, "allow_ai": True})

    assert result.error is not None and result.error.code == "AMBIGUOUS_INPUT"


def test_ai_failure(api: TestClient, use_ai: UseAI) -> None:
    use_ai({PHRASE: AIError("O limite de uso gratuito do OpenCode foi atingido.")})

    result = post(api, {"input": PHRASE, "allow_ai": True})

    assert result.error is not None
    assert result.error.code == "AI_FAILED"
    assert "limite de uso gratuito" in result.error.message
    assert result.interpretation is None


def test_no_provider_on_the_server(api: TestClient, use_ai: UseAI) -> None:
    use_ai(None)

    result = post(api, {"input": PHRASE, "allow_ai": True})

    assert result.error is not None
    assert result.error.code == "AI_UNAVAILABLE"
    assert result.input == PHRASE


@pytest.mark.parametrize(
    "body",
    [
        {"input": PHRASE},  # not allowed: the phrase never leaves the server
        {"input": PHRASE, "allow_ai": False},
        {"input": PHRASE, "allow_ai": True, "intent": "arithmetic"},  # an explicit operation
        {"input": PHRASE, "allow_ai": True, "intent": "derivative", "options": {"order": 2}},
        {"input": PHRASE, "allow_ai": True, "options": {"variable": "x"}},
        {"input": "derivada de x^2", "allow_ai": True},  # the rules understand it
        {"input": "2x + 5 = 17", "allow_ai": True},  # plain math
        {"input": "2 +", "allow_ai": True},  # a typo
    ],
)
def test_the_ai_is_not_asked(api: TestClient, use_ai: UseAI, body: dict) -> None:
    mock = use_ai({})

    api.post("/api/calculate", json=body)

    assert mock is not None and mock.calls == []


def test_rules_keep_their_interpretation(api: TestClient, use_ai: UseAI) -> None:
    use_ai({})

    result = post(api, {"input": "derivada de x^2", "allow_ai": True})

    assert result.success
    assert result.interpretation is not None and result.interpretation.method == "rules"


def test_allow_ai_must_be_a_boolean(api: TestClient) -> None:
    response = api.post("/api/calculate", json={"input": PHRASE, "allow_ai": "sim"})

    assert response.status_code == 422

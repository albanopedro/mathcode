from app.ai.base import AIError, IntentCandidate


class MockProvider:
    """Fixed answers, for tests: no network, no subprocess."""

    name = "mock"
    model = "mock"

    def __init__(self, answers: dict[str, IntentCandidate | AIError]) -> None:
        self.answers = answers
        self.calls: list[str] = []

    def interpret(self, text: str) -> IntentCandidate:
        self.calls.append(text)
        answer = self.answers.get(text)
        if answer is None:
            raise AIError("O mock não conhece este pedido.")
        if isinstance(answer, AIError):
            raise answer
        return answer

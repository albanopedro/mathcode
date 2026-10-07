"""When the AI is asked (needs_ai), how it is configured, and the service around it."""

import asyncio
import subprocess
import sys
import threading
import time

import pytest
from pydantic import ValidationError

from app.ai import build_provider, needs_ai
from app.ai import service as service_module
from app.ai.base import AIError, IntentCandidate
from app.ai.mock import MockProvider
from app.ai.opencode import OpencodeProvider
from app.ai.service import CONCURRENCY, AIService
from app.core.config import Settings
from app.core.limits import MAX_INPUT_LENGTH


@pytest.mark.parametrize(
    "text",
    [
        "quanto vale o dobro de sete",
        "a raiz quadrada de dezesseis",
        "derivada de x ao quadrado mais tres x",  # the rule found the operation, not the math
        "resolva x mais 3 igual a 10",
        "quando o seno de x vale meio?",
    ],
)
def test_phrases_the_rules_do_not_understand(text: str) -> None:
    assert needs_ai(text)


@pytest.mark.parametrize(
    "text",
    [
        "2x + 5 = 17",  # math
        "quanto é 2 + 2?",  # the rules understand it
        "derivada de x^2",
        "2 +",  # a typo: the parser's message is better
        "sin(x",
        "sen(30°) + raiz(4)",
        "média de 2, 4 e 6",  # the rules already answer "not yet"
        "",
    ],
)
def test_requests_that_do_not_need_the_ai(text: str) -> None:
    assert not needs_ai(text)


def test_a_too_long_phrase_is_never_sent() -> None:
    assert not needs_ai("qual o dobro de sete " * (MAX_INPUT_LENGTH // 10))


def test_settings_default_to_no_ai() -> None:
    settings = Settings(_env_file=None)

    assert settings.ai_provider == "none"
    assert build_provider(settings) is None


def test_settings_build_the_opencode_provider(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MATHCODE_AI_PROVIDER", "opencode")
    monkeypatch.setenv("MATHCODE_AI_MODEL", "opencode/big-pickle")
    monkeypatch.setenv("MATHCODE_AI_TIMEOUT", "30")

    provider = build_provider(Settings(_env_file=None))

    assert isinstance(provider, OpencodeProvider)
    assert provider.model == "opencode/big-pickle"
    assert provider.timeout == 30


@pytest.mark.parametrize(
    ("name", "value"),
    [
        ("MATHCODE_AI_MODEL", "opencode/gpt-5"),  # paid
        ("MATHCODE_AI_MODEL", "anthropic/claude-sonnet-4"),
        ("MATHCODE_AI_PROVIDER", "openai"),
        ("MATHCODE_AI_TIMEOUT", "1"),
        ("MATHCODE_AI_TIMEOUT", "3600"),
    ],
)
def test_settings_refuse(monkeypatch: pytest.MonkeyPatch, name: str, value: str) -> None:
    monkeypatch.setenv(name, value)

    with pytest.raises(ValidationError):
        Settings(_env_file=None)


class SlowProvider:
    name = "slow"
    model = "slow"

    def __init__(self, seconds: float) -> None:
        self.seconds = seconds
        self.running = 0
        self.most = 0
        self._lock = threading.Lock()

    def interpret(self, text: str) -> IntentCandidate:
        with self._lock:
            self.running += 1
            self.most = max(self.most, self.running)
        time.sleep(self.seconds)
        with self._lock:
            self.running -= 1
        return IntentCandidate(intent="arithmetic", expression="1 + 1")


def test_at_most_two_calls_at_once() -> None:
    provider = SlowProvider(0.2)

    async def many() -> None:
        service = AIService(provider, timeout=10)
        await asyncio.gather(*(service.interpret(str(n)) for n in range(5)))

    asyncio.run(many())

    assert provider.most == CONCURRENCY == 2


def test_the_service_times_out_a_stuck_provider(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(service_module, "GRACE", 0.0)
    service = AIService(SlowProvider(2), timeout=0.2)

    with pytest.raises(AIError, match=r"mais de 0\.2 s"):
        asyncio.run(service.interpret("pedido"))


def test_the_mock_records_its_calls() -> None:
    answer = IntentCandidate(intent="arithmetic", expression="2 * 7")
    mock = MockProvider({"o dobro de sete": answer, "falha": AIError("fora do ar")})

    assert mock.interpret("o dobro de sete") is answer
    with pytest.raises(AIError, match="fora do ar"):
        mock.interpret("falha")
    with pytest.raises(AIError, match="não conhece"):
        mock.interpret("outro")
    assert mock.calls == ["o dobro de sete", "falha", "outro"]


def test_the_server_process_never_imports_sympy() -> None:
    # needs_ai runs in the API process: the rules and the parser, never the engine.
    code = (
        "import sys, app.main\n"
        "from app.ai import needs_ai\n"
        "needs_ai('quanto vale o dobro de sete'); needs_ai('derivada de x^2')\n"
        "print(sorted(m for m in ('sympy', 'mpmath') if m in sys.modules))\n"
    )
    done = subprocess.run(  # noqa: S603 - fixed argv
        [sys.executable, "-c", code], capture_output=True, text=True, check=True, timeout=60
    )

    assert done.stdout.strip() == "[]"

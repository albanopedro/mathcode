"""OpencodeProvider against a fake `opencode` executable: no network, no real model."""

import json
import stat
import sys
from pathlib import Path

import pytest

from app.ai.base import AIError
from app.ai.opencode import (
    AGENT,
    OpencodeProvider,
    explain_failure,
    free_model,
    inline_config,
    parse_events,
    strip_code_fence,
)
from app.ai.prompt import SYSTEM_PROMPT
from app.models.intents import IntentName

MODEL = "opencode/space-bunny-free"

# Records how it was run, then answers what the test asked for.
FAKE = """#!{python}
import json, os, sys, time
with open(os.environ["FAKE_LOG"], "w") as log:
    json.dump({{
        "argv": sys.argv[1:],
        "cwd": os.getcwd(),
        "cwd_files": os.listdir("."),
        "config": os.environ.get("OPENCODE_CONFIG_CONTENT"),
        "stdin": sys.stdin.read(),
    }}, log)
time.sleep(float(os.environ.get("FAKE_SLEEP", "0")))
sys.stdout.write(open(os.environ["FAKE_STDOUT"]).read())
sys.stderr.write(os.environ.get("FAKE_STDERR", ""))
sys.exit(int(os.environ.get("FAKE_EXIT", "0")))
"""


class Fake:
    def __init__(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        self.path = tmp_path / "opencode"
        self.path.write_text(FAKE.format(python=sys.executable))
        self.path.chmod(self.path.stat().st_mode | stat.S_IXUSR)
        self.log = tmp_path / "log.json"
        self.stdout = tmp_path / "stdout.txt"
        self.stdout.write_text("")
        self.monkeypatch = monkeypatch
        monkeypatch.setenv("FAKE_LOG", str(self.log))
        monkeypatch.setenv("FAKE_STDOUT", str(self.stdout))

    def answer(self, *events: dict, extra: str = "") -> None:
        lines = [json.dumps(event) for event in events]
        self.stdout.write_text(extra + "\n".join(lines) + "\n")

    def set(self, name: str, value: str) -> None:
        self.monkeypatch.setenv(f"FAKE_{name}", value)

    def run(self) -> dict:
        return json.loads(self.log.read_text())

    def provider(self, timeout: float = 30) -> OpencodeProvider:
        return OpencodeProvider(MODEL, timeout, executable=str(self.path))


def text_event(text: str) -> dict:
    return {"type": "text", "part": {"type": "text", "text": text}}


START = {"type": "step_start", "part": {"type": "step-start"}}
ANSWER = {"intent": "derivative", "expression": "x^2 + 3x", "options": {}, "clarification": None}


@pytest.fixture
def fake(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Fake:
    return Fake(tmp_path, monkeypatch)


def test_reads_the_answer(fake: Fake) -> None:
    fake.answer(START, text_event(json.dumps(ANSWER)))

    candidate = fake.provider().interpret("derivada de x ao quadrado mais tres x")

    assert candidate.intent == IntentName.DERIVATIVE
    assert candidate.expression == "x^2 + 3x"
    assert candidate.options == {}


def test_runs_locked_down(fake: Fake) -> None:
    fake.answer(text_event(json.dumps(ANSWER)))

    fake.provider().interpret("derivada de x ao quadrado")
    run = fake.run()

    argv = run["argv"]
    assert argv[0] == "run"
    assert "--standalone" in argv
    assert argv[argv.index("--model") + 1] == MODEL
    assert argv[argv.index("--agent") + 1] == AGENT
    assert argv[argv.index("--format") + 1] == "json"
    assert "<<<" in argv[-1] and "derivada de x ao quadrado" in argv[-1]
    # An empty directory of its own, removed afterwards: nothing to read there.
    assert run["cwd_files"] == []
    assert not Path(run["cwd"]).exists()
    assert run["stdin"] == ""
    config = json.loads(run["config"])
    assert config == inline_config()
    assert config["permission"] == {"*": "deny"}
    assert config["agent"][AGENT]["permission"] == {"*": "deny"}
    assert config["agent"][AGENT]["prompt"] == SYSTEM_PROMPT


def test_the_text_is_one_argument_never_a_shell_command(fake: Fake) -> None:
    fake.answer(text_event(json.dumps(ANSWER)))
    text = 'x"; rm -rf ~; echo "$(whoami)'

    fake.provider().interpret(text)

    assert text in fake.run()["argv"][-1]


def test_accepts_a_code_fence(fake: Fake) -> None:
    fake.answer(text_event("```json\n" + json.dumps(ANSWER) + "\n```"))

    assert fake.provider().interpret("pedido").expression == "x^2 + 3x"


def test_uses_the_last_text_and_skips_log_lines(fake: Fake) -> None:
    fake.answer(
        text_event("pensando..."),
        text_event(json.dumps(ANSWER)),
        extra="INFO starting server\n",
    )

    assert fake.provider().interpret("pedido").intent == IntentName.DERIVATIVE


@pytest.mark.parametrize(
    "answer",
    [
        "a derivada é 2x + 3",  # prose, not JSON
        json.dumps({**ANSWER, "result": "2x + 3"}),  # an extra key: the answer itself
        json.dumps({**ANSWER, "intent": "derivada"}),  # not one of the intents
        json.dumps({**ANSWER, "options": {"order": 10**30}}),  # beyond the option limits
        json.dumps({**ANSWER, "options": {"variable": "x" * 101}}),
        json.dumps([ANSWER]),
    ],
)
def test_rejects_answers_out_of_format(fake: Fake, answer: str) -> None:
    fake.answer(text_event(answer))

    with pytest.raises(AIError, match="formato esperado"):
        fake.provider().interpret("pedido")


def test_rejects_any_cost(fake: Fake) -> None:
    fake.answer(
        text_event(json.dumps(ANSWER)),
        {"type": "step_finish", "part": {"type": "step-finish", "cost": 0.0001}},
    )

    with pytest.raises(AIError, match="custo"):
        fake.provider().interpret("pedido")


def test_zero_cost_is_fine(fake: Fake) -> None:
    fake.answer(
        text_event(json.dumps(ANSWER)),
        {"type": "step_finish", "part": {"type": "step-finish", "cost": 0}},
    )

    assert fake.provider().interpret("pedido").expression == "x^2 + 3x"


def test_no_answer(fake: Fake) -> None:
    fake.answer(START)

    with pytest.raises(AIError, match="não respondeu"):
        fake.provider().interpret("pedido")


def test_error_event(fake: Fake) -> None:
    fake.answer({"type": "error", "error": {"name": "FreeUsageLimitError"}})

    with pytest.raises(AIError, match="limite de uso gratuito"):
        fake.provider().interpret("pedido")


def test_failed_run(fake: Fake) -> None:
    fake.set("EXIT", "1")
    fake.set("STDERR", "Error: model not found\n")

    with pytest.raises(AIError, match="model not found"):
        fake.provider().interpret("pedido")


def test_timeout(fake: Fake) -> None:
    fake.set("SLEEP", "10")

    with pytest.raises(AIError, match=r"mais de 0\.5 s"):
        fake.provider(timeout=0.5).interpret("pedido")


def test_not_installed(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("PATH", str(tmp_path))

    with pytest.raises(AIError, match="não está instalado"):
        OpencodeProvider(MODEL, 30).interpret("pedido")


@pytest.mark.parametrize(
    "model", ["opencode/space-bunny-free", "opencode/some-model-free", "opencode/big-pickle"]
)
def test_free_models(model: str) -> None:
    assert free_model(model) == model


@pytest.mark.parametrize(
    "model",
    [
        "opencode/gpt-5",
        "opencode/claude-sonnet-4",
        "opencode/free",
        "opencode/space-bunny-free-pro",
        "anthropic/claude-free",
        "openai/gpt-4o-free",
        "space-bunny-free",
        "big-pickle",
        "",
    ],
)
def test_paid_or_unknown_models_are_refused(model: str) -> None:
    with pytest.raises(ValueError, match="free"):
        free_model(model)
    with pytest.raises(ValueError, match="free"):
        OpencodeProvider(model, 30)


def test_parse_events_ignores_noise() -> None:
    run = parse_events('not json\n[1, 2]\n"text"\n{"type": "text", "part": {"text": 5}}\n')

    assert run.texts == [] and run.errors == [] and run.cost == 0


def test_strip_code_fence() -> None:
    assert strip_code_fence('  {"a": 1}  ') == '{"a": 1}'
    assert strip_code_fence('```\n{"a": 1}\n```') == '{"a": 1}'
    assert strip_code_fence("```") == ""


def test_explain_failure_is_printable_and_short() -> None:
    message = explain_failure("ok\n\x1b[31mboom" + "!" * 500 + "\n\n")

    assert message.startswith("O OpenCode falhou: ")
    assert "\x1b" not in message
    assert len(message) < 250
    assert explain_failure("") == "O OpenCode falhou: sem detalhes"

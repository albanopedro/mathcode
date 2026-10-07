"""Interpretation through the user's own OpenCode CLI, with a free model (ADR 0004).

OpenCode's free models may only be used from within OpenCode, so the CLI is
run as a subprocess. Learned from the DevAI project and adapted to OpenCode v2:

- the run is locked down: an inline config (``OPENCODE_CONFIG_CONTENT``)
  defines a ``mathcode`` agent with every permission denied (no files, no
  commands);
- it runs with ``--standalone`` (a private server, not the shared background
  service) inside an **empty temporary directory**, because OpenCode watches
  the directory it runs in;
- only free models are accepted (``free_model``); a run that reports any cost
  is an error. OpenCode v2 did not report cost events in the runs observed in
  Phase 8, so the guarantee comes from the model list.
"""

import json
import os
import shutil
import subprocess
import tempfile
from dataclasses import dataclass, field
from typing import Any

import pydantic

from app.ai.base import AIError, IntentCandidate
from app.ai.prompt import SYSTEM_PROMPT, user_message

AGENT = "mathcode"
DEFAULT_MODEL = "opencode/space-bunny-free"  # free, zero data retention (OpenCode Zen)
# OpenCode's free models end in "-free", plus a few named exceptions.
FREE_EXCEPTIONS = frozenset({"big-pickle"})


def free_model(model: str) -> str:
    """Return ``model`` if it is one of OpenCode's free models; reject anything else."""
    name = model.removeprefix("opencode/")
    if not model.startswith("opencode/") or not (name.endswith("-free") or name in FREE_EXCEPTIONS):
        raise ValueError(
            f"{model!r} is not a free OpenCode model ('opencode/<name>-free'). "
            "Mathcode only uses free models (ADR 0001)."
        )
    return model


@dataclass
class RunOutput:
    texts: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    cost: float = 0.0


class OpencodeProvider:
    name = "opencode"

    def __init__(self, model: str, timeout: float, executable: str | None = None) -> None:
        self.model = free_model(model)
        self.timeout = timeout
        self.executable = executable  # None: find `opencode` on PATH

    def interpret(self, text: str) -> IntentCandidate:
        executable = self.executable or shutil.which("opencode")
        if executable is None:
            raise AIError("O OpenCode não está instalado (brew install opencode).")

        env = os.environ | {"OPENCODE_CONFIG_CONTENT": json.dumps(inline_config())}
        with tempfile.TemporaryDirectory(prefix="mathcode-ai-") as empty_dir:
            command = [
                executable,
                "run",
                "--standalone",
                "--model",
                self.model,
                "--agent",
                AGENT,
                "--format",
                "json",
                "--title",
                "mathcode",
                user_message(text),
            ]
            try:
                completed = subprocess.run(  # noqa: S603 - fixed argv, no shell
                    command,
                    cwd=empty_dir,
                    env=env,
                    capture_output=True,
                    text=True,
                    timeout=self.timeout,
                    stdin=subprocess.DEVNULL,
                    check=False,
                )
            except subprocess.TimeoutExpired as error:
                raise AIError(f"A IA levou mais de {self.timeout:g} s para responder.") from error

        if completed.returncode != 0:
            raise AIError(explain_failure(completed.stderr or completed.stdout))
        return to_candidate(parse_events(completed.stdout))


def inline_config() -> dict[str, Any]:
    """OpenCode config for this run only: an agent that cannot use any tool."""
    return {
        "permission": {"*": "deny"},
        "agent": {
            AGENT: {
                "mode": "primary",
                "description": "Mathcode: translates requests, no tools",
                "prompt": SYSTEM_PROMPT,
                "permission": {"*": "deny"},
            }
        },
    }


def parse_events(stdout: str) -> RunOutput:
    """Read the JSON event lines: text parts, costs (when reported), errors."""
    run = RunOutput()
    for line in stdout.splitlines():
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue  # a log line, not an event
        if not isinstance(event, dict):
            continue
        part = event.get("part") or {}
        kind = event.get("type")
        if kind == "text" and isinstance(part.get("text"), str):
            run.texts.append(part["text"])
        elif kind == "step_finish":
            run.cost += float(part.get("cost") or 0)
        elif kind == "error":
            run.errors.append(json.dumps(event.get("error") or event))
    return run


def to_candidate(run: RunOutput) -> IntentCandidate:
    if run.errors:
        raise AIError(explain_failure(run.errors[-1]))
    if run.cost > 0:
        raise AIError(
            f"A IA informou custo de {run.cost}. O Mathcode só usa modelos gratuitos, "
            "então a resposta foi descartada."
        )
    if not run.texts:
        raise AIError("A IA não respondeu.")
    try:
        return IntentCandidate.model_validate_json(strip_code_fence(run.texts[-1]))
    except pydantic.ValidationError as error:
        raise AIError("A resposta da IA não estava no formato esperado.") from error


def strip_code_fence(text: str) -> str:
    """Accept an answer wrapped in ```json ... ``` as well as plain JSON."""
    text = text.strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[1] if "\n" in text else ""
        text = text.rsplit("```", 1)[0]
    return text.strip()


def explain_failure(output: str) -> str:
    lowered = output.lower()
    if "freetiererror" in lowered or "free tier" in lowered:
        return "O plano gratuito do OpenCode recusou o pedido. Tente outro modelo gratuito."
    if "429" in output or "rate limit" in lowered or "freeusagelimit" in lowered:
        return "O limite de uso gratuito do OpenCode foi atingido. Tente mais tarde."
    last = next((line for line in reversed(output.strip().splitlines()) if line.strip()), "")
    detail = "".join(char if char.isprintable() else " " for char in last)
    return f"O OpenCode falhou: {detail[:200] or 'sem detalhes'}"

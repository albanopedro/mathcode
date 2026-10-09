"""The AI layer's contract (ADR 0004): the model interprets, it never calculates.

A provider turns a request in words into an ``IntentCandidate``: an operation,
the math text and its options. The candidate is validated here (Pydantic) and,
afterwards, by the same pipeline as any request: the math text goes through
the safe parser, the options through the intent's schema. Whatever number the
model may "know" is ignored: the Math Engine calculates.
"""

from typing import Protocol, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.core.limits import MAX_INPUT_LENGTH
from app.interpreter.planner import MAX_STEPS
from app.models.intents import IntentName, OptionValue


class AIError(Exception):
    """The provider could not interpret the request (not a math error)."""


class StepCandidate(BaseModel):
    """One step of a compound request (Phase 12, ADR 0021): a request of its own."""

    model_config = ConfigDict(extra="forbid")

    title: str = Field(min_length=1, max_length=60)
    intent: IntentName
    expression: str = Field(max_length=4 * MAX_INPUT_LENGTH)
    options: dict[str, OptionValue] = Field(default_factory=dict, max_length=8)

    @model_validator(mode="after")
    def _not_nested(self) -> Self:
        if self.intent is IntentName.ASSISTANT:
            raise ValueError("a step cannot be a plan")
        return self


class IntentCandidate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    intent: IntentName | None = None
    expression: str = Field(default="", max_length=4 * MAX_INPUT_LENGTH)
    # The same limits as a request's options: the candidate is a request too.
    options: dict[str, OptionValue] = Field(default_factory=dict, max_length=8)
    # A question for the user when the request is ambiguous or not math.
    clarification: str | None = Field(default=None, max_length=300)
    # A compound request: intent "assistant", the function in ``expression``, and
    # the calculations here; each one is calculated and verified like a request.
    steps: list[StepCandidate] | None = Field(default=None, min_length=1, max_length=MAX_STEPS)


class AIProvider(Protocol):
    name: str
    model: str

    def interpret(self, text: str) -> IntentCandidate:
        """Blocking call; the API runs it in a thread, with its own timeout."""
        ...

"""The AI layer's contract (ADR 0004): the model interprets, it never calculates.

A provider turns a request in words into an ``IntentCandidate``: an operation,
the math text and its options. The candidate is validated here (Pydantic) and,
afterwards, by the same pipeline as any request: the math text goes through
the safe parser, the options through the intent's schema. Whatever number the
model may "know" is ignored: the Math Engine calculates.
"""

from typing import Protocol

from pydantic import BaseModel, ConfigDict, Field

from app.core.limits import MAX_INPUT_LENGTH
from app.models.intents import IntentName, OptionValue


class AIError(Exception):
    """The provider could not interpret the request (not a math error)."""


class IntentCandidate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    intent: IntentName | None = None
    expression: str = Field(default="", max_length=4 * MAX_INPUT_LENGTH)
    # The same limits as a request's options: the candidate is a request too.
    options: dict[str, OptionValue] = Field(default_factory=dict, max_length=8)
    # A question for the user when the request is ambiguous or not math.
    clarification: str | None = Field(default=None, max_length=300)


class AIProvider(Protocol):
    name: str
    model: str

    def interpret(self, text: str) -> IntentCandidate:
        """Blocking call; the API runs it in a thread, with its own timeout."""
        ...

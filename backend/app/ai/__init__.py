"""Optional AI interpretation of requests in words (ADR 0004).

Used only when the user allows it (``allow_ai``), the server has a provider
configured, and neither the local rules nor the math parser understood the
request. The AI never calculates.
"""

import re

from app.ai.base import AIError, AIProvider, IntentCandidate
from app.ai.opencode import OpencodeProvider
from app.core.config import Settings
from app.core.errors import MathError
from app.core.limits import MAX_INPUT_LENGTH
from app.interpreter.language import match_language
from app.parsing import parse
from app.parsing.vocabulary import ALIASES, CONSTANTS, FUNCTIONS

__all__ = ["AIError", "AIProvider", "IntentCandidate", "build_provider", "needs_ai"]

_KNOWN_WORDS = {*FUNCTIONS, *ALIASES, *CONSTANTS}
_WORD = re.compile(r"[^\W\d_]{3,}")


def build_provider(settings: Settings) -> AIProvider | None:
    if settings.ai_provider == "opencode":
        return OpencodeProvider(settings.ai_model, settings.ai_timeout)
    return None


def needs_ai(text: str) -> bool:
    """True for a request in words that the rules and the parser do not understand.

    The rules may find the operation and still leave math in words ("derivada de
    x ao quadrado"); the math part is what must parse. "2 +" is a typo, not a
    phrase: the parser's message is more useful than an AI guess, so the AI is
    asked only when there are words other than function names.
    """
    if len(text) > MAX_INPUT_LENGTH:
        return False  # the pipeline answers INPUT_TOO_LONG; nothing is sent
    try:
        found = match_language(text)
    except MathError:
        return False  # the rules recognized it and have an answer (e.g. "not yet")
    math_text = text if found is None else found.text
    try:
        parse(math_text)
    except MathError:
        words = {word.lower() for word in _WORD.findall(math_text)}
        return bool(words - _KNOWN_WORDS)
    return False

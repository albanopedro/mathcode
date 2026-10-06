"""Character-level cleanup of the raw input.

Every character of the normalized text remembers where it came from in the
original input, so errors can point at what the user actually typed.
"""

import unicodedata
from dataclasses import dataclass

from app.core.errors import ErrorCode, MathError
from app.core.limits import MAX_INPUT_LENGTH

_SUPERSCRIPTS = {
    "⁰": "0",
    "¹": "1",
    "²": "2",
    "³": "3",
    "⁴": "4",
    "⁵": "5",
    "⁶": "6",
    "⁷": "7",
    "⁸": "8",
    "⁹": "9",
    "⁻": "-",
    "⁺": "+",
}

# Applied before NFKC, which would otherwise turn "x²" into "x2" and the
# ordinal "30º" (common on Brazilian keyboards) into "30o".
_REPLACEMENTS = {
    "×": "*",
    "·": "*",
    "⋅": "*",
    "∙": "*",
    "÷": "/",
    "∕": "/",
    "−": "-",
    "–": "-",
    "π": "pi",
    "º": "°",
}


@dataclass(frozen=True)
class NormalizedText:
    source: str
    text: str
    origins: tuple[int, ...]

    def origin(self, index: int) -> int:
        """Index in ``source`` of the character at ``index`` in ``text``."""
        if index < len(self.origins):
            return self.origins[index]
        return len(self.source)


def normalize(source: str) -> NormalizedText:
    if not source.strip():
        raise MathError(ErrorCode.EMPTY_INPUT, "Digite uma expressão.")
    if len(source) > MAX_INPUT_LENGTH:
        raise MathError(
            ErrorCode.INPUT_TOO_LONG,
            f"A entrada tem {len(source)} caracteres; o limite é {MAX_INPUT_LENGTH}.",
        )

    chars: list[str] = []
    origins: list[int] = []

    def emit(text: str, origin: int) -> None:
        chars.extend(text)
        origins.extend([origin] * len(text))

    i = 0
    while i < len(source):
        ch = source[i]
        if ch in _SUPERSCRIPTS:
            start = i
            while i < len(source) and source[i] in _SUPERSCRIPTS:
                i += 1
            run = source[start:i]
            emit("^", start)
            if len(run) > 1:
                emit("(", start)
            for offset, sup in enumerate(run):
                emit(_SUPERSCRIPTS[sup], start + offset)
            if len(run) > 1:
                emit(")", i - 1)
            continue
        if ch in _REPLACEMENTS:
            emit(_REPLACEMENTS[ch], i)
        elif ch.isspace():
            emit(" ", i)
        else:
            emit(unicodedata.normalize("NFKC", ch), i)
        i += 1

    return NormalizedText(source=source, text="".join(chars), origins=tuple(origins))

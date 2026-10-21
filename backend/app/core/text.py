"""Text helpers shared by the interpreter and the engine.

The rules of the project read what the user typed, so they compare words
without accents and without case. That folding was written twice, once in the
interpreter and once in the probability engine; the two copies could drift
apart, and one of them was even being imported by its private name.
"""

import unicodedata


def fold(text: str) -> str:
    """Lowercase without accents, one character for each character of ``text``."""
    return "".join(unicodedata.normalize("NFD", ch)[0].lower() for ch in text)

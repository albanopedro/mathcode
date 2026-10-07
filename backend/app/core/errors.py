"""Errors the math pipeline reports to the user (as opposed to bugs)."""

from enum import StrEnum


class ErrorCode(StrEnum):
    EMPTY_INPUT = "EMPTY_INPUT"
    INPUT_TOO_LONG = "INPUT_TOO_LONG"
    PARSE_ERROR = "PARSE_ERROR"
    AMBIGUOUS_INPUT = "AMBIGUOUS_INPUT"
    UNKNOWN_SYMBOL = "UNKNOWN_SYMBOL"
    UNKNOWN_FUNCTION = "UNKNOWN_FUNCTION"
    UNSUPPORTED_FEATURE = "UNSUPPORTED_FEATURE"
    DIVISION_BY_ZERO = "DIVISION_BY_ZERO"
    DOMAIN_ERROR = "DOMAIN_ERROR"
    LIMIT_EXCEEDED = "LIMIT_EXCEEDED"
    TIMEOUT = "TIMEOUT"
    SERVER_BUSY = "SERVER_BUSY"
    UNSUPPORTED_INTENT = "UNSUPPORTED_INTENT"
    INVALID_INPUT_FOR_INTENT = "INVALID_INPUT_FOR_INTENT"
    VERIFICATION_FAILED = "VERIFICATION_FAILED"
    AI_UNAVAILABLE = "AI_UNAVAILABLE"
    AI_FAILED = "AI_FAILED"
    INTERNAL_ERROR = "INTERNAL_ERROR"


class MathError(Exception):
    """An expected failure, with a message meant for the user.

    ``position`` is a 0-based index into the user's original input, when the
    problem can be pinned to one place.
    """

    def __init__(self, code: ErrorCode, message: str, position: int | None = None) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.position = position

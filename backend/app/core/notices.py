"""Non-fatal messages attached to a result: conventions applied, ambiguities resolved."""

from collections.abc import Iterable
from dataclasses import dataclass
from enum import StrEnum


class NoticeCode(StrEnum):
    AMBIGUOUS_IMPLICIT_MULTIPLICATION = "AMBIGUOUS_IMPLICIT_MULTIPLICATION"
    DECIMAL_COMMA = "DECIMAL_COMMA"
    LOG_BASE_10 = "LOG_BASE_10"
    ANGLE_IN_RADIANS = "ANGLE_IN_RADIANS"
    REAL_ROOT = "REAL_ROOT"
    DOMAIN_CHANGED = "DOMAIN_CHANGED"
    COMPLEX_SOLUTIONS_OMITTED = "COMPLEX_SOLUTIONS_OMITTED"
    ROOTS_SHOWN_APPROXIMATELY = "ROOTS_SHOWN_APPROXIMATELY"
    NOT_DIFFERENTIABLE_POINTS = "NOT_DIFFERENTIABLE_POINTS"
    ABSOLUTE_VALUE_IN_LOG = "ABSOLUTE_VALUE_IN_LOG"
    ONE_SIDED_DOMAIN = "ONE_SIDED_DOMAIN"


@dataclass(frozen=True)
class Notice:
    code: NoticeCode
    message: str


def unique(notices: Iterable[Notice]) -> list[Notice]:
    """Drops repeated notices, keeping the first occurrence of each."""
    return list(dict.fromkeys(notices))

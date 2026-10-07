"""Time limits for the verification, inside a calculation worker (ADR 0010).

SymPy cannot be interrupted from another thread, so the limit is a SIGALRM
timer: when it fires, ``VerificationTimeout`` is raised wherever the code is.
Limits nest. The verification as a whole has one (the worker's budget), and
optional steps (a comparison of methods, a ``simplify``) have their own,
shorter ones: when a step runs out of time, ``StepTimeout`` is raised at the
step and the verification goes on without it; when the whole budget runs out,
``VerificationTimeout`` reaches the caller.

Signals only work in the main thread; elsewhere the limits do nothing (the
worker pool's hard timeout still applies).
"""

import signal
import threading
import time
from collections.abc import Iterator
from contextlib import contextmanager
from types import FrameType


class VerificationTimeout(BaseException):
    """The verification's time ran out.

    A BaseException, like KeyboardInterrupt: library code that catches
    ``Exception`` must not swallow it.
    """


class StepTimeout(Exception):
    """An optional step ran out of its own time; the verification goes on."""


_deadlines: list[float] = []  # absolute (time.monotonic), innermost last


def _usable() -> bool:
    return hasattr(signal, "setitimer") and threading.current_thread() is threading.main_thread()


def _on_alarm(signum: int, frame: FrameType | None) -> None:
    raise VerificationTimeout


def _arm() -> None:
    if _deadlines:
        remaining = _deadlines[-1] - time.monotonic()
        signal.setitimer(signal.ITIMER_REAL, max(remaining, 1e-4))  # 0 would disarm it
    else:
        signal.setitimer(signal.ITIMER_REAL, 0)


@contextmanager
def time_limit(seconds: float | None, *, step: bool = False) -> Iterator[None]:
    """Run the body for at most ``seconds`` (None: no limit of its own).

    With ``step=True``, running out of this limit raises ``StepTimeout`` while
    an enclosing limit still has time left.
    """
    if seconds is None or not _usable():
        yield
        return
    outer = _deadlines[-1] if _deadlines else None
    deadline = time.monotonic() + seconds
    if outer is not None:
        deadline = min(deadline, outer)
    previous = signal.signal(signal.SIGALRM, _on_alarm) if outer is None else None
    _deadlines.append(deadline)
    _arm()
    try:
        yield
    except VerificationTimeout:
        if step and (outer is None or time.monotonic() < outer):
            raise StepTimeout from None
        raise
    finally:
        _deadlines.pop()
        _arm()
        if outer is None:
            signal.signal(signal.SIGALRM, previous)

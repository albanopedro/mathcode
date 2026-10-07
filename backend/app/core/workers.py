"""Calculation workers: warm processes with a hard timeout (ADR 0002, section 4).

SymPy cannot be interrupted from a thread, and some valid inputs take minutes
(e.g. simplifying ``(x+1)^1000*(x+2)^1000``). So every calculation runs in a
separate process, which is killed and replaced when it exceeds the timeout.

Workers are started with "spawn" (safe in a multi-threaded server) and import
SymPy once, at startup, so requests do not pay for it.
"""

import asyncio
import contextlib
import logging
import multiprocessing
import signal
from dataclasses import dataclass
from multiprocessing.connection import Connection
from multiprocessing.process import BaseProcess
from typing import Any

from app.core.errors import ErrorCode
from app.models.intents import IntentName
from app.models.result import MathResult, ResultError

logger = logging.getLogger(__name__)

_CONTEXT = multiprocessing.get_context("spawn")
_STARTUP_TIMEOUT = 60.0  # seconds to import SymPy and answer the warm-up job
_WARM_UP = ("1 + 1", None, None)

type Job = tuple[str, str | None, dict[str, str | int] | None]


def _serve(conn: Connection) -> None:
    """Worker main loop: receive ``(text, intent, options)``, send back a MathResult as JSON."""
    signal.signal(signal.SIGINT, signal.SIG_IGN)  # Ctrl+C is handled by the server
    # Imported here, not at module level: the server process never loads SymPy.
    from app.calculator import calculate

    while True:
        try:
            job = conn.recv()
        except EOFError:
            return  # the server went away
        if job is None:
            return
        text, intent, options = job
        conn.send(calculate(text, intent, options).model_dump(mode="json"))


@dataclass(eq=False)
class _Worker:
    process: BaseProcess
    conn: Connection

    def kill(self) -> None:
        self.process.kill()
        self.process.join(timeout=5)
        self.conn.close()


class _Timeout(Exception):
    pass


class WorkerPool:
    def __init__(self, size: int, timeout: float, queue_timeout: float) -> None:
        self._size = size
        self._timeout = timeout
        self._queue_timeout = queue_timeout
        self._idle: asyncio.Queue[_Worker] = asyncio.Queue()
        self._workers: set[_Worker] = set()
        self._tasks: set[asyncio.Task[None]] = set()
        self._closed = False

    async def start(self) -> None:
        workers = await asyncio.gather(*(asyncio.to_thread(_spawn) for _ in range(self._size)))
        for worker in workers:
            self._workers.add(worker)
            self._idle.put_nowait(worker)

    async def stop(self) -> None:
        self._closed = True
        # Replacements in progress are awaited, not cancelled: a cancelled spawn
        # would leave an untracked process behind. Once closed, they kill it.
        await asyncio.gather(*self._tasks, return_exceptions=True)
        workers, self._workers = self._workers, set()
        await asyncio.to_thread(_shutdown, workers)

    async def calculate(
        self,
        text: str,
        intent: IntentName | None,
        options: dict[str, str | int] | None = None,
    ) -> MathResult:
        try:
            worker = await asyncio.wait_for(self._idle.get(), timeout=self._queue_timeout)
        except TimeoutError:
            return _failure(
                text,
                intent,
                ErrorCode.SERVER_BUSY,
                "O servidor está ocupado com outros cálculos. Tente de novo em instantes.",
            )

        job: Job = (text, intent.value if intent else None, options)
        try:
            data = await asyncio.to_thread(self._roundtrip, worker, job)
        except _Timeout:
            self._replace(worker)
            return _failure(
                text,
                intent,
                ErrorCode.TIMEOUT,
                f"O cálculo passou de {self._timeout:g} s e foi interrompido.",
            )
        except EOFError, OSError:
            logger.exception("calculation worker died")
            self._replace(worker)
            return _failure(text, intent, ErrorCode.INTERNAL_ERROR, "Erro interno ao calcular.")
        except BaseException:
            # The request was cancelled mid-calculation: the worker's state is
            # unknown, so it is not reused.
            self._replace(worker)
            raise

        self._idle.put_nowait(worker)
        return MathResult.model_validate(data)

    def _roundtrip(self, worker: _Worker, job: Job) -> Any:
        worker.conn.send(job)
        if not worker.conn.poll(self._timeout):
            raise _Timeout
        return worker.conn.recv()

    def _replace(self, worker: _Worker) -> None:
        self._workers.discard(worker)
        task = asyncio.create_task(self._respawn(worker))
        self._tasks.add(task)
        task.add_done_callback(self._tasks.discard)

    async def _respawn(self, dead: _Worker) -> None:
        await asyncio.to_thread(dead.kill)
        if self._closed:
            return
        try:
            worker = await asyncio.to_thread(_spawn)
        except Exception:
            logger.exception("could not start a replacement calculation worker")
            return
        if self._closed:
            await asyncio.to_thread(worker.kill)
            return
        self._workers.add(worker)
        self._idle.put_nowait(worker)


def _spawn() -> _Worker:
    parent, child = _CONTEXT.Pipe()
    process = _CONTEXT.Process(target=_serve, args=(child,), daemon=True, name="mathcode-worker")
    process.start()
    child.close()
    worker = _Worker(process, parent)
    try:
        parent.send(_WARM_UP)
        if not parent.poll(_STARTUP_TIMEOUT):
            raise RuntimeError("calculation worker did not start in time")
        parent.recv()
    except BaseException:
        worker.kill()
        raise
    return worker


def _shutdown(workers: set[_Worker]) -> None:
    for worker in workers:
        with contextlib.suppress(OSError):
            worker.conn.send(None)  # ask it to exit cleanly
    for worker in workers:
        worker.process.join(timeout=2)
        if worker.process.is_alive():
            worker.process.kill()
            worker.process.join(timeout=5)
        worker.conn.close()


def _failure(text: str, intent: IntentName | None, code: ErrorCode, message: str) -> MathResult:
    return MathResult(
        success=False, intent=intent, input=text, error=ResultError(code=code, message=message)
    )

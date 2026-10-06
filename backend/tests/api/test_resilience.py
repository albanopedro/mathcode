"""Timeouts, dead workers and a full queue: the server keeps answering."""

import os
import signal
import threading
import time
from collections.abc import Iterator

import pytest
from api_helpers import SLOW_INPUT, running_app
from fastapi.testclient import TestClient


@pytest.fixture(scope="module")
def short_timeout() -> Iterator[TestClient]:
    yield from running_app(workers=1, calculation_timeout=0.5)


@pytest.fixture(scope="module")
def short_queue() -> Iterator[TestClient]:
    yield from running_app(workers=1, calculation_timeout=1.5, queue_timeout=0.2)


def worker_pids(client: TestClient) -> set[int]:
    return {w.process.pid for w in client.app.state.pool._workers}


def test_slow_calculation_times_out(short_timeout: TestClient) -> None:
    started = time.perf_counter()
    response = short_timeout.post("/api/calculate", json={"input": SLOW_INPUT})
    elapsed = time.perf_counter() - started

    assert response.status_code == 200
    data = response.json()
    assert data["success"] is False
    assert data["error"]["code"] == "TIMEOUT"
    assert "0.5 s" in data["error"]["message"]
    assert elapsed < 5


def test_the_timed_out_worker_is_replaced(short_timeout: TestClient) -> None:
    before = worker_pids(short_timeout)
    short_timeout.post("/api/calculate", json={"input": SLOW_INPUT})

    response = short_timeout.post("/api/calculate", json={"input": "2 + 2"})

    assert response.status_code == 200
    assert response.json()["result"]["plain"] == "4"
    assert worker_pids(short_timeout).isdisjoint(before)


def test_a_dead_worker_is_an_internal_error_and_is_replaced(short_timeout: TestClient) -> None:
    (pid,) = worker_pids(short_timeout)
    os.kill(pid, signal.SIGKILL)
    time.sleep(0.2)

    response = short_timeout.post("/api/calculate", json={"input": "2 + 2"})
    assert response.status_code == 500
    data = response.json()
    assert data["error"]["code"] == "INTERNAL_ERROR"
    assert data["result"] is None

    recovered = short_timeout.post("/api/calculate", json={"input": "2 + 2"})
    assert recovered.status_code == 200
    assert pid not in worker_pids(short_timeout)


def test_full_queue_is_503(short_queue: TestClient) -> None:
    slow = threading.Thread(
        target=short_queue.post, args=("/api/calculate",), kwargs={"json": {"input": SLOW_INPUT}}
    )
    slow.start()
    time.sleep(0.3)  # the only worker is now busy

    response = short_queue.post("/api/calculate", json={"input": "2 + 2"})
    slow.join()

    assert response.status_code == 503
    data = response.json()
    assert data["success"] is False
    assert data["error"]["code"] == "SERVER_BUSY"

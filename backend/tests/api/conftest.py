from collections.abc import Iterator

import pytest
from api_helpers import running_app
from fastapi.testclient import TestClient


@pytest.fixture(scope="module")
def api() -> Iterator[TestClient]:
    yield from running_app(workers=2)

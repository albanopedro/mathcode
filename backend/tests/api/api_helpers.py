from collections.abc import Iterator

from fastapi.testclient import TestClient

from app.core.config import Settings
from app.main import create_app

# Simplifying this takes minutes in SymPy, although it is within every input limit.
SLOW_INPUT = "(x+1)^1000*(x+2)^1000"


def running_app(**overrides: object) -> Iterator[TestClient]:
    """A client whose lifespan ran: real worker processes are up."""
    settings = Settings.model_validate({"environment": "test", **overrides})
    with TestClient(create_app(settings)) as client:
        yield client

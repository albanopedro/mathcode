import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.core.config import Settings
from app.main import create_app


def test_defaults_without_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("MATHCODE_ENVIRONMENT", raising=False)
    monkeypatch.delenv("MATHCODE_DOCS_ENABLED", raising=False)

    settings = Settings(_env_file=None)

    assert settings.environment == "development"
    assert settings.show_docs is True


def test_reads_prefixed_env_vars(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MATHCODE_ENVIRONMENT", "production")

    settings = Settings(_env_file=None)

    assert settings.environment == "production"
    assert settings.show_docs is False


def test_docs_flag_overrides_environment_default(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MATHCODE_ENVIRONMENT", "production")
    monkeypatch.setenv("MATHCODE_DOCS_ENABLED", "true")

    assert Settings(_env_file=None).show_docs is True


def test_rejects_unknown_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MATHCODE_ENVIRONMENT", "staging")

    with pytest.raises(ValidationError):
        Settings(_env_file=None)


def test_docs_routes_follow_settings() -> None:
    dev = TestClient(create_app(Settings(_env_file=None, environment="development")))
    prod = TestClient(create_app(Settings(_env_file=None, environment="production")))

    assert dev.get("/api/docs").status_code == 200
    assert dev.get("/api/openapi.json").status_code == 200
    assert prod.get("/api/docs").status_code == 404
    assert prod.get("/api/openapi.json").status_code == 404

from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app import main
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


def test_the_docs_page_loads_nothing_from_outside(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    (tmp_path / "swagger-ui-bundle.js").write_text("// swagger")
    (tmp_path / "swagger-ui.css").write_text("/* swagger */")
    monkeypatch.setattr(main, "SWAGGER_DIR", tmp_path)
    client = TestClient(create_app(Settings(_env_file=None, environment="development")))

    page = client.get("/api/docs").text
    assert "/api/static/swagger/swagger-ui-bundle.js" in page
    assert "/api/static/swagger/swagger-ui.css" in page
    assert '"validatorUrl": null' in page
    assert "https://" not in page.replace("https://fastapi.tiangolo.com", "")
    assert client.get("/api/static/swagger/swagger-ui-bundle.js").text == "// swagger"


def test_the_docs_page_explains_missing_files(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(main, "SWAGGER_DIR", tmp_path / "missing")
    client = TestClient(create_app(Settings(_env_file=None, environment="development")))

    response = client.get("/api/docs")
    assert response.status_code == 200
    assert "npm install" in response.text

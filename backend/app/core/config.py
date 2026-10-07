"""Application settings, read from ``MATHCODE_*`` environment variables.

A ``.env`` file at the project root (``Mathcode/.env``) is also read, if present.
See ``.env.example`` for the available variables.
"""

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

PROJECT_ROOT = Path(__file__).resolve().parents[3]

Environment = Literal["development", "test", "production"]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="MATHCODE_",
        env_file=PROJECT_ROOT / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    environment: Environment = "development"
    # Interactive OpenAPI docs (/api/docs). Off by default in production.
    docs_enabled: bool | None = None

    # Calculation worker processes (ADR 0002, section 4).
    workers: int = Field(default=2, ge=1, le=16)
    # Seconds a single calculation may run before its worker is killed.
    calculation_timeout: float = Field(default=5.0, gt=0, le=60)
    # Seconds a request may wait for a free worker before getting HTTP 503.
    queue_timeout: float = Field(default=10.0, gt=0, le=120)

    # Optional AI interpretation of requests in words (ADR 0004). "none" keeps
    # everything local; "opencode" uses a free OpenCode model, only for requests
    # whose user ticked "Permitir IA".
    ai_provider: Literal["none", "opencode"] = "none"
    ai_model: str = "opencode/space-bunny-free"
    ai_timeout: float = Field(default=90.0, ge=5, le=300)

    @field_validator("ai_model")
    @classmethod
    def _only_free_models(cls, model: str) -> str:
        # Imported here: app.ai imports this module (import cycle at load time).
        from app.ai.opencode import free_model

        return free_model(model)

    @property
    def show_docs(self) -> bool:
        if self.docs_enabled is not None:
            return self.docs_enabled
        return self.environment != "production"


@lru_cache
def get_settings() -> Settings:
    return Settings()

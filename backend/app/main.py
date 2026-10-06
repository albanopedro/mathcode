from fastapi import FastAPI

from app import __version__
from app.api import health
from app.core.config import Settings, get_settings


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()
    app = FastAPI(
        title="Mathcode API",
        version=__version__,
        docs_url="/api/docs" if settings.show_docs else None,
        redoc_url=None,
        openapi_url="/api/openapi.json" if settings.show_docs else None,
    )
    app.include_router(health.router, prefix="/api")
    return app


app = create_app()

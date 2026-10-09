from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.openapi.docs import get_swagger_ui_html
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles

from app import __version__
from app.ai import build_provider
from app.ai.service import AIService
from app.api import calculate, health
from app.core.config import Settings, get_settings
from app.core.workers import WorkerPool


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        pool = WorkerPool(
            size=settings.workers,
            timeout=settings.calculation_timeout,
            queue_timeout=settings.queue_timeout,
        )
        await pool.start()
        app.state.pool = pool
        app.state.ai = AIService(build_provider(settings), settings.ai_timeout)
        try:
            yield
        finally:
            await pool.stop()

    app = FastAPI(
        title="Mathcode API",
        version=__version__,
        docs_url=None,  # served below, with local files
        redoc_url=None,
        openapi_url="/api/openapi.json" if settings.show_docs else None,
        lifespan=lifespan,
    )
    app.include_router(health.router, prefix="/api")
    app.include_router(calculate.router, prefix="/api")
    if settings.show_docs:
        _add_docs(app)
    return app


# Swagger UI, copied here from npm by frontend/scripts/copy-swagger.mjs (not in Git).
SWAGGER_DIR = Path(__file__).parent / "static" / "swagger"
_SWAGGER_MISSING = """<!doctype html><meta charset="utf-8"><title>Mathcode API</title>
<p>Os arquivos do Swagger UI não estão no backend. Rode <code>npm install</code> (ou
<code>npm run swagger</code>) na pasta <code>frontend</code> e recarregue esta página.</p>
<p>A especificação da API está em <a href="/api/openapi.json">/api/openapi.json</a>.</p>
"""


def _add_docs(app: FastAPI) -> None:
    """/api/docs with Swagger UI from local files: nothing comes from a CDN (ADR 0001)."""
    if SWAGGER_DIR.is_dir():
        app.mount("/api/static/swagger", StaticFiles(directory=SWAGGER_DIR), name="swagger")

    @app.get("/api/docs", include_in_schema=False)
    async def docs() -> HTMLResponse:
        if not (SWAGGER_DIR / "swagger-ui-bundle.js").is_file():
            return HTMLResponse(_SWAGGER_MISSING)
        return get_swagger_ui_html(
            openapi_url="/api/openapi.json",
            title="Mathcode API",
            swagger_js_url="/api/static/swagger/swagger-ui-bundle.js",
            swagger_css_url="/api/static/swagger/swagger-ui.css",
            swagger_favicon_url="/api/static/swagger/favicon-32x32.png",
            # No online validator badge: it would send the spec's address outside.
            swagger_ui_parameters={"validatorUrl": None},
        )


app = create_app()

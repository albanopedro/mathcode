from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app import __version__
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
        try:
            yield
        finally:
            await pool.stop()

    app = FastAPI(
        title="Mathcode API",
        version=__version__,
        docs_url="/api/docs" if settings.show_docs else None,
        redoc_url=None,
        openapi_url="/api/openapi.json" if settings.show_docs else None,
        lifespan=lifespan,
    )
    app.include_router(health.router, prefix="/api")
    app.include_router(calculate.router, prefix="/api")
    return app


app = create_app()

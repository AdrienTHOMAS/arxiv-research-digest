"""FastAPI application factory and lifespan management.

Creates the production application instance with structured logging,
database lifecycle hooks, CORS middleware, and all API routers mounted.
"""

from __future__ import annotations

import sys
from contextlib import asynccontextmanager
from pathlib import Path
from typing import TYPE_CHECKING

import structlog
from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.templating import Jinja2Templates

from arxiv_digest.api.v1.router import router as v1_router
from arxiv_digest.config import get_settings
from arxiv_digest.database import close_db, init_db

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)

_TEMPLATES_DIR = Path(__file__).resolve().parent / "templates"
templates = Jinja2Templates(directory=str(_TEMPLATES_DIR))


def _configure_structlog(log_level: str) -> None:
    """Configure structlog processors and output format.

    Uses JSON rendering when the log level is INFO or above (production),
    and colourful console output for DEBUG (development).

    Args:
        log_level: The minimum log level string (e.g. ``DEBUG``, ``INFO``).
    """
    shared_processors: list[structlog.types.Processor] = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_log_level,
        structlog.stdlib.add_logger_name,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.UnicodeDecoder(),
    ]

    is_development = log_level.upper() == "DEBUG"

    if is_development:
        renderer: structlog.types.Processor = structlog.dev.ConsoleRenderer()
    else:
        renderer = structlog.processors.JSONRenderer()

    structlog.configure(
        processors=[
            *shared_processors,
            structlog.processors.format_exc_info,
            renderer,
        ],
        wrapper_class=structlog.stdlib.BoundLogger,
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(file=sys.stderr),
        cache_logger_on_first_use=True,
    )


@asynccontextmanager
async def _lifespan(_app: FastAPI) -> AsyncGenerator[None, None]:
    """Manage application startup and shutdown lifecycle events.

    On startup: initialises structured logging and the database engine.
    On shutdown: disposes of the database connection pool.

    Args:
        app: The FastAPI application instance.
    """
    settings = get_settings()
    _configure_structlog(settings.LOG_LEVEL)

    logger.info(
        "app.starting",
        app_name=settings.APP_NAME,
        version=settings.APP_VERSION,
    )

    await init_db()

    logger.info("app.started")

    yield

    logger.info("app.shutting_down")
    await close_db()
    logger.info("app.stopped")


def create_app() -> FastAPI:
    """Build and return the fully configured FastAPI application.

    Sets up the lifespan manager, CORS middleware, exception handlers,
    the root endpoint, and mounts all API routers.

    Returns:
        A ready-to-serve :class:`FastAPI` instance.
    """
    settings = get_settings()

    app = FastAPI(
        title=settings.APP_NAME,
        version=settings.APP_VERSION,
        description="Agentic ArXiv research monitor powered by Claude.",
        lifespan=_lifespan,
    )

    # ── CORS middleware ──────────────────────────────────────────────────
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # ── Exception handlers ───────────────────────────────────────────────

    @app.exception_handler(ValueError)
    async def value_error_handler(request: Request, exc: ValueError) -> JSONResponse:
        """Return a 422 response for unhandled ValueError exceptions."""
        logger.warning("error.value_error", detail=str(exc), path=request.url.path)
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content={"detail": str(exc)},
        )

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
        """Return a 500 response for unexpected exceptions."""
        logger.exception(
            "error.unhandled",
            path=request.url.path,
            exception_type=type(exc).__name__,
        )
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"detail": "Internal server error."},
        )

    # ── Routes ───────────────────────────────────────────────────────────

    @app.get(
        "/",
        summary="Root",
        description="Returns basic application information.",
        tags=["root"],
    )
    async def root() -> dict[str, str]:
        """Return application metadata and a link to the health endpoint."""
        return {
            "app": settings.APP_NAME,
            "version": settings.APP_VERSION,
            "docs": "/docs",
            "health": "/api/v1/health",
        }

    app.include_router(v1_router, prefix="/api/v1")

    return app

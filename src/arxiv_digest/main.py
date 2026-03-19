"""FastAPI application factory and lifespan management.

Creates the production application instance with structured logging,
database lifecycle hooks, CORS middleware, and all API routers mounted.
"""

from __future__ import annotations

import math
import sys
from contextlib import asynccontextmanager
from pathlib import Path
from typing import TYPE_CHECKING

import structlog
from fastapi import Depends, FastAPI, Query, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import func, select
from sqlalchemy.orm import selectinload
from starlette.templating import Jinja2Templates

from arxiv_digest.api.deps import get_db_session
from arxiv_digest.api.v1.router import router as v1_router
from arxiv_digest.config import get_settings
from arxiv_digest.database import close_db, init_db
from arxiv_digest.models.digest import Digest
from arxiv_digest.models.paper import Paper
from arxiv_digest.schemas.topic import load_topics

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator

    from sqlalchemy.ext.asyncio import AsyncSession

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)

_TEMPLATES_DIR = Path(__file__).resolve().parent / "templates"
templates = Jinja2Templates(directory=str(_TEMPLATES_DIR))

_UI_TEMPLATES_DIR = Path(__file__).resolve().parent / "ui" / "templates"
_UI_STATIC_DIR = Path(__file__).resolve().parent / "ui" / "static"
ui_templates = Jinja2Templates(directory=str(_UI_TEMPLATES_DIR))


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
        logger_factory=structlog.stdlib.LoggerFactory(),
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

    # ── Static files ─────────────────────────────────────────────────────
    if _UI_STATIC_DIR.exists():
        app.mount("/static", StaticFiles(directory=str(_UI_STATIC_DIR)), name="static")

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

    # ── API routes ───────────────────────────────────────────────────────

    app.include_router(v1_router, prefix="/api/v1")

    # ── UI routes ────────────────────────────────────────────────────────

    @app.get("/", response_class=HTMLResponse, include_in_schema=False)
    async def index(
        request: Request,
        session: AsyncSession = Depends(get_db_session),
    ) -> HTMLResponse:
        """Render the dashboard with the latest digests per topic."""
        query = (
            select(Digest)
            .order_by(Digest.run_date.desc(), Digest.created_at.desc())
            .limit(50)
        )
        result = await session.execute(query)
        digests = list(result.scalars().all())

        return ui_templates.TemplateResponse(
            "index.html",
            {"request": request, "digests": digests},
        )

    @app.get("/digest/{digest_id}", response_class=HTMLResponse, include_in_schema=False)
    async def digest_detail(
        request: Request,
        digest_id: str,
        session: AsyncSession = Depends(get_db_session),
    ) -> HTMLResponse:
        """Render a full digest view with summary and papers."""
        query = (
            select(Digest)
            .options(selectinload(Digest.papers))
            .where(Digest.id == digest_id)
        )
        result = await session.execute(query)
        digest = result.scalar_one_or_none()

        if digest is None:
            return HTMLResponse(content="Digest not found", status_code=404)

        return ui_templates.TemplateResponse(
            "digest.html",
            {"request": request, "digest": digest},
        )

    @app.get("/papers", response_class=HTMLResponse, include_in_schema=False)
    async def papers_page(
        request: Request,
        topic_id: str | None = Query(default=None),
        min_score: float | None = Query(default=None, ge=0.0, le=1.0),
        page: int = Query(default=1, ge=1),
        page_size: int = Query(default=20, ge=1, le=100),
        session: AsyncSession = Depends(get_db_session),
    ) -> HTMLResponse:
        """Render the filterable papers table."""
        query = select(Paper)
        count_query = select(func.count(Paper.id))

        if topic_id:
            query = query.where(Paper.topic_id == topic_id)
            count_query = count_query.where(Paper.topic_id == topic_id)

        if min_score is not None:
            query = query.where(Paper.relevance_score >= min_score)
            count_query = count_query.where(Paper.relevance_score >= min_score)

        total_result = await session.execute(count_query)
        total = total_result.scalar_one()

        offset = (page - 1) * page_size
        query = query.order_by(
            Paper.relevance_score.desc().nullslast(),
            Paper.published_date.desc(),
        )
        query = query.offset(offset).limit(page_size)

        result = await session.execute(query)
        papers = list(result.scalars().all())
        pages = math.ceil(total / page_size) if total > 0 else 0

        try:
            topics = load_topics()
        except Exception:
            topics = []

        return ui_templates.TemplateResponse(
            "papers.html",
            {
                "request": request,
                "papers": papers,
                "topics": topics,
                "page": page,
                "page_size": page_size,
                "pages": pages,
                "total": total,
                "topic_id": topic_id,
                "min_score": min_score,
            },
        )

    return app

app = create_app()

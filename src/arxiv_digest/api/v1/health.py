"""Health check endpoint for monitoring and readiness probes."""

from __future__ import annotations

from typing import TYPE_CHECKING

import structlog
from fastapi import APIRouter, Depends
from sqlalchemy import text

from arxiv_digest.api.deps import get_db_session

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession
from arxiv_digest.config import get_settings

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)

router = APIRouter(tags=["health"])


@router.get(
    "/health",
    summary="Health check",
    description="Returns application health status including database connectivity.",
)
async def health_check(
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, str]:
    """Return the current health status of the application.

    Performs a lightweight ``SELECT 1`` query to verify database
    connectivity and reports the result alongside the application version.
    """
    settings = get_settings()
    db_status = "connected"

    try:
        await session.execute(text("SELECT 1"))
    except Exception:
        logger.exception("health.db_check_failed")
        db_status = "disconnected"

    return {
        "status": "healthy",
        "version": settings.APP_VERSION,
        "database": db_status,
    }

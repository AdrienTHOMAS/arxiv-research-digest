"""FastAPI dependency injection providers.

Provides reusable dependencies for database sessions and API key
authentication across all API endpoints.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import structlog
from fastapi import Depends, HTTPException, status
from fastapi.security import APIKeyHeader

from arxiv_digest.config import get_settings
from arxiv_digest.database import get_db

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator

    from sqlalchemy.ext.asyncio import AsyncSession

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)

_api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    """Yield an async database session for FastAPI dependency injection.

    Wraps :func:`arxiv_digest.database.get_db` so that all API routes
    use a consistent dependency name.
    """
    async for session in get_db():
        yield session


async def verify_api_key(
    api_key: str | None = Depends(_api_key_header),
) -> str:
    """Validate the ``X-API-Key`` header against the configured secret.

    Args:
        api_key: The API key extracted from the request header.

    Returns:
        The validated API key string.

    Raises:
        HTTPException: 401 if the key is missing or does not match.
    """
    settings = get_settings()
    expected = settings.API_KEY.get_secret_value()

    if api_key is None:
        logger.warning("auth.missing_key")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing X-API-Key header.",
        )

    if api_key != expected:
        logger.warning("auth.invalid_key")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API key.",
        )

    return api_key

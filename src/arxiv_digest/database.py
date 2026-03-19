"""Async SQLAlchemy database engine, session factory, and FastAPI integration.

Provides:
- ``async_engine`` / ``async_session_factory`` created lazily via ``init_db``
- ``get_db`` — an async generator suitable as a FastAPI ``Depends`` provider
- ``init_db`` / ``close_db`` — lifespan helpers for startup / shutdown
- ``Base`` — declarative base class for ORM models
"""

from __future__ import annotations

import datetime
from typing import TYPE_CHECKING
from uuid import uuid4

import structlog
from sqlalchemy import MetaData, String
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import (
    DeclarativeBase,
    Mapped,
    mapped_column,
)

from arxiv_digest.config import get_settings

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)

# ── Naming convention for constraints (Alembic-friendly) ────────────────
NAMING_CONVENTION: dict[str, str] = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}

metadata = MetaData(naming_convention=NAMING_CONVENTION)


def _utcnow() -> datetime.datetime:
    """Return the current UTC time as an aware datetime."""
    return datetime.datetime.now(tz=datetime.UTC)


def _new_uuid() -> str:
    """Generate a new UUID v4 as a string."""
    return str(uuid4())


class Base(DeclarativeBase):
    """Declarative base shared by all ORM models.

    Every model inheriting from ``Base`` automatically receives:
    - ``id`` — UUID v4 primary key (stored as text for portability)
    - ``created_at`` — UTC timestamp set on insert
    - ``updated_at`` — UTC timestamp set on insert and updated on flush
    """

    metadata = metadata

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=_new_uuid,
    )
    created_at: Mapped[datetime.datetime] = mapped_column(
        default=_utcnow,
    )
    updated_at: Mapped[datetime.datetime] = mapped_column(
        default=_utcnow,
        onupdate=_utcnow,
    )


# ── Module-level engine / session state ─────────────────────────────────

_engine: AsyncEngine | None = None
_session_factory: async_sessionmaker[AsyncSession] | None = None


class DatabaseNotInitialisedError(RuntimeError):
    """Raised when the database layer is accessed before ``init_db`` is called."""


def _get_engine() -> AsyncEngine:
    """Return the current engine or raise if ``init_db`` has not been called."""
    if _engine is None:
        msg = "Database engine is not initialised. Call init_db() during application startup."
        raise DatabaseNotInitialisedError(msg)
    return _engine


def _get_session_factory() -> async_sessionmaker[AsyncSession]:
    """Return the current session factory or raise if uninitialised."""
    if _session_factory is None:
        msg = "Session factory is not initialised. Call init_db() during application startup."
        raise DatabaseNotInitialisedError(msg)
    return _session_factory


async def init_db(database_url: str | None = None) -> None:
    """Create the async engine and session factory.

    Should be called once during application startup (e.g. in a FastAPI
    lifespan handler).

    Args:
        database_url: Override the URL from settings.  Useful for tests that
            substitute an SQLite connection string.
    """
    global _engine, _session_factory  # noqa: PLW0603

    url = database_url or get_settings().DATABASE_URL

    logger.info("database.init", url=url.split("@")[-1])

    _engine = create_async_engine(
        url,
        echo=False,
        pool_pre_ping=True,
        pool_size=5,
        max_overflow=10,
        pool_recycle=3600,
    )

    _session_factory = async_sessionmaker(
        bind=_engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )

    logger.info("database.ready")


async def close_db() -> None:
    """Dispose of the engine connection pool.

    Should be called during application shutdown.
    """
    global _engine, _session_factory  # noqa: PLW0603

    if _engine is not None:
        logger.info("database.closing")
        await _engine.dispose()
        _engine = None
        _session_factory = None
        logger.info("database.closed")


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Yield an async database session for FastAPI dependency injection.

    Usage::

        @router.get("/items")
        async def list_items(db: AsyncSession = Depends(get_db)):
            ...

    The session is committed on success and rolled back on exception.
    """
    factory = _get_session_factory()
    async with factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise

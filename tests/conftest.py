"""Async test fixtures for the ArXiv Research Digest test suite.

Provides an in-memory SQLite database via aiosqlite, overrides the FastAPI
dependency injection to use test sessions, and exposes an async HTTP client
for integration testing.
"""

from __future__ import annotations

import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any
from unittest.mock import patch

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import event
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from arxiv_digest.database import Base

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator


@pytest.fixture(scope="session")
def topics_file(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """Create a temporary topics YAML file for the test session.

    Returns:
        Path to a valid topics YAML configuration file.
    """
    topics_yaml = tmp_path_factory.mktemp("config") / "topics.yaml"
    topics_yaml.write_text(
        "topics:\n"
        "  - id: test_topic\n"
        "    name: Test Topic\n"
        "    description: A topic used exclusively for testing.\n"
        "    arxiv_categories:\n"
        "      - cs.LG\n"
        "    keywords:\n"
        "      - testing\n"
        "    max_papers: 10\n"
        "  - id: another_topic\n"
        "    name: Another Topic\n"
        "    description: A second topic for filter testing.\n"
        "    arxiv_categories:\n"
        "      - cs.CL\n"
        "    keywords:\n"
        "      - language\n"
        "    max_papers: 5\n",
        encoding="utf-8",
    )
    return topics_yaml


def _set_sqlite_pragma(dbapi_conn: object, _connection_record: object) -> None:
    """Enable foreign keys for SQLite connections.

    Args:
        dbapi_conn: The raw DBAPI connection.
        _connection_record: Unused connection record metadata.
    """
    cursor = dbapi_conn.cursor()  # type: ignore[union-attr]
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()


@pytest.fixture
async def async_engine() -> AsyncGenerator[AsyncEngine, None]:
    """Create an async SQLite engine backed by aiosqlite.

    Creates all tables on startup and disposes the engine on teardown.

    Yields:
        A fully initialised :class:`AsyncEngine`.
    """
    engine = create_async_engine(
        "sqlite+aiosqlite://",
        echo=False,
        connect_args={"check_same_thread": False},
    )

    event.listen(engine.sync_engine, "connect", _set_sqlite_pragma)

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    yield engine

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)

    await engine.dispose()


@pytest.fixture
async def db_session(
    async_engine: AsyncEngine,
) -> AsyncGenerator[AsyncSession, None]:
    """Provide a transactional async database session for each test.

    Each test runs inside a transaction that is rolled back after completion,
    ensuring test isolation without the overhead of table recreation.

    Args:
        async_engine: The test SQLite engine.

    Yields:
        An :class:`AsyncSession` bound to the test engine.
    """
    session_factory = async_sessionmaker(
        bind=async_engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )

    async with session_factory() as session:
        yield session
        await session.rollback()


@pytest.fixture
async def app(
    db_session: AsyncSession,
    topics_file: Path,
) -> AsyncGenerator[Any, None]:
    """Create the FastAPI application with test dependency overrides.

    Overrides the database session dependency and application settings to use
    the test database and a known API key.

    Args:
        db_session: The transactional test database session.
        topics_file: Path to the test topics YAML file.

    Yields:
        A configured :class:`FastAPI` application instance.
    """
    from arxiv_digest.api.deps import get_db_session
    from arxiv_digest.config import Settings, get_settings

    test_settings = Settings(
        DATABASE_URL="sqlite+aiosqlite://",
        API_KEY="test-api-key-12345",  # type: ignore[arg-type]
        TOPICS_FILE=topics_file,
        LOG_LEVEL="DEBUG",
        CACHE_DIR=Path("/tmp/arxiv-test-cache"),
    )

    get_settings.cache_clear()

    async def _override_db() -> AsyncGenerator[AsyncSession, None]:
        yield db_session

    with (
        patch("arxiv_digest.config.get_settings", return_value=test_settings),
        patch("arxiv_digest.api.deps.get_settings", return_value=test_settings),
        patch("arxiv_digest.api.v1.health.get_settings", return_value=test_settings),
        patch("arxiv_digest.schemas.topic.get_settings", return_value=test_settings),
    ):
        from arxiv_digest.main import create_app

        test_app = create_app()
        test_app.dependency_overrides[get_db_session] = _override_db
        yield test_app
        test_app.dependency_overrides.clear()

    get_settings.cache_clear()


@pytest.fixture
async def async_client(app: Any) -> AsyncGenerator[AsyncClient, None]:
    """Provide an async HTTP client wired to the test FastAPI application.

    Args:
        app: The test FastAPI application with dependency overrides.

    Yields:
        An :class:`httpx.AsyncClient` for making requests to the test app.
    """
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        yield client


def make_paper_data(
    *,
    arxiv_id: str = "2301.00001",
    title: str = "Test Paper Title",
    topic_id: str = "test_topic",
    digest_id: str | None = None,
    relevance_score: float | None = 0.85,
) -> dict[str, object]:
    """Build a dictionary of paper attributes suitable for ORM model creation.

    Args:
        arxiv_id: The ArXiv identifier for the paper.
        title: Paper title.
        topic_id: Research topic identifier.
        digest_id: Optional parent digest UUID.
        relevance_score: Relevance score between 0.0 and 1.0.

    Returns:
        A dictionary of keyword arguments for :class:`Paper` construction.
    """
    return {
        "arxiv_id": arxiv_id,
        "title": title,
        "authors": [{"name": "Test Author"}],
        "abstract": "This is a test abstract for unit testing purposes.",
        "published_date": datetime.date(2024, 1, 15),
        "categories": ["cs.LG"],
        "pdf_url": f"https://arxiv.org/pdf/{arxiv_id}",
        "relevance_score": relevance_score,
        "topic_id": topic_id,
        "digest_id": digest_id,
    }

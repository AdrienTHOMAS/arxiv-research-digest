"""Tests for the web UI routes."""

from __future__ import annotations

import datetime
from typing import TYPE_CHECKING

from arxiv_digest.models.digest import Digest
from arxiv_digest.models.paper import Paper
from tests.conftest import make_paper_data

if TYPE_CHECKING:
    from httpx import AsyncClient
    from sqlalchemy.ext.asyncio import AsyncSession


async def test_index_page_empty(async_client: AsyncClient) -> None:
    """GET / returns the HTML dashboard with no digests."""
    response = await async_client.get("/", follow_redirects=True)

    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]
    assert "ArXiv Research Digest" in response.text


async def test_index_page_with_digests(
    async_client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    """GET / shows digest cards when digests exist."""
    digest = Digest(
        topic_id="test_topic",
        run_date=datetime.date(2024, 1, 15),
        status="complete",
        paper_count=3,
    )
    db_session.add(digest)
    await db_session.commit()

    response = await async_client.get("/")
    assert response.status_code == 200
    assert "test_topic" in response.text
    assert "complete" in response.text


async def test_digest_detail_page(
    async_client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    """GET /digest/{id} renders digest detail with papers."""
    digest = Digest(
        topic_id="test_topic",
        run_date=datetime.date(2024, 1, 15),
        status="complete",
        paper_count=1,
        summary="Test summary content",
    )
    db_session.add(digest)
    await db_session.flush()

    data = make_paper_data(
        arxiv_id="2401.99001",
        title="UI Test Paper",
        digest_id=digest.id,
    )
    paper = Paper(**data)
    db_session.add(paper)
    await db_session.commit()

    response = await async_client.get(f"/digest/{digest.id}")
    assert response.status_code == 200
    assert "UI Test Paper" in response.text
    assert "Test summary content" in response.text


async def test_digest_detail_not_found(async_client: AsyncClient) -> None:
    """GET /digest/nonexistent returns 404."""
    response = await async_client.get("/digest/nonexistent-id")
    assert response.status_code == 404


async def test_papers_page_empty(async_client: AsyncClient) -> None:
    """GET /papers renders the papers table page."""
    response = await async_client.get("/papers")
    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]
    assert "Papers" in response.text


async def test_papers_page_with_data(
    async_client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    """GET /papers shows papers in the table."""
    data = make_paper_data(
        arxiv_id="2401.99002",
        title="Papers Page Test",
    )
    paper = Paper(**data)
    db_session.add(paper)
    await db_session.commit()

    response = await async_client.get("/papers")
    assert response.status_code == 200
    assert "Papers Page Test" in response.text


async def test_papers_page_filters(
    async_client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    """GET /papers with filters applies them correctly."""
    data = make_paper_data(
        arxiv_id="2401.99003",
        title="High Score Paper",
        relevance_score=0.95,
    )
    paper = Paper(**data)
    db_session.add(paper)
    await db_session.commit()

    response = await async_client.get("/papers?min_score=0.9")
    assert response.status_code == 200
    assert "High Score Paper" in response.text

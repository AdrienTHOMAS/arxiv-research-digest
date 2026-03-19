"""Tests for the papers endpoints."""

from __future__ import annotations

from typing import TYPE_CHECKING

from arxiv_digest.models.paper import Paper
from tests.conftest import make_paper_data

if TYPE_CHECKING:
    from httpx import AsyncClient
    from sqlalchemy.ext.asyncio import AsyncSession


async def _insert_paper(
    db_session: AsyncSession,
    *,
    arxiv_id: str = "2301.00001",
    title: str = "Test Paper Title",
    topic_id: str = "test_topic",
    digest_id: str | None = None,
    relevance_score: float | None = 0.85,
) -> Paper:
    """Insert a paper record into the test database and return it.

    Args:
        db_session: The test database session.
        arxiv_id: The ArXiv identifier for the paper.
        title: Paper title.
        topic_id: Research topic identifier.
        digest_id: Optional parent digest UUID.
        relevance_score: Relevance score between 0.0 and 1.0.

    Returns:
        The persisted :class:`Paper` instance.
    """
    data = make_paper_data(
        arxiv_id=arxiv_id,
        title=title,
        topic_id=topic_id,
        digest_id=digest_id,
        relevance_score=relevance_score,
    )
    paper = Paper(**data)
    db_session.add(paper)
    await db_session.flush()
    return paper


async def test_list_papers(
    async_client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    """GET /api/v1/papers returns a paginated response with papers."""
    await _insert_paper(db_session, arxiv_id="2401.00001", title="First Paper")
    await _insert_paper(db_session, arxiv_id="2401.00002", title="Second Paper")
    await db_session.commit()

    response = await async_client.get("/api/v1/papers")

    assert response.status_code == 200

    body = response.json()
    assert "items" in body
    assert "total" in body
    assert "page" in body
    assert "page_size" in body
    assert "pages" in body
    assert body["total"] >= 2
    assert isinstance(body["items"], list)
    assert len(body["items"]) >= 2

    paper_item = body["items"][0]
    assert "id" in paper_item
    assert "arxiv_id" in paper_item
    assert "title" in paper_item


async def test_list_papers_empty(async_client: AsyncClient) -> None:
    """GET /api/v1/papers returns an empty list when no papers exist."""
    response = await async_client.get("/api/v1/papers")

    assert response.status_code == 200

    body = response.json()
    assert body["total"] == 0
    assert body["items"] == []
    assert body["pages"] == 0


async def test_get_paper_not_found(async_client: AsyncClient) -> None:
    """GET /api/v1/papers/nonexistent returns 404."""
    response = await async_client.get("/api/v1/papers/nonexistent-paper-id")

    assert response.status_code == 404

    body = response.json()
    assert "detail" in body


async def test_list_papers_filter_by_topic(
    async_client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    """GET /api/v1/papers?topic_id=... filters papers by topic."""
    await _insert_paper(
        db_session,
        arxiv_id="2401.10001",
        title="ML Paper",
        topic_id="ml_topic",
    )
    await _insert_paper(
        db_session,
        arxiv_id="2401.10002",
        title="NLP Paper",
        topic_id="nlp_topic",
    )
    await db_session.commit()

    response = await async_client.get("/api/v1/papers?topic_id=ml_topic")

    assert response.status_code == 200

    body = response.json()
    assert body["total"] >= 1
    # Verify the filter reduced results — both papers were inserted but only one matches
    for item in body["items"]:
        assert item["title"] == "ML Paper"


async def test_get_paper_by_id(
    async_client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    """GET /api/v1/papers/{id} returns the correct paper."""
    paper = await _insert_paper(
        db_session,
        arxiv_id="2401.20001",
        title="Specific Paper",
    )
    await db_session.commit()

    response = await async_client.get(f"/api/v1/papers/{paper.id}")

    assert response.status_code == 200

    body = response.json()
    assert body["id"] == paper.id
    assert body["arxiv_id"] == "2401.20001"
    assert body["title"] == "Specific Paper"
    assert "abstract" in body
    assert "authors" in body
    assert "published_date" in body
    assert "categories" in body
    assert isinstance(body["categories"], list)


async def test_list_papers_pagination(
    async_client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    """GET /api/v1/papers with page_size limits results appropriately."""
    for i in range(5):
        await _insert_paper(
            db_session,
            arxiv_id=f"2401.3000{i}",
            title=f"Paginated Paper {i}",
        )
    await db_session.commit()

    response = await async_client.get("/api/v1/papers?page=1&page_size=2")

    assert response.status_code == 200

    body = response.json()
    assert body["page"] == 1
    assert body["page_size"] == 2
    assert len(body["items"]) <= 2
    assert body["total"] >= 5

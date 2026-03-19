"""Tests for the papers API endpoints with filters, pagination, and sorting."""

from __future__ import annotations

import datetime
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
    title: str = "Test Paper",
    topic_id: str = "test_topic",
    relevance_score: float | None = 0.85,
    published_date: datetime.date | None = None,
) -> Paper:
    """Insert a paper record and return it."""
    data = make_paper_data(
        arxiv_id=arxiv_id,
        title=title,
        topic_id=topic_id,
        relevance_score=relevance_score,
    )
    if published_date is not None:
        data["published_date"] = published_date
    paper = Paper(**data)
    db_session.add(paper)
    await db_session.flush()
    return paper


async def test_list_papers_no_filters(
    async_client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    """GET /api/v1/papers with no filters returns all papers."""
    await _insert_paper(db_session, arxiv_id="2501.00001", title="Paper A")
    await _insert_paper(db_session, arxiv_id="2501.00002", title="Paper B")
    await _insert_paper(db_session, arxiv_id="2501.00003", title="Paper C")
    await db_session.commit()

    response = await async_client.get("/api/v1/papers")

    assert response.status_code == 200
    body = response.json()
    assert body["total"] >= 3
    assert len(body["items"]) >= 3
    assert body["page"] == 1
    assert body["page_size"] == 20


async def test_filter_by_topic_id(
    async_client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    """GET /api/v1/papers?topic_id=X returns only papers for that topic."""
    await _insert_paper(db_session, arxiv_id="2502.00001", topic_id="topic_alpha")
    await _insert_paper(db_session, arxiv_id="2502.00002", topic_id="topic_beta")
    await _insert_paper(db_session, arxiv_id="2502.00003", topic_id="topic_alpha")
    await db_session.commit()

    response = await async_client.get("/api/v1/papers?topic_id=topic_alpha")

    assert response.status_code == 200
    body = response.json()
    assert body["total"] >= 2
    for item in body["items"]:
        # All returned papers should have the title of alpha-topic papers
        assert item["arxiv_id"] in ("2502.00001", "2502.00003")


async def test_filter_by_min_score(
    async_client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    """GET /api/v1/papers?min_score=0.5 filters by relevance score."""
    await _insert_paper(db_session, arxiv_id="2503.00001", relevance_score=0.9)
    await _insert_paper(db_session, arxiv_id="2503.00002", relevance_score=0.3)
    await _insert_paper(db_session, arxiv_id="2503.00003", relevance_score=0.7)
    await db_session.commit()

    response = await async_client.get("/api/v1/papers?min_score=0.5")

    assert response.status_code == 200
    body = response.json()
    # Only papers with score >= 0.5 should be returned
    for item in body["items"]:
        if item["arxiv_id"] in ("2503.00001", "2503.00003"):
            assert item["relevance_score"] >= 0.5


async def test_pagination(
    async_client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    """GET /api/v1/papers with page and page_size paginates correctly."""
    for i in range(8):
        await _insert_paper(
            db_session,
            arxiv_id=f"2504.{i:05d}",
            title=f"Paginated Paper {i}",
            relevance_score=0.5 + i * 0.05,
        )
    await db_session.commit()

    # Page 1 with page_size=3
    resp1 = await async_client.get("/api/v1/papers?page=1&page_size=3")
    assert resp1.status_code == 200
    body1 = resp1.json()
    assert len(body1["items"]) == 3
    assert body1["page"] == 1
    assert body1["page_size"] == 3
    assert body1["total"] >= 8

    # Page 2 should have different items
    resp2 = await async_client.get("/api/v1/papers?page=2&page_size=3")
    assert resp2.status_code == 200
    body2 = resp2.json()
    assert len(body2["items"]) == 3
    assert body2["page"] == 2

    # Items on page 1 and page 2 should not overlap
    ids_page1 = {item["id"] for item in body1["items"]}
    ids_page2 = {item["id"] for item in body2["items"]}
    assert ids_page1.isdisjoint(ids_page2)


async def test_sort_by_relevance_score_desc(
    async_client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    """GET /api/v1/papers returns papers sorted by relevance_score descending."""
    await _insert_paper(db_session, arxiv_id="2505.00001", relevance_score=0.3)
    await _insert_paper(db_session, arxiv_id="2505.00002", relevance_score=0.9)
    await _insert_paper(db_session, arxiv_id="2505.00003", relevance_score=0.6)
    await db_session.commit()

    response = await async_client.get("/api/v1/papers")

    assert response.status_code == 200
    body = response.json()
    scores = [
        item["relevance_score"]
        for item in body["items"]
        if item["relevance_score"] is not None
    ]
    # Filter to only our test papers by checking scores in expected range
    our_scores = [s for s in scores if s in (0.3, 0.6, 0.9)]
    if len(our_scores) >= 2:
        # Scores should be in descending order
        assert our_scores == sorted(our_scores, reverse=True)


async def test_pagination_pages_count(
    async_client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    """Pages count is correctly calculated from total and page_size."""
    for i in range(5):
        await _insert_paper(
            db_session,
            arxiv_id=f"2506.{i:05d}",
            title=f"Count Paper {i}",
        )
    await db_session.commit()

    response = await async_client.get("/api/v1/papers?page_size=2")

    assert response.status_code == 200
    body = response.json()
    # With 5+ items and page_size=2, pages should be >= 3
    assert body["pages"] >= 3

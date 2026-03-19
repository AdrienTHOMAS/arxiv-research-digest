"""Tests for the digests endpoints."""

from __future__ import annotations

import datetime
from typing import TYPE_CHECKING

from arxiv_digest.models.digest import Digest

if TYPE_CHECKING:
    from httpx import AsyncClient
    from sqlalchemy.ext.asyncio import AsyncSession


async def _seed_digest(
    db_session: AsyncSession,
    *,
    topic_id: str = "test_topic",
    run_date: datetime.date | None = None,
    status: str = "pending",
) -> Digest:
    """Insert a digest record into the test database and return it.

    Args:
        db_session: The test database session.
        topic_id: Research topic identifier.
        run_date: Date for the digest; defaults to 2024-01-15.
        status: Digest processing status.

    Returns:
        The persisted :class:`Digest` instance.
    """
    date = run_date or datetime.date(2024, 1, 15)
    digest = Digest(
        topic_id=topic_id,
        run_date=date,
        status=status,
        paper_count=0,
    )
    db_session.add(digest)
    await db_session.flush()
    return digest


async def test_create_digest(async_client: AsyncClient) -> None:
    """POST /api/v1/digests with a valid API key creates a pending digest."""
    payload = {
        "topic_id": "test_topic",
        "run_date": "2024-06-01",
    }
    response = await async_client.post(
        "/api/v1/digests",
        json=payload,
        headers={"X-API-Key": "test-api-key-12345"},
    )

    assert response.status_code == 201

    body = response.json()
    assert body["topic_id"] == "test_topic"
    assert body["run_date"] == "2024-06-01"
    assert body["status"] == "pending"
    assert body["paper_count"] == 0
    assert "id" in body
    assert "papers" in body
    assert isinstance(body["papers"], list)


async def test_create_digest_no_auth(async_client: AsyncClient) -> None:
    """POST /api/v1/digests without an API key returns 401."""
    payload = {
        "topic_id": "test_topic",
        "run_date": "2024-06-02",
    }
    response = await async_client.post(
        "/api/v1/digests",
        json=payload,
    )

    assert response.status_code == 401


async def test_list_digests(
    async_client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    """GET /api/v1/digests returns a paginated response."""
    await _seed_digest(db_session, run_date=datetime.date(2024, 3, 1))
    await _seed_digest(db_session, run_date=datetime.date(2024, 3, 2))
    await db_session.commit()

    response = await async_client.get("/api/v1/digests")

    assert response.status_code == 200

    body = response.json()
    assert "items" in body
    assert "total" in body
    assert "page" in body
    assert "page_size" in body
    assert "pages" in body
    assert body["total"] >= 2
    assert isinstance(body["items"], list)


async def test_list_digests_filter_by_topic(
    async_client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    """GET /api/v1/digests?topic_id=... filters results by topic."""
    await _seed_digest(
        db_session,
        topic_id="filter_topic",
        run_date=datetime.date(2024, 4, 1),
    )
    await _seed_digest(
        db_session,
        topic_id="other_topic",
        run_date=datetime.date(2024, 4, 2),
    )
    await db_session.commit()

    response = await async_client.get("/api/v1/digests?topic_id=filter_topic")

    assert response.status_code == 200

    body = response.json()
    assert body["total"] >= 1
    for item in body["items"]:
        assert item["topic_id"] == "filter_topic"


async def test_get_digest(
    async_client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    """GET /api/v1/digests/{id} returns the digest with a papers list."""
    digest = await _seed_digest(db_session, run_date=datetime.date(2024, 5, 1))
    await db_session.commit()

    response = await async_client.get(f"/api/v1/digests/{digest.id}")

    assert response.status_code == 200

    body = response.json()
    assert body["id"] == digest.id
    assert body["topic_id"] == "test_topic"
    assert "papers" in body
    assert isinstance(body["papers"], list)


async def test_get_digest_not_found(async_client: AsyncClient) -> None:
    """GET /api/v1/digests/nonexistent returns 404."""
    response = await async_client.get("/api/v1/digests/nonexistent-id-12345")

    assert response.status_code == 404

    body = response.json()
    assert "detail" in body

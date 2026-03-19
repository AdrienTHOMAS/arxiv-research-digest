"""Tests for the topics endpoints."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from httpx import AsyncClient


async def test_list_topics(async_client: AsyncClient) -> None:
    """GET /api/v1/topics returns a list of configured topics."""
    response = await async_client.get("/api/v1/topics")

    assert response.status_code == 200

    body = response.json()
    assert isinstance(body, list)
    assert len(body) >= 1

    topic = body[0]
    assert "id" in topic
    assert "name" in topic
    assert "description" in topic
    assert "arxiv_categories" in topic
    assert "keywords" in topic
    assert "max_papers" in topic


async def test_get_topic(async_client: AsyncClient) -> None:
    """GET /api/v1/topics/{id} returns the correct topic."""
    response = await async_client.get("/api/v1/topics/test_topic")

    assert response.status_code == 200

    body = response.json()
    assert body["id"] == "test_topic"
    assert body["name"] == "Test Topic"
    assert "cs.LG" in body["arxiv_categories"]


async def test_get_topic_not_found(async_client: AsyncClient) -> None:
    """GET /api/v1/topics/nonexistent returns 404."""
    response = await async_client.get("/api/v1/topics/nonexistent")

    assert response.status_code == 404

    body = response.json()
    assert "detail" in body

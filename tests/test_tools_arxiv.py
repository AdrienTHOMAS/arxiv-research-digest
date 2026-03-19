"""Tests for the ArXiv paper fetching tool."""

from __future__ import annotations

import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import feedparser
import pytest

from arxiv_digest.models.paper import Paper
from arxiv_digest.schemas.topic import TopicSchema
from arxiv_digest.tools.arxiv import fetch_arxiv_papers

# ── Helpers ─────────────────────────────────────────────────────────────


def _make_topic(**overrides: object) -> TopicSchema:
    """Build a TopicSchema with sensible defaults."""
    defaults = {
        "id": "test_topic",
        "name": "Test Topic",
        "description": "A topic for testing.",
        "arxiv_categories": ["cs.LG"],
        "keywords": ["testing"],
        "max_papers": 10,
    }
    return TopicSchema.model_validate({**defaults, **overrides})


def _make_feed_entry(
    *,
    arxiv_id: str = "2401.00001",
    title: str = "Test Paper",
    summary: str = "An abstract about testing.",
    published: str = "2024-01-15T00:00:00Z",
) -> feedparser.FeedParserDict:
    """Build a feedparser-style entry that supports both attribute and dict access."""
    entry = feedparser.FeedParserDict()
    entry["id"] = f"http://arxiv.org/abs/{arxiv_id}v1"
    entry["title"] = title
    entry["summary"] = summary
    entry["published"] = published
    entry["authors"] = [{"name": "Author One"}]
    entry["tags"] = [{"term": "cs.LG"}]
    entry["links"] = [
        {"href": f"http://arxiv.org/abs/{arxiv_id}", "type": "text/html"},
        {"href": f"http://arxiv.org/pdf/{arxiv_id}", "type": "application/pdf"},
    ]
    return entry


# ── Fixtures ────────────────────────────────────────────────────────────


@pytest.fixture
def mock_feed_response() -> MagicMock:
    """Return a feedparser-style result with two entries dated today."""
    feed = MagicMock()
    today = datetime.datetime.now(tz=datetime.UTC).date()
    iso_today = today.isoformat() + "T00:00:00Z"

    feed.entries = [
        _make_feed_entry(arxiv_id="2401.00001", title="Paper Alpha", published=iso_today),
        _make_feed_entry(arxiv_id="2401.00002", title="Paper Beta", published=iso_today),
    ]
    feed.bozo = False
    feed.bozo_exception = None
    return feed


@pytest.fixture
def mock_db_session() -> AsyncMock:
    """Return a mock AsyncSession with common stubs."""
    session = AsyncMock()

    # Default: no existing papers in DB
    execute_result = MagicMock()
    execute_result.all.return_value = []
    session.execute.return_value = execute_result

    return session


# ── Tests ───────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_fetch_arxiv_papers_success(
    mock_feed_response: MagicMock,
    mock_db_session: AsyncMock,
) -> None:
    """Successfully fetches and creates Paper objects from ArXiv feed."""
    topic = _make_topic()

    with patch(
        "arxiv_digest.tools.arxiv._fetch_feed",
        return_value=mock_feed_response,
    ):
        papers = await fetch_arxiv_papers(topic=topic, db=mock_db_session, days_back=3)

    assert len(papers) == 2
    assert all(isinstance(p, Paper) for p in papers)
    assert papers[0].arxiv_id == "2401.00001"
    assert papers[1].arxiv_id == "2401.00002"
    assert papers[0].topic_id == "test_topic"


@pytest.mark.asyncio
async def test_fetch_arxiv_papers_dedup(
    mock_feed_response: MagicMock,
    mock_db_session: AsyncMock,
) -> None:
    """Papers already in the database are skipped during deduplication."""
    topic = _make_topic()

    # Simulate "2401.00001" already exists in DB
    execute_result = MagicMock()
    execute_result.all.return_value = [("2401.00001",)]
    mock_db_session.execute.return_value = execute_result

    with patch(
        "arxiv_digest.tools.arxiv._fetch_feed",
        return_value=mock_feed_response,
    ):
        papers = await fetch_arxiv_papers(topic=topic, db=mock_db_session, days_back=3)

    assert len(papers) == 1
    assert papers[0].arxiv_id == "2401.00002"


@pytest.mark.asyncio
async def test_fetch_arxiv_papers_network_error(
    mock_db_session: AsyncMock,
) -> None:
    """Network errors are handled gracefully, returning an empty list."""
    topic = _make_topic()

    with patch(
        "arxiv_digest.tools.arxiv._fetch_feed",
        side_effect=Exception("Network timeout"),
    ):
        papers = await fetch_arxiv_papers(topic=topic, db=mock_db_session, days_back=3)

    assert papers == []


@pytest.mark.asyncio
async def test_fetch_arxiv_papers_empty_results(
    mock_db_session: AsyncMock,
) -> None:
    """An empty ArXiv feed returns an empty list of papers."""
    topic = _make_topic()

    empty_feed = MagicMock()
    empty_feed.entries = []
    empty_feed.bozo = False
    empty_feed.bozo_exception = None

    with patch(
        "arxiv_digest.tools.arxiv._fetch_feed",
        return_value=empty_feed,
    ):
        papers = await fetch_arxiv_papers(topic=topic, db=mock_db_session, days_back=3)

    assert papers == []

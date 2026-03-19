"""Fetch papers from the ArXiv API and persist new entries to the database."""

from __future__ import annotations

import datetime
import urllib.parse
from typing import TYPE_CHECKING

import feedparser
import structlog
from sqlalchemy import select
from tenacity import retry, stop_after_attempt, wait_exponential

from arxiv_digest.models.paper import Paper

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

    from arxiv_digest.schemas.topic import TopicSchema

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)

_ARXIV_API_URL = "http://export.arxiv.org/api/query"
_MAX_RESULTS = 200


def _build_search_query(topic: TopicSchema) -> str:
    """Build an ArXiv API ``search_query`` string from a topic definition.

    Combines category filters (OR) with keyword filters (OR) using AND.

    Args:
        topic: The topic containing categories and keywords.

    Returns:
        An ArXiv API search query string.
    """
    cat_parts = [f"cat:{cat}" for cat in topic.arxiv_categories]
    cat_query = " OR ".join(cat_parts)

    if topic.keywords:
        kw_parts = [f'all:"{kw}"' for kw in topic.keywords]
        kw_query = " OR ".join(kw_parts)
        return f"({cat_query}) AND ({kw_query})"

    return cat_query


def _parse_arxiv_id(entry_id: str) -> str:
    """Extract the bare ArXiv ID from a full Atom entry URL.

    Args:
        entry_id: The ``id`` field from a feedparser entry
            (e.g. ``http://arxiv.org/abs/2301.12345v1``).

    Returns:
        The short ArXiv identifier without version suffix
        (e.g. ``2301.12345``).
    """
    # entry_id looks like http://arxiv.org/abs/2301.12345v1
    raw = entry_id.rsplit("/", maxsplit=1)[-1]
    # Strip version suffix (v1, v2, etc.)
    if "v" in raw:
        raw = raw[: raw.rfind("v")]
    return raw


def _parse_entry(entry: object, topic_id: str) -> Paper:
    """Convert a single feedparser entry into a :class:`Paper` ORM instance.

    Args:
        entry: A feedparser entry object.
        topic_id: The topic this paper was fetched for.

    Returns:
        An unsaved :class:`Paper` instance.
    """
    arxiv_id = _parse_arxiv_id(entry.id)  # type: ignore[attr-defined]
    published = datetime.datetime.fromisoformat(
        entry.published.replace("Z", "+00:00"),  # type: ignore[attr-defined]
    ).date()

    authors = [{"name": a.get("name", "")} for a in entry.get("authors", [])]  # type: ignore[attr-defined]
    categories = [t["term"] for t in entry.get("tags", []) if "term" in t]  # type: ignore[attr-defined]

    pdf_url = ""
    for link in entry.get("links", []):  # type: ignore[attr-defined]
        if link.get("type") == "application/pdf":
            pdf_url = link["href"]
            break
    if not pdf_url:
        pdf_url = f"https://arxiv.org/pdf/{arxiv_id}"

    return Paper(
        arxiv_id=arxiv_id,
        title=entry.title.strip(),  # type: ignore[attr-defined]
        authors=authors,
        abstract=entry.summary.strip(),  # type: ignore[attr-defined]
        published_date=published,
        categories=categories,
        pdf_url=pdf_url,
        topic_id=topic_id,
    )


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=10),
    reraise=True,
)
def _fetch_feed(query: str, max_results: int) -> feedparser.FeedParserDict:
    """Fetch and parse an ArXiv Atom feed with automatic retry.

    Args:
        query: The ``search_query`` parameter value.
        max_results: Maximum number of results to request.

    Returns:
        The parsed feed.

    Raises:
        RuntimeError: If the feed contains a ``bozo_exception``.
    """
    params = urllib.parse.urlencode({
        "search_query": query,
        "start": 0,
        "max_results": max_results,
        "sortBy": "submittedDate",
        "sortOrder": "descending",
    })
    url = f"{_ARXIV_API_URL}?{params}"
    feed = feedparser.parse(url)

    if feed.bozo and feed.bozo_exception:
        msg = f"Feed parse error: {feed.bozo_exception}"
        raise RuntimeError(msg)

    return feed


async def fetch_arxiv_papers(
    topic: TopicSchema,
    db: AsyncSession,
    *,
    days_back: int = 3,
) -> list[Paper]:
    """Fetch recent ArXiv papers for a topic and persist new ones.

    Queries the ArXiv API using the topic's categories and keywords, filters
    by publication date, deduplicates against existing database records, and
    inserts new papers.

    Args:
        topic: The research topic definition.
        db: An active async database session.
        days_back: Number of days to look back for new papers.

    Returns:
        A list of newly inserted :class:`Paper` instances.
    """
    log = logger.bind(topic_id=topic.id, days_back=days_back)
    log.info("arxiv.fetch_start")

    query = _build_search_query(topic)
    max_results = min(topic.max_papers * 3, _MAX_RESULTS)

    log.info("arxiv.query_built", query=query, max_results=max_results)

    try:
        feed = _fetch_feed(query, max_results)
    except Exception:
        log.exception("arxiv.fetch_failed")
        return []

    cutoff = datetime.datetime.now(tz=datetime.UTC).date() - datetime.timedelta(days=days_back)
    entries = feed.entries
    log.info("arxiv.raw_entries", count=len(entries))

    # Parse and filter by date
    candidates: list[Paper] = []
    for entry in entries:
        paper = _parse_entry(entry, topic.id)
        if paper.published_date >= cutoff:
            candidates.append(paper)

    log.info("arxiv.date_filtered", count=len(candidates))

    if not candidates:
        log.info("arxiv.no_new_papers")
        return []

    # Deduplicate against existing papers in DB
    candidate_ids = [p.arxiv_id for p in candidates]
    stmt = select(Paper.arxiv_id).where(Paper.arxiv_id.in_(candidate_ids))
    result = await db.execute(stmt)
    existing_ids: set[str] = {row[0] for row in result.all()}

    new_papers = [p for p in candidates if p.arxiv_id not in existing_ids]
    log.info("arxiv.deduplicated", new=len(new_papers), existing=len(existing_ids))

    if not new_papers:
        log.info("arxiv.all_duplicates")
        return []

    # Respect max_papers limit
    new_papers = new_papers[: topic.max_papers]

    for paper in new_papers:
        db.add(paper)
    await db.flush()

    log.info("arxiv.fetch_complete", papers_added=len(new_papers))
    return new_papers

"""Fetch detailed metadata for a single ArXiv paper."""

from __future__ import annotations

import datetime
from typing import TYPE_CHECKING

import feedparser
import structlog
from sqlalchemy import select

from arxiv_digest.models.paper import Paper
from arxiv_digest.tools.semantic_scholar import search_semantic_scholar

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)

_ARXIV_API_URL = "http://export.arxiv.org/api/query"


def _paper_to_dict(paper: Paper) -> dict[str, object]:
    """Convert a :class:`Paper` ORM instance to a metadata dictionary.

    Args:
        paper: The paper to convert.

    Returns:
        A dictionary of paper metadata fields.
    """
    return {
        "arxiv_id": paper.arxiv_id,
        "title": paper.title,
        "authors": paper.authors,
        "abstract": paper.abstract,
        "categories": paper.categories,
        "pdf_url": paper.pdf_url,
        "published_date": str(paper.published_date),
    }


async def fetch_paper_details(
    arxiv_id: str,
    db: AsyncSession,
) -> dict[str, object]:
    """Retrieve detailed metadata for a single ArXiv paper.

    Checks the local database first.  If the paper is not found locally it is
    fetched from the ArXiv API.  Citation data from Semantic Scholar is
    appended when available.

    Args:
        arxiv_id: The ArXiv paper identifier (e.g. ``2301.12345``).
        db: An active async database session.

    Returns:
        A dictionary with paper metadata and optional citation counts.
    """
    log = logger.bind(arxiv_id=arxiv_id)
    log.info("paper_details.lookup")

    # Check local DB first
    stmt = select(Paper).where(Paper.arxiv_id == arxiv_id)
    result = await db.execute(stmt)
    paper = result.scalar_one_or_none()

    if paper is not None:
        log.info("paper_details.found_in_db")
        details = _paper_to_dict(paper)
    else:
        log.info("paper_details.fetching_from_arxiv")
        details = await _fetch_from_arxiv(arxiv_id)
        if not details:
            log.warning("paper_details.not_found")
            return {"arxiv_id": arxiv_id, "error": "Paper not found"}

    # Enrich with Semantic Scholar data
    scholar = await search_semantic_scholar(arxiv_id)
    if scholar.get("available"):
        details["citation_count"] = scholar.get("citation_count", 0)
        details["influential_citations"] = scholar.get("influential_citations", 0)
    else:
        details["citation_count"] = None

    return details


async def _fetch_from_arxiv(arxiv_id: str) -> dict[str, object] | None:
    """Fetch a single paper's metadata from the ArXiv API.

    Args:
        arxiv_id: The ArXiv paper identifier.

    Returns:
        A metadata dictionary, or ``None`` if the paper was not found.
    """
    url = f"{_ARXIV_API_URL}?id_list={arxiv_id}"

    try:
        feed = feedparser.parse(url)
    except Exception:
        logger.exception("paper_details.arxiv_fetch_error", arxiv_id=arxiv_id)
        return None

    if not feed.entries:
        return None

    entry = feed.entries[0]
    published = datetime.datetime.fromisoformat(
        entry.published.replace("Z", "+00:00"),
    ).date()
    authors = [{"name": a.get("name", "")} for a in entry.get("authors", [])]
    categories = [t["term"] for t in entry.get("tags", []) if "term" in t]

    pdf_url = ""
    for link in entry.get("links", []):
        if link.get("type") == "application/pdf":
            pdf_url = link["href"]
            break
    if not pdf_url:
        pdf_url = f"https://arxiv.org/pdf/{arxiv_id}"

    return {
        "arxiv_id": arxiv_id,
        "title": entry.title.strip(),
        "authors": authors,
        "abstract": entry.summary.strip(),
        "categories": categories,
        "pdf_url": pdf_url,
        "published_date": str(published),
    }

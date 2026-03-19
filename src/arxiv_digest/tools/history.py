"""Historical trend analysis across past digest runs."""

from __future__ import annotations

import datetime
import re
from collections import Counter
from typing import TYPE_CHECKING

import structlog
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from arxiv_digest.models.digest import Digest

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

    from arxiv_digest.models.paper import Paper

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)

_STOP_WORDS: frozenset[str] = frozenset({
    "a", "an", "and", "are", "as", "at", "be", "by", "for", "from",
    "has", "have", "in", "is", "it", "its", "of", "on", "or", "that",
    "the", "to", "was", "were", "which", "with", "we", "our", "this",
    "can", "using", "via", "based", "through", "between", "their",
    "more", "not", "than", "also", "been", "but", "into", "each",
    "show", "such", "both", "over", "these", "about", "may", "they",
    "most", "where", "when", "will", "how", "what", "does", "do",
    "no", "all", "some", "any", "other", "only", "one", "two",
})

_WORD_PATTERN = re.compile(r"[a-z]{3,}")
_TOP_KEYWORDS = 15


async def compare_with_history(
    topic_id: str,
    db: AsyncSession,
    *,
    lookback_days: int = 30,
) -> dict[str, object]:
    """Analyse recent digest history for a topic to identify trends.

    Loads completed digests within the lookback window, extracts recurring
    authors and trending keywords from their papers, and determines whether
    publishing volume is increasing, stable, or decreasing.

    Args:
        topic_id: The research topic identifier.
        db: An active async database session.
        lookback_days: Number of days of history to consider.

    Returns:
        A dictionary containing trend analysis results.
    """
    log = logger.bind(topic_id=topic_id, lookback_days=lookback_days)
    log.info("history.analysis_start")

    cutoff = datetime.datetime.now(tz=datetime.UTC).date() - datetime.timedelta(days=lookback_days)

    stmt = (
        select(Digest)
        .where(
            Digest.topic_id == topic_id,
            Digest.status == "complete",
            Digest.run_date >= cutoff,
        )
        .options(selectinload(Digest.papers))
        .order_by(Digest.run_date.desc())
    )
    result = await db.execute(stmt)
    digests: list[Digest] = list(result.scalars().all())

    if not digests:
        log.info("history.no_digests")
        return {
            "digests_analyzed": 0,
            "recurring_authors": [],
            "trending_keywords": [],
            "trend_direction": "stable",
            "avg_papers_per_digest": 0.0,
        }

    all_papers: list[Paper] = []
    for digest in digests:
        all_papers.extend(digest.papers)

    recurring_authors = _find_recurring_authors(all_papers)
    trending_keywords = _extract_trending_keywords(all_papers)
    trend_direction = _compute_trend_direction(digests)
    total_papers = sum(d.paper_count for d in digests)
    avg_papers = total_papers / len(digests) if digests else 0.0

    log.info(
        "history.analysis_complete",
        digests=len(digests),
        recurring_authors=len(recurring_authors),
        trending_keywords=len(trending_keywords),
        trend=trend_direction,
    )

    return {
        "digests_analyzed": len(digests),
        "recurring_authors": recurring_authors,
        "trending_keywords": trending_keywords,
        "trend_direction": trend_direction,
        "avg_papers_per_digest": round(avg_papers, 2),
    }


def _find_recurring_authors(papers: list[Paper]) -> list[str]:
    """Identify authors appearing in more than one paper.

    Args:
        papers: A flat list of papers from multiple digests.

    Returns:
        A sorted list of author names that appear at least twice.
    """
    counter: Counter[str] = Counter()
    for paper in papers:
        if paper.authors:
            for author in paper.authors:
                name = author.get("name", "").strip()
                if name:
                    counter[name] += 1

    return sorted(name for name, count in counter.items() if count > 1)


def _extract_trending_keywords(papers: list[Paper]) -> list[str]:
    """Extract the most frequent meaningful words from paper text.

    Processes titles and abstracts, filtering out common stop words and
    short tokens.

    Args:
        papers: A flat list of papers.

    Returns:
        A list of the top keywords ordered by frequency.
    """
    counter: Counter[str] = Counter()
    for paper in papers:
        text = f"{paper.title} {paper.abstract}".lower()
        words = _WORD_PATTERN.findall(text)
        for word in words:
            if word not in _STOP_WORDS:
                counter[word] += 1

    return [word for word, _ in counter.most_common(_TOP_KEYWORDS)]


def _compute_trend_direction(
    digests: list[Digest],
) -> str:
    """Determine whether publishing volume is trending up, down, or stable.

    Splits the digest list (already sorted newest-first) into two halves and
    compares average paper counts.

    Args:
        digests: Digests sorted by run_date descending.

    Returns:
        One of ``"increasing"``, ``"decreasing"``, or ``"stable"``.
    """
    if len(digests) < 2:  # noqa: PLR2004
        return "stable"

    mid = len(digests) // 2
    recent = digests[:mid]
    older = digests[mid:]

    avg_recent = sum(d.paper_count for d in recent) / len(recent)
    avg_older = sum(d.paper_count for d in older) / len(older)

    if avg_older == 0:
        return "increasing" if avg_recent > 0 else "stable"

    change_ratio = (avg_recent - avg_older) / avg_older
    threshold = 0.2

    if change_ratio > threshold:
        return "increasing"
    if change_ratio < -threshold:
        return "decreasing"
    return "stable"

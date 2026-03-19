"""Heuristic impact scoring for ArXiv papers (no LLM calls)."""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

import structlog

if TYPE_CHECKING:
    from arxiv_digest.models.paper import Paper

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)

_NOVELTY_TERMS: list[str] = [
    "novel",
    "first",
    "new approach",
    "state-of-the-art",
    "breakthrough",
    "outperform",
    "surpass",
]

_METHODOLOGY_TERMS: list[str] = [
    "ablation",
    "benchmark",
    "baseline",
    "evaluation",
    "dataset",
    "framework",
    "architecture",
]

_RESULT_TERMS: list[str] = [
    "significant",
    "substantial",
    "dramatic",
    "remarkable",
    "superior",
    "exceed",
]


def _count_term_hits(text: str, terms: list[str]) -> int:
    """Count how many distinct terms from *terms* appear in *text*.

    Uses case-insensitive word-boundary matching so that ``"novel"`` matches
    ``"a novel approach"`` but not ``"novelist"``.

    Args:
        text: The text to search within.
        terms: A list of terms to search for.

    Returns:
        The number of distinct terms found.
    """
    lower = text.lower()
    return sum(
        1
        for term in terms
        if re.search(rf"\b{re.escape(term)}\b", lower)
    )


def score_paper_impact(paper: Paper) -> dict[str, object]:
    """Compute a heuristic impact score for a paper.

    The score ranges from 1 to 10 and is built from five sub-scores:

    * **novelty** (0-3): presence of novelty-indicating terms in the abstract.
    * **methodology** (0-3): presence of methodology-related terms.
    * **results** (0-2): presence of strong-result terms.
    * **collaboration** (0-2): bonus for large author lists.
    * **breadth** (0-1): bonus for cross-category papers.

    Args:
        paper: The :class:`Paper` instance to score.

    Returns:
        A dictionary with ``score``, ``breakdown``, and ``reasoning`` keys.
    """
    log = logger.bind(arxiv_id=paper.arxiv_id)
    abstract = paper.abstract or ""

    novelty = min(_count_term_hits(abstract, _NOVELTY_TERMS), 3)
    methodology = min(_count_term_hits(abstract, _METHODOLOGY_TERMS), 3)
    results = min(_count_term_hits(abstract, _RESULT_TERMS), 2)

    author_count = len(paper.authors) if paper.authors else 0
    if author_count > 10:  # noqa: PLR2004
        collaboration = 2
    elif author_count > 5:  # noqa: PLR2004
        collaboration = 1
    else:
        collaboration = 0

    category_count = len(paper.categories) if paper.categories else 0
    breadth = 1 if category_count > 2 else 0  # noqa: PLR2004

    raw_total = novelty + methodology + results + collaboration + breadth
    score = max(1, min(raw_total, 10))

    breakdown = {
        "novelty": novelty,
        "methodology": methodology,
        "results": results,
        "collaboration": collaboration,
        "breadth": breadth,
    }
    reasoning = _build_reasoning(
        breakdown=breakdown,
        author_count=author_count,
        category_count=category_count,
    )

    log.info("scorer.scored", score=score)

    return {
        "score": score,
        "breakdown": breakdown,
        "reasoning": reasoning,
    }


def _build_reasoning(
    *,
    breakdown: dict[str, int],
    author_count: int,
    category_count: int,
) -> str:
    """Construct a human-readable explanation of the impact score.

    Args:
        breakdown: Mapping of sub-score names to their integer values.
        author_count: Total number of authors.
        category_count: Total number of categories.

    Returns:
        A short explanation string.
    """
    parts: list[str] = []

    if breakdown["novelty"]:
        parts.append(f"Novelty signals detected ({breakdown['novelty']}/3)")
    if breakdown["methodology"]:
        parts.append(f"Methodology terms present ({breakdown['methodology']}/3)")
    if breakdown["results"]:
        parts.append(f"Strong result language ({breakdown['results']}/2)")
    if breakdown["collaboration"]:
        parts.append(
            f"Large collaboration ({author_count} authors, +{breakdown['collaboration']})",
        )
    if breakdown["breadth"]:
        parts.append(f"Cross-disciplinary ({category_count} categories, +1)")

    if not parts:
        parts.append("Baseline score; no strong heuristic signals detected")

    return ". ".join(parts) + "."

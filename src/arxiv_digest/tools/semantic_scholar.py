"""Semantic Scholar API client for citation metadata."""

from __future__ import annotations

import asyncio

import httpx
import structlog

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)

_BASE_URL = "https://api.semanticscholar.org/graph/v1/paper"
_FIELDS = "citationCount,influentialCitationCount,title,year,referenceCount"
_REQUEST_TIMEOUT_SECONDS: float = 10.0
_RATE_LIMIT_DELAY_SECONDS: float = 0.1


async def search_semantic_scholar(arxiv_id: str) -> dict[str, object]:
    """Query Semantic Scholar for citation data of an ArXiv paper.

    Uses the free (unauthenticated) Semantic Scholar API.  Returns a
    graceful fallback dictionary when the paper is not indexed or the
    service is unavailable.

    Args:
        arxiv_id: The ArXiv paper identifier (e.g. ``2301.12345``).

    Returns:
        A dictionary with ``available`` (bool) plus citation fields on
        success, or ``available=False`` and an ``error`` message on failure.
    """
    log = logger.bind(arxiv_id=arxiv_id)
    url = f"{_BASE_URL}/ARXIV:{arxiv_id}?fields={_FIELDS}"

    log.info("semantic_scholar.request", url=url)

    try:
        async with httpx.AsyncClient(timeout=_REQUEST_TIMEOUT_SECONDS) as client:
            response = await client.get(url)

        if response.status_code == 404:  # noqa: PLR2004
            log.info("semantic_scholar.not_found")
            return {"available": False, "error": "Paper not indexed by Semantic Scholar"}

        response.raise_for_status()

    except httpx.TimeoutException:
        log.warning("semantic_scholar.timeout")
        return {"available": False, "error": "Request timed out"}

    except httpx.HTTPStatusError as exc:
        log.warning(
            "semantic_scholar.http_error",
            status_code=exc.response.status_code,
        )
        return {"available": False, "error": f"HTTP {exc.response.status_code}"}

    except httpx.HTTPError as exc:
        log.warning("semantic_scholar.request_error", error=str(exc))
        return {"available": False, "error": str(exc)}

    data = response.json()

    result: dict[str, object] = {
        "available": True,
        "citation_count": data.get("citationCount", 0),
        "influential_citations": data.get("influentialCitationCount", 0),
        "reference_count": data.get("referenceCount", 0),
    }

    log.info(
        "semantic_scholar.success",
        citation_count=result["citation_count"],
    )

    # Small delay to respect rate limits (100 req / 5 min)
    await asyncio.sleep(_RATE_LIMIT_DELAY_SECONDS)

    return result

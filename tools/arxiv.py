"""ArXiv paper fetching tool.

Queries the ArXiv API for recent papers matching a search query,
filters by date range and categories, and returns structured metadata.
"""

import logging
from datetime import datetime, timedelta, timezone
from typing import Any

import feedparser
import requests

logger = logging.getLogger(__name__)

ARXIV_API: str = "http://export.arxiv.org/api/query"


def fetch_arxiv_papers(
    query: str,
    days_back: int = 7,
    max_results: int = 30,
    categories: list[str] | None = None,
) -> dict[str, Any]:
    """Fetch recent papers from ArXiv matching a query and category filters.

    Args:
        query: Search query string (e.g., "large language models").
        days_back: Number of days to look back from today.
        max_results: Maximum number of papers to return.
        categories: ArXiv category codes to filter by (e.g., ["cs.AI", "cs.LG"]).
            Defaults to ["cs.AI", "cs.LG", "cs.CL"].

    Returns:
        Dictionary with keys: query, total_found, date_range, papers.
        Each paper has: id, title, abstract, authors, published, url, pdf_url, categories.
    """
    if categories is None:
        categories = ["cs.AI", "cs.LG", "cs.CL"]

    cutoff_date = datetime.now(tz=timezone.utc) - timedelta(days=days_back)
    date_range = f"{cutoff_date.strftime('%Y-%m-%d')} to {datetime.now(tz=timezone.utc).strftime('%Y-%m-%d')}"

    cat_filter = " OR ".join(f"cat:{cat}" for cat in categories)
    search_query = f"({query}) AND ({cat_filter})"

    params: dict[str, Any] = {
        "search_query": search_query,
        "start": 0,
        "max_results": max_results * 2,  # fetch extra to account for date filtering
        "sortBy": "submittedDate",
        "sortOrder": "descending",
    }

    try:
        response = requests.get(ARXIV_API, params=params, timeout=30)
        response.raise_for_status()
    except requests.ConnectionError:
        logger.error("Failed to connect to ArXiv API — check network connectivity.")
        return {
            "query": query,
            "total_found": 0,
            "date_range": date_range,
            "papers": [],
            "error": "Network connection failed. Unable to reach ArXiv API.",
        }
    except requests.Timeout:
        logger.error("ArXiv API request timed out after 30 seconds.")
        return {
            "query": query,
            "total_found": 0,
            "date_range": date_range,
            "papers": [],
            "error": "Request timed out. ArXiv API may be experiencing high load.",
        }
    except requests.HTTPError as exc:
        logger.error("ArXiv API returned HTTP %s", exc.response.status_code)
        return {
            "query": query,
            "total_found": 0,
            "date_range": date_range,
            "papers": [],
            "error": f"ArXiv API returned HTTP {exc.response.status_code}.",
        }

    feed = feedparser.parse(response.text)
    papers: list[dict[str, Any]] = []

    for entry in feed.entries:
        published_str = entry.get("published", "")
        try:
            published_dt = datetime.fromisoformat(published_str.replace("Z", "+00:00"))
        except (ValueError, AttributeError):
            logger.warning("Skipping entry with unparseable date: %s", published_str)
            continue

        if published_dt < cutoff_date:
            continue

        arxiv_id = entry.get("id", "").split("/abs/")[-1]
        authors_list = [a.get("name", "") for a in entry.get("authors", [])]

        paper_categories = [tag.get("term", "") for tag in entry.get("tags", [])]

        abstract = entry.get("summary", "").strip().replace("\n", " ")
        if len(abstract) > 800:
            abstract = abstract[:797] + "..."

        pdf_url = ""
        for link in entry.get("links", []):
            if link.get("type") == "application/pdf":
                pdf_url = link.get("href", "")
                break
        if not pdf_url and arxiv_id:
            pdf_url = f"https://arxiv.org/pdf/{arxiv_id}"

        papers.append(
            {
                "id": arxiv_id,
                "title": entry.get("title", "").strip().replace("\n", " "),
                "abstract": abstract,
                "authors": authors_list[:5],
                "published": published_dt.strftime("%Y-%m-%d"),
                "url": entry.get("id", ""),
                "pdf_url": pdf_url,
                "categories": paper_categories,
            }
        )

        if len(papers) >= max_results:
            break

    logger.info(
        "Fetched %d papers for query '%s' in date range %s",
        len(papers),
        query,
        date_range,
    )

    return {
        "query": query,
        "total_found": len(papers),
        "date_range": date_range,
        "papers": papers,
    }

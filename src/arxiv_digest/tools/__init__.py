"""Pipeline tools for fetching, scoring, and analysing ArXiv papers.

Re-exports the public functions for convenient importing::

    from arxiv_digest.tools import (
        fetch_arxiv_papers,
        fetch_paper_details,
        generate_digest,
        score_paper_impact,
        search_semantic_scholar,
        compare_with_history,
    )
"""

from arxiv_digest.tools.arxiv import fetch_arxiv_papers
from arxiv_digest.tools.digest_gen import generate_digest
from arxiv_digest.tools.history import compare_with_history
from arxiv_digest.tools.paper_details import fetch_paper_details
from arxiv_digest.tools.scorer import score_paper_impact
from arxiv_digest.tools.semantic_scholar import search_semantic_scholar

__all__ = [
    "compare_with_history",
    "fetch_arxiv_papers",
    "fetch_paper_details",
    "generate_digest",
    "score_paper_impact",
    "search_semantic_scholar",
]

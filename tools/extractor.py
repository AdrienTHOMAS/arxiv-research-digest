"""Key findings extraction tool.

Provides a structured analysis scaffold for the Claude agent to
evaluate individual papers on novelty, impact, methodology, and
reproducibility.
"""

import logging
from typing import Any

logger = logging.getLogger(__name__)


def extract_key_findings(
    paper_id: str,
    title: str,
    abstract: str,
    full_text_available: bool = False,
) -> dict[str, Any]:
    """Build a structured extraction scaffold for a single paper.

    The returned dictionary provides scoring criteria and instructions
    that guide the Claude agent to perform a deep analysis of the paper.

    Args:
        paper_id: ArXiv paper ID (e.g., "2401.12345").
        title: Paper title.
        abstract: Full paper abstract text.
        full_text_available: Whether full PDF text can be analyzed.

    Returns:
        Dictionary with paper metadata, scoring criteria, and analysis
        instructions for the agent.
    """
    abstract_excerpt = abstract[:500] if len(abstract) > 500 else abstract

    logger.info("Preparing extraction scaffold for paper %s: %s", paper_id, title)

    return {
        "paper_id": paper_id,
        "title": title,
        "abstract_excerpt": abstract_excerpt,
        "full_text_available": full_text_available,
        "scoring_criteria": {
            "novelty": "Is this a new approach or incremental?",
            "impact": "Could this change how the field works?",
            "methodology": "Is the method sound?",
            "reproducibility": "Can others replicate this?",
        },
        "instruction": (
            "Score this paper 1-10 on impact, extract: "
            "problem_solved, proposed_method, key_results, "
            "why_it_matters (2-3 sentences), impact_score (int 1-10), "
            "is_breakthrough (bool)"
        ),
    }

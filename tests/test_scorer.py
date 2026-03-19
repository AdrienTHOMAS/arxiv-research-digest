"""Tests for the heuristic paper impact scorer."""

from __future__ import annotations

from unittest.mock import MagicMock

from arxiv_digest.tools.scorer import _count_term_hits, score_paper_impact


def test_count_term_hits_found() -> None:
    """_count_term_hits finds matching terms in text."""
    text = "This is a novel approach that can outperform existing methods."
    terms = ["novel", "outperform", "missing"]
    assert _count_term_hits(text, terms) == 2


def test_count_term_hits_none() -> None:
    """_count_term_hits returns 0 when no terms match."""
    assert _count_term_hits("nothing here", ["novel", "first"]) == 0


def test_score_paper_impact_basic() -> None:
    """score_paper_impact returns a score dict with expected keys."""
    paper = MagicMock()
    paper.arxiv_id = "2401.00001"
    paper.abstract = "A novel framework for evaluation with benchmark results."
    paper.authors = [{"name": "Author A"}, {"name": "Author B"}]
    paper.categories = ["cs.LG"]

    result = score_paper_impact(paper)

    assert "score" in result
    assert "breakdown" in result
    assert "reasoning" in result
    assert isinstance(result["score"], int)
    assert 1 <= result["score"] <= 10
    bd = result["breakdown"]
    assert "novelty" in bd
    assert "methodology" in bd
    assert "results" in bd


def test_score_paper_impact_large_team() -> None:
    """Papers with many authors get a collaboration bonus."""
    paper = MagicMock()
    paper.arxiv_id = "2401.00002"
    paper.abstract = "Simple paper."
    paper.authors = [{"name": f"Author {i}"} for i in range(12)]
    paper.categories = ["cs.LG", "cs.AI", "stat.ML"]

    result = score_paper_impact(paper)

    bd = result["breakdown"]
    assert bd["collaboration"] == 2
    assert bd["breadth"] == 1


def test_score_paper_impact_empty_abstract() -> None:
    """Papers with empty abstract still get a valid score."""
    paper = MagicMock()
    paper.arxiv_id = "2401.00003"
    paper.abstract = ""
    paper.authors = []
    paper.categories = []

    result = score_paper_impact(paper)

    assert result["score"] == 1
    assert "Baseline" in result["reasoning"]

"""Anthropic tool-use definitions for the research agent.

Each entry in ``TOOLS`` follows the Anthropic API ``tool`` schema and is
passed directly to ``client.messages.create(tools=TOOLS)``.
"""

from __future__ import annotations

TOOLS: list[dict[str, object]] = [
    # ── 1. fetch_arxiv_papers ────────────────────────────────────────────
    {
        "name": "fetch_arxiv_papers",
        "description": (
            "Fetch recent papers from ArXiv for a given research topic. "
            "Returns a list of papers with titles, authors, abstracts, "
            "categories, and PDF URLs. Papers are filtered by the topic's "
            "configured ArXiv categories and keywords."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "topic_id": {
                    "type": "string",
                    "description": (
                        "Unique topic identifier as defined in topics.yaml "
                        "(e.g. 'machine_learning', 'nlp', 'computer_vision')."
                    ),
                },
                "days_back": {
                    "type": "integer",
                    "description": (
                        "Number of days to look back for new papers. "
                        "Defaults to 3. Use higher values (7-14) for "
                        "weekly digests or catching up after gaps."
                    ),
                    "default": 3,
                },
            },
            "required": ["topic_id"],
        },
    },
    # ── 2. fetch_paper_details ───────────────────────────────────────────
    {
        "name": "fetch_paper_details",
        "description": (
            "Fetch detailed metadata for a specific ArXiv paper by its ID. "
            "Returns the full abstract, all authors with affiliations, "
            "submission and update dates, comments, journal reference, "
            "and related categories. Use this to deep-dive into a paper "
            "that scored well in initial screening."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "arxiv_id": {
                    "type": "string",
                    "description": (
                        "The ArXiv paper identifier (e.g. '2401.12345' or "
                        "'2401.12345v2'). Do not include the full URL."
                    ),
                },
            },
            "required": ["arxiv_id"],
        },
    },
    # ── 3. score_paper_impact ────────────────────────────────────────────
    {
        "name": "score_paper_impact",
        "description": (
            "Score a paper's potential research impact on a 0-10 scale using "
            "heuristics: author reputation, institutional affiliation, "
            "methodological novelty, dataset contribution, and topic "
            "relevance. Returns a numeric score, a breakdown by factor, "
            "and a short reasoning string. Use this as a first-pass filter "
            "before checking citations on Semantic Scholar."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "arxiv_id": {
                    "type": "string",
                    "description": "ArXiv paper identifier to score.",
                },
            },
            "required": ["arxiv_id"],
        },
    },
    # ── 4. search_semantic_scholar ───────────────────────────────────────
    {
        "name": "search_semantic_scholar",
        "description": (
            "Look up a paper on Semantic Scholar to retrieve citation count, "
            "influential citation count, reference count, venue, and "
            "related papers. Useful for gauging real-world uptake of a "
            "paper — only call this for papers with a score >= 6 to "
            "avoid unnecessary API calls."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "arxiv_id": {
                    "type": "string",
                    "description": (
                        "ArXiv paper identifier. The tool resolves this to "
                        "the Semantic Scholar corpus ID internally."
                    ),
                },
            },
            "required": ["arxiv_id"],
        },
    },
    # ── 5. compare_with_history ──────────────────────────────────────────
    {
        "name": "compare_with_history",
        "description": (
            "Compare current papers against previously digested papers for "
            "the same topic. Identifies emerging trends, recurring themes, "
            "new research directions, and papers that extend or contradict "
            "prior work. Returns a trends dict with keys: emerging_themes, "
            "continued_threads, new_directions, and notable_shifts."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "topic_id": {
                    "type": "string",
                    "description": "Topic identifier to compare history for.",
                },
                "lookback_days": {
                    "type": "integer",
                    "description": (
                        "Number of days of history to compare against. "
                        "Defaults to 30. Use 7 for short-term trends "
                        "or 90 for longer-term pattern detection."
                    ),
                    "default": 30,
                },
            },
            "required": ["topic_id"],
        },
    },
    # ── 6. generate_digest ───────────────────────────────────────────────
    {
        "name": "generate_digest",
        "description": (
            "Generate the final Markdown digest from analysed papers. "
            "Renders a Jinja2 template in the requested format, persists "
            "the digest to the database, and writes the output file to "
            "disk. Call this as the last step after all papers have been "
            "fetched, scored, enriched, and trends compared."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "topic_id": {
                    "type": "string",
                    "description": "Topic identifier for this digest.",
                },
                "papers": {
                    "type": "array",
                    "description": (
                        "List of paper objects to include in the digest. "
                        "Each paper must have been scored and enriched."
                    ),
                    "items": {
                        "type": "object",
                        "properties": {
                            "arxiv_id": {
                                "type": "string",
                                "description": "ArXiv paper identifier.",
                            },
                            "title": {
                                "type": "string",
                                "description": "Paper title.",
                            },
                            "authors": {
                                "type": "string",
                                "description": "Comma-separated author names.",
                            },
                            "abstract": {
                                "type": "string",
                                "description": "Paper abstract.",
                            },
                            "score": {
                                "type": "number",
                                "description": "Impact score (0-10).",
                            },
                            "score_breakdown": {
                                "type": "object",
                                "description": "Score breakdown by factor.",
                            },
                            "reasoning": {
                                "type": "string",
                                "description": "Why this paper scored as it did.",
                            },
                            "citation_count": {
                                "type": "integer",
                                "description": "Citation count from Semantic Scholar.",
                            },
                            "categories": {
                                "type": "array",
                                "items": {"type": "string"},
                                "description": "ArXiv categories.",
                            },
                            "pdf_url": {
                                "type": "string",
                                "description": "URL to the paper PDF.",
                            },
                        },
                        "required": [
                            "arxiv_id",
                            "title",
                            "authors",
                            "abstract",
                            "score",
                            "reasoning",
                            "categories",
                            "pdf_url",
                        ],
                    },
                },
                "format": {
                    "type": "string",
                    "enum": ["newsletter", "technical", "executive"],
                    "description": (
                        "Digest format. 'newsletter' for a broad audience, "
                        "'technical' for researchers wanting methodology "
                        "details, 'executive' for a quick TLDR summary."
                    ),
                },
            },
            "required": ["topic_id", "papers", "format"],
        },
    },
]

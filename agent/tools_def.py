"""Tool definitions for the ArXiv Research Digest agent.

Defines the TOOLS list in Anthropic tool_use format, describing each
tool the agent can invoke during the research digest workflow.
"""

TOOLS: list[dict] = [
    {
        "name": "fetch_arxiv_papers",
        "description": (
            "Search ArXiv for recent papers matching a query and optional category "
            "filters. Returns structured metadata for each paper including title, "
            "abstract, authors, publication date, and links."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Search query for ArXiv papers (e.g., 'large language models', 'reinforcement learning').",
                },
                "days_back": {
                    "type": "integer",
                    "description": "Number of days to look back from today. Defaults to 7.",
                    "default": 7,
                },
                "max_results": {
                    "type": "integer",
                    "description": "Maximum number of papers to return. Defaults to 30.",
                    "default": 30,
                },
                "categories": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "ArXiv category filters (e.g., ['cs.AI', 'cs.LG', 'cs.CL']). Defaults to ['cs.AI', 'cs.LG', 'cs.CL'].",
                    "default": ["cs.AI", "cs.LG", "cs.CL"],
                },
            },
            "required": ["query"],
        },
    },
    {
        "name": "extract_key_findings",
        "description": (
            "Analyze a single paper's abstract and metadata to extract key findings, "
            "assess novelty, and score potential impact. Provides a structured scaffold "
            "for deep analysis of promising papers."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "paper_id": {
                    "type": "string",
                    "description": "The ArXiv paper ID (e.g., '2401.12345').",
                },
                "title": {
                    "type": "string",
                    "description": "The paper title.",
                },
                "abstract": {
                    "type": "string",
                    "description": "The full paper abstract.",
                },
                "full_text_available": {
                    "type": "boolean",
                    "description": "Whether the full PDF text is available for deeper analysis. Defaults to false.",
                    "default": False,
                },
            },
            "required": ["paper_id", "title", "abstract"],
        },
    },
    {
        "name": "compare_with_previous",
        "description": (
            "Compare the current week's findings with previous digest data to identify "
            "emerging trends, recurring themes, and prolific authors. Saves current "
            "findings for future comparisons."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "topic": {
                    "type": "string",
                    "description": "The research topic being tracked.",
                },
                "current_findings": {
                    "type": "array",
                    "description": "List of paper objects from the current week's analysis.",
                },
                "previous_digest_path": {
                    "type": "string",
                    "description": "Optional path to a specific previous digest JSON file. If not provided, the most recent file for this topic is used.",
                },
            },
            "required": ["topic", "current_findings"],
        },
    },
    {
        "name": "generate_digest",
        "description": (
            "Prepare and save the final digest document from curated top papers, trends, "
            "and notable authors. Returns the output path and formatting instructions."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "topic": {
                    "type": "string",
                    "description": "The research topic for the digest header.",
                },
                "top_papers": {
                    "type": "array",
                    "description": "Ranked list of the best papers with analysis and scores.",
                },
                "week": {
                    "type": "string",
                    "description": "Week identifier (e.g., '2025-W03'). Defaults to the current week.",
                },
                "trends": {
                    "type": "array",
                    "description": "Identified research trends and themes.",
                },
                "notable_authors": {
                    "type": "array",
                    "description": "Authors who published multiple notable papers this week.",
                },
                "format": {
                    "type": "string",
                    "enum": ["newsletter", "technical", "executive"],
                    "description": "Output format style. Defaults to 'newsletter'.",
                    "default": "newsletter",
                },
            },
            "required": ["topic", "top_papers"],
        },
    },
]

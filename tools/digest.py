"""Digest generation tool.

Prepares the final digest payload and saves the rendered output
to the output directory using a Jinja2 template.
"""

import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from jinja2 import Environment, FileSystemLoader, TemplateNotFound

logger = logging.getLogger(__name__)

DIGEST_TEMPLATE_PATH: Path = Path(__file__).parent.parent / "templates" / "digest.md.j2"


def _current_week_label() -> str:
    """Return the ISO week label for the current date."""
    now = datetime.now(tz=timezone.utc)
    iso_year, iso_week, _ = now.isocalendar()
    return f"{iso_year}-W{iso_week:02d}"


def generate_digest(
    topic: str,
    top_papers: list[dict[str, Any]],
    week: str | None = None,
    trends: list[str] | None = None,
    notable_authors: list[dict[str, Any]] | None = None,
    format: str = "newsletter",
) -> dict[str, Any]:
    """Prepare the digest payload and return rendering instructions.

    Collects all curated data into a structured payload that the agent
    uses to produce the final written digest.

    Args:
        topic: Research topic for the digest header.
        top_papers: Ranked list of top papers with analysis and scores.
        week: Week identifier (e.g., "2025-W03"). Defaults to current week.
        trends: Identified research trends and themes.
        notable_authors: Authors with multiple notable papers this week.
        format: Output style — one of "newsletter", "technical", "executive".

    Returns:
        Dictionary with the digest payload, output path, and formatting
        instructions for the agent.
    """
    if week is None:
        week = _current_week_label()
    if trends is None:
        trends = []
    if notable_authors is None:
        notable_authors = []

    capped_papers = top_papers[:10]

    output_dir = Path(__file__).parent.parent / "output" / "digests"
    output_dir.mkdir(parents=True, exist_ok=True)

    slug = topic.lower().replace(" ", "_")
    output_filename = f"{slug}_{week}.md"
    output_path = str(output_dir / output_filename)

    format_instructions = {
        "newsletter": (
            "Write in an engaging, accessible tone. Use clear section headers, "
            "bullet points, and brief but insightful summaries. Each paper gets "
            "2-3 sentences plus a 'Why it matters' callout. Aim for a reader who "
            "is technical but time-constrained."
        ),
        "technical": (
            "Write in a detailed, technical tone. Include methodology notes, "
            "specific numerical results, and comparisons to prior work. Each paper "
            "gets a full paragraph with technical depth. Aim for a researcher audience."
        ),
        "executive": (
            "Write in a concise, high-level tone. Focus on strategic implications "
            "and industry impact. Each paper gets 1-2 sentences maximum. Include "
            "a TL;DR section at the top. Aim for a non-technical leadership audience."
        ),
    }

    logger.info(
        "Prepared digest for '%s' (week %s): %d top papers, %d trends, format=%s",
        topic,
        week,
        len(capped_papers),
        len(trends),
        format,
    )

    return {
        "topic": topic,
        "week": week,
        "top_papers": capped_papers,
        "trends": trends,
        "notable_authors": notable_authors,
        "format": format,
        "output_path": output_path,
        "instruction": (
            f"Write the full digest in Markdown using the '{format}' style. "
            f"{format_instructions.get(format, format_instructions['newsletter'])} "
            f"Use the Jinja2 template structure from {DIGEST_TEMPLATE_PATH} as a guide. "
            f"After writing, the digest will be saved to: {output_path}"
        ),
    }


def save_digest(content: str, output_path: str) -> str:
    """Save rendered digest content to the output path.

    Args:
        content: The full Markdown digest content to save.
        output_path: File path where the digest should be written.

    Returns:
        The absolute path where the digest was saved.
    """
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)

    try:
        path.write_text(content, encoding="utf-8")
        logger.info("Digest saved to %s", path)
    except OSError as exc:
        logger.error("Failed to save digest to %s: %s", path, exc)
        raise

    return str(path.resolve())

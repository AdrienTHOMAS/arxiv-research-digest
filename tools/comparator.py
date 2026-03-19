"""Historical comparison tool.

Compares the current week's paper findings with previous digests
to identify emerging trends, recurring themes, and prolific authors.
Persists current findings for future comparisons.
"""

import json
import logging
import re
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

PREVIOUS_DIR: Path = Path(__file__).parent.parent / "data" / "previous"


def _slugify(text: str) -> str:
    """Convert text to a filesystem-safe slug."""
    slug = text.lower().strip()
    slug = re.sub(r"[^\w\s-]", "", slug)
    slug = re.sub(r"[\s_-]+", "_", slug)
    return slug.strip("_")


def _find_most_recent(topic: str) -> Path | None:
    """Find the most recent previous digest JSON for a topic."""
    slug = _slugify(topic)
    matching_files = sorted(
        PREVIOUS_DIR.glob(f"{slug}_*.json"),
        key=lambda p: p.stem,
        reverse=True,
    )
    return matching_files[0] if matching_files else None


def _current_week_label() -> str:
    """Return the ISO week label for the current date (e.g., '2025-W03')."""
    now = datetime.now(tz=timezone.utc)
    iso_year, iso_week, _ = now.isocalendar()
    return f"{iso_year}-W{iso_week:02d}"


def compare_with_previous(
    topic: str,
    current_findings: list[dict[str, Any]],
    previous_digest_path: str | None = None,
) -> dict[str, Any]:
    """Compare current findings with previous digest data.

    Identifies emerging trends, recurring themes, and prolific authors
    by comparing against the most recent saved digest for the same topic.
    Saves the current findings for future comparisons.

    Args:
        topic: Research topic being tracked.
        current_findings: List of paper objects from the current week.
        previous_digest_path: Optional explicit path to a previous digest
            JSON file. If not provided, the most recent matching file is used.

    Returns:
        Dictionary with comparison data including previous week info,
        prolific authors, and an instruction for trend analysis.
    """
    PREVIOUS_DIR.mkdir(parents=True, exist_ok=True)

    # Load previous data
    previous_data: dict[str, Any] = {}
    previous_path: Path | None = None

    if previous_digest_path:
        previous_path = Path(previous_digest_path)
        if previous_path.exists():
            try:
                previous_data = json.loads(previous_path.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError) as exc:
                logger.warning("Failed to read previous digest at %s: %s", previous_path, exc)
    else:
        previous_path = _find_most_recent(topic)
        if previous_path:
            try:
                previous_data = json.loads(previous_path.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError) as exc:
                logger.warning("Failed to read previous digest at %s: %s", previous_path, exc)
                previous_data = {}

    # Save current findings
    week_label = _current_week_label()
    slug = _slugify(topic)
    current_path = PREVIOUS_DIR / f"{slug}_{week_label}.json"

    save_payload = {
        "topic": topic,
        "week": week_label,
        "saved_at": datetime.now(tz=timezone.utc).isoformat(),
        "papers": current_findings,
    }

    try:
        current_path.write_text(
            json.dumps(save_payload, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        logger.info("Saved current findings to %s", current_path)
    except OSError as exc:
        logger.error("Failed to save current findings: %s", exc)

    # Analyze prolific authors
    author_counter: Counter[str] = Counter()
    for paper in current_findings:
        for author in paper.get("authors", []):
            if author:
                author_counter[author] += 1

    prolific_authors = [
        {"author": author, "papers": count}
        for author, count in author_counter.most_common()
        if count >= 2
    ]

    has_previous = bool(previous_data)
    previous_week = previous_data.get("week", "")
    previous_papers = previous_data.get("papers", [])

    logger.info(
        "Comparison for '%s': current=%d papers, previous=%d papers (week %s)",
        topic,
        len(current_findings),
        len(previous_papers),
        previous_week or "none",
    )

    return {
        "has_previous_data": has_previous,
        "previous_week": previous_week,
        "previous_paper_count": len(previous_papers),
        "current_paper_count": len(current_findings),
        "prolific_authors_this_week": prolific_authors,
        "comparison_instruction": (
            "Analyze the current findings against the previous week's data. "
            "Identify: (1) new research directions not seen before, "
            "(2) topics that are gaining momentum across weeks, "
            "(3) research areas that seem to be losing steam, "
            "(4) any author or lab that has significantly increased output. "
            "Be specific — cite paper IDs when referencing trends."
        ),
    }

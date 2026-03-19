"""Digest generation tool — renders Jinja2 templates and persists results.

Produces Markdown digests in three formats (newsletter, technical, executive)
from scored paper data, writes the output to disk, and updates the database.
"""

from __future__ import annotations

import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

import structlog
from jinja2 import Environment, FileSystemLoader, TemplateNotFound
from sqlalchemy import select

from arxiv_digest.models import Digest

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)

VALID_FORMATS = frozenset({"newsletter", "technical", "executive"})

_TEMPLATES_DIR = Path(__file__).resolve().parent.parent / "templates"
_OUTPUT_DIR = Path("output")


def _get_jinja_env() -> Environment:
    """Create a Jinja2 environment pointing at the project templates dir."""
    return Environment(
        loader=FileSystemLoader(str(_TEMPLATES_DIR)),
        autoescape=False,  # noqa: S701  — Markdown output, not HTML
        keep_trailing_newline=True,
        trim_blocks=True,
        lstrip_blocks=True,
    )


async def generate_digest(  # noqa: PLR0913
    topic_id: str,
    papers: list[dict[str, Any]],
    format: str,  # noqa: A002
    db: AsyncSession,
    *,
    topic_name: str | None = None,
    trends: dict[str, Any] | None = None,
) -> dict[str, object]:
    """Render a digest from scored papers and persist it.

    Args:
        topic_id: The topic identifier (e.g. ``machine_learning``).
        papers: List of paper dicts with keys ``title``, ``authors``,
            ``abstract``, ``score``, ``score_breakdown``, ``reasoning``,
            ``citation_count``, ``categories``, ``pdf_url``.
        format: One of ``newsletter``, ``technical``, or ``executive``.
        db: Active async database session.
        topic_name: Human-readable topic name (falls back to *topic_id*).
        trends: Optional trend analysis dict to include in the digest.

    Returns:
        Dict with ``digest_id``, ``file_path``, ``content``, ``paper_count``.

    Raises:
        ValueError: If *format* is not one of the valid formats.
        jinja2.TemplateNotFound: If the template file is missing.
    """
    if format not in VALID_FORMATS:
        msg = f"Invalid digest format '{format}'. Must be one of {sorted(VALID_FORMATS)}."
        raise ValueError(msg)

    run_date = datetime.datetime.now(tz=datetime.UTC).date()
    resolved_topic_name = topic_name or topic_id.replace("_", " ").title()

    logger.info(
        "digest.generating",
        topic_id=topic_id,
        format=format,
        paper_count=len(papers),
    )

    # ── Render template ──────────────────────────────────────────────────
    env = _get_jinja_env()
    template_name = f"digest_{format}.md.j2"

    try:
        template = env.get_template(template_name)
    except TemplateNotFound:
        logger.exception("digest.template_not_found", template=template_name)
        raise

    sorted_papers = sorted(papers, key=lambda p: p.get("score", 0), reverse=True)

    content = template.render(
        topic_name=resolved_topic_name,
        run_date=run_date.isoformat(),
        papers=sorted_papers,
        trends=trends or {},
        total_papers=len(sorted_papers),
    )

    # ── Persist digest to database ───────────────────────────────────────
    # Check for existing digest for this topic + date and update, or create new.
    stmt = select(Digest).where(
        Digest.topic_id == topic_id,
        Digest.run_date == run_date,
    )
    result = await db.execute(stmt)
    digest: Digest | None = result.scalar_one_or_none()

    if digest is None:
        digest = Digest(
            topic_id=topic_id,
            run_date=run_date,
            summary=content[:500],
            paper_count=len(sorted_papers),
            status="complete",
        )
        db.add(digest)
    else:
        digest.summary = content[:500]
        digest.paper_count = len(sorted_papers)
        digest.status = "complete"

    await db.flush()

    logger.info(
        "digest.persisted",
        digest_id=digest.id,
        topic_id=topic_id,
        status=digest.status,
    )

    # ── Write Markdown to disk ───────────────────────────────────────────
    out_dir = _OUTPUT_DIR / topic_id
    out_dir.mkdir(parents=True, exist_ok=True)
    file_path = out_dir / f"{run_date.isoformat()}_{format}.md"
    file_path.write_text(content, encoding="utf-8")

    logger.info("digest.written", file_path=str(file_path))

    return {
        "digest_id": digest.id,
        "file_path": str(file_path),
        "content": content,
        "paper_count": len(sorted_papers),
    }

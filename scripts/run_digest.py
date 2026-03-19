#!/usr/bin/env python3
"""CLI script to run a single digest without starting the FastAPI server.

Usage::

    python scripts/run_digest.py --topic 'AI agents' --days 7 --format newsletter
    python scripts/run_digest.py --topic machine_learning --output digest.md
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

# Ensure the project root is on the path
_project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_project_root / "src"))


async def _run(
    topic: str,
    days: int,
    digest_format: str,
    output: str | None,
) -> None:
    """Execute a digest run for the given topic.

    Args:
        topic: Topic ID or name.
        days: Number of days to look back.
        digest_format: Output format (newsletter, technical, executive).
        output: Output file path, or None for stdout.
    """
    from arxiv_digest.database import close_db, init_db  # noqa: PLC0415
    from arxiv_digest.schemas.topic import load_topics  # noqa: PLC0415

    await init_db()

    # Resolve topic name to topic ID if needed
    topics = load_topics()
    topic_id = topic
    for t in topics:
        if t.name.lower() == topic.lower() or t.id == topic:
            topic_id = t.id
            break

    try:
        from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker  # noqa: PLC0415

        from arxiv_digest.database import _get_engine  # noqa: PLC0415
        from arxiv_digest.services.digest_service import DigestService  # noqa: PLC0415

        engine = _get_engine()
        factory = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)

        async with factory() as session:
            service = DigestService(db=session)
            result = await service.run_digest(
                topic_id=topic_id,
                format=digest_format,
                days_back=days,
            )
            await session.commit()

        content = str(result.get("content", ""))

        if output:
            Path(output).write_text(content, encoding="utf-8")
            print(f"Digest written to {output}")  # noqa: T201
        else:
            print(content)  # noqa: T201

    finally:
        await close_db()


def main() -> None:
    """Parse CLI arguments and run the digest."""
    parser = argparse.ArgumentParser(
        description="Run an ArXiv research digest from the command line.",
    )
    parser.add_argument(
        "--topic",
        required=True,
        help="Topic ID or name (e.g. 'machine_learning' or 'AI agents').",
    )
    parser.add_argument(
        "--days",
        type=int,
        default=7,
        help="Number of days to look back (default: 7).",
    )
    parser.add_argument(
        "--format",
        dest="digest_format",
        choices=["newsletter", "technical", "executive"],
        default="newsletter",
        help="Digest format (default: newsletter).",
    )
    parser.add_argument(
        "--output",
        default=None,
        help="Output file path (default: stdout).",
    )

    args = parser.parse_args()
    asyncio.run(_run(args.topic, args.days, args.digest_format, args.output))


if __name__ == "__main__":
    main()

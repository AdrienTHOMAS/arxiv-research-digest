"""Weekly scheduler for the ArXiv Research Digest.

Runs the digest agent on a cron-like schedule using the `schedule` library,
defaulting to every Monday at 08:00 UTC.
"""

import argparse
import logging
import time
from datetime import datetime, timezone

import schedule
from dotenv import load_dotenv

from agent.loop import run

load_dotenv()

logger = logging.getLogger("arxiv_scheduler")


def run_weekly_digest(topics: list[str], output_format: str = "newsletter") -> None:
    """Run the digest agent for each topic in the list.

    Args:
        topics: List of research topics to generate digests for.
        output_format: Digest format — "newsletter", "technical", or "executive".
    """
    timestamp = datetime.now(tz=timezone.utc).isoformat()
    logger.info("Starting scheduled digest run at %s for %d topics", timestamp, len(topics))

    for topic in topics:
        logger.info("Processing topic: %s", topic)
        try:
            result = run(
                topic=topic,
                days_back=7,
                max_papers=30,
                output_format=output_format,
            )
            logger.info(
                "Completed '%s': %d papers found, digest at %s",
                topic,
                result["papers_found"],
                result["digest_path"],
            )
        except Exception as exc:
            logger.exception("Failed to generate digest for '%s': %s", topic, exc)

    logger.info("Scheduled run complete")


def main() -> None:
    """Parse arguments and start the scheduler."""
    parser = argparse.ArgumentParser(
        description="Schedule weekly ArXiv Research Digest runs",
    )
    parser.add_argument(
        "--topics",
        nargs="+",
        required=True,
        help="Research topics to generate digests for",
    )
    parser.add_argument(
        "--run-now",
        action="store_true",
        help="Run immediately in addition to scheduling",
    )
    parser.add_argument(
        "--format",
        choices=["newsletter", "technical", "executive"],
        default="newsletter",
        help="Output format (default: newsletter)",
    )

    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    if args.run_now:
        logger.info("Running immediate digest...")
        run_weekly_digest(args.topics, output_format=args.format)

    schedule.every().monday.at("08:00").do(
        run_weekly_digest,
        topics=args.topics,
        output_format=args.format,
    )

    logger.info(
        "Scheduler started — will run every Monday at 08:00 UTC for topics: %s",
        ", ".join(args.topics),
    )

    try:
        while True:
            schedule.run_pending()
            time.sleep(60)
    except KeyboardInterrupt:
        logger.info("Scheduler stopped by user")


if __name__ == "__main__":
    main()

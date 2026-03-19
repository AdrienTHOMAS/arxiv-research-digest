"""Digest orchestration service.

Coordinates agent loop execution, run logging, and webhook delivery for
each research topic digest run.
"""

from __future__ import annotations

import datetime
from typing import TYPE_CHECKING

import structlog

from arxiv_digest.config import get_settings
from arxiv_digest.models.run_log import RunLog
from arxiv_digest.schemas.topic import load_topics
from arxiv_digest.services.webhook_service import WebhookService

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)


class DigestService:
    """Orchestrates a full digest run: agent loop, run logging, and webhooks.

    Args:
        db: An active async database session.
    """

    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def run_digest(
        self,
        topic_id: str,
        format: str = "newsletter",
        days_back: int = 3,
    ) -> dict[str, object]:
        """Execute a single digest run for a topic.

        Creates a :class:`RunLog` entry, delegates to the agent loop, triggers
        webhook notifications on success, and records the outcome.

        Args:
            topic_id: Identifier of the research topic to process.
            format: Digest output format (e.g. ``newsletter``, ``technical``).
            days_back: Number of days to look back for papers.

        Returns:
            A dict containing the agent loop result enriched with ``run_log_id``.

        Raises:
            Exception: Re-raises any error from the agent loop after recording
                it in the run log.
        """
        from arxiv_digest.agent.loop import run_agent_loop  # noqa: PLC0415

        today = datetime.date.today()

        run_log = RunLog(
            run_date=today,
            topic_id=topic_id,
            status="running",
        )
        self._db.add(run_log)
        await self._db.flush()

        logger.info(
            "digest.run.started",
            topic_id=topic_id,
            run_log_id=run_log.id,
            format=format,
            days_back=days_back,
        )

        try:
            result = await run_agent_loop(
                topic_id=topic_id,
                digest_format=format,
                db=self._db,
                days_back=days_back,
            )

            run_log.status = "complete"
            run_log.papers_found = int(result.get("papers_found", 0))
            run_log.papers_filtered = int(result.get("papers_filtered", 0))
            run_log.duration_seconds = float(result.get("duration_seconds", 0.0))
            await self._db.flush()

            logger.info(
                "digest.run.complete",
                topic_id=topic_id,
                run_log_id=run_log.id,
                duration_seconds=run_log.duration_seconds,
            )

            await self._deliver_webhooks(result)

            return {**result, "run_log_id": run_log.id}

        except Exception as exc:
            run_log.status = "failed"
            run_log.error = str(exc)
            await self._db.flush()

            logger.error(
                "digest.run.failed",
                topic_id=topic_id,
                run_log_id=run_log.id,
                error=str(exc),
            )
            raise

    async def run_all_topics(
        self,
        format: str = "newsletter",
    ) -> list[dict[str, object]]:
        """Run digests for every configured topic.

        Args:
            format: Digest output format applied to all topics.

        Returns:
            A list of result dicts, one per topic.
        """
        topics = load_topics()
        results: list[dict[str, object]] = []

        logger.info("digest.run_all.started", topic_count=len(topics))

        for topic in topics:
            logger.info("digest.run_all.topic", topic_id=topic.id)
            result = await self.run_digest(topic_id=topic.id, format=format)
            results.append(result)

        logger.info("digest.run_all.complete", topic_count=len(results))
        return results

    async def _deliver_webhooks(self, result: dict[str, object]) -> None:
        """Deliver webhook notifications for a completed digest.

        Args:
            result: The agent loop result containing digest metadata.
        """
        settings = get_settings()
        if not settings.WEBHOOK_URLS:
            return

        digest_id = str(result.get("digest_id", ""))
        payload: dict[str, object] = {
            "title": f"ArXiv Digest Ready",
            "summary": str(result.get("content", "")),
            "paper_count": result.get("paper_count", 0),
            "digest_id": digest_id,
        }

        webhook_service = WebhookService(session=self._db)

        for url in settings.WEBHOOK_URLS:
            logger.info("digest.webhook.delivering", url=url, digest_id=digest_id)
            await webhook_service.deliver(
                digest_id=digest_id,
                url=url,
                payload=payload,
            )

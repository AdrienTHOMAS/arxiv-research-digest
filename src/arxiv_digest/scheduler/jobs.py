"""APScheduler job definitions for periodic digest execution.

Reads topic and schedule configuration from YAML files and registers
cron-triggered jobs that invoke :class:`DigestService` for each topic.
"""

from __future__ import annotations

from pathlib import Path

import structlog
import yaml
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from arxiv_digest.config import get_settings
from arxiv_digest.schemas.topic import load_topics

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)

_SCHEDULE_FILE = Path("config/schedule.yaml")
_DEFAULT_CRON = "0 8 * * 0-4"
_DEFAULT_FORMAT = "newsletter"
_TIMEZONE = "Europe/Paris"


def _load_schedule_config() -> dict[str, dict[str, str]]:
    """Load per-topic schedule overrides from ``config/schedule.yaml``.

    Returns:
        A mapping of ``{topic_id: {"cron": ..., "format": ...}}``, plus a
        ``"default"`` key with fallback values.
    """
    if not _SCHEDULE_FILE.exists():
        logger.info("scheduler.no_schedule_file", path=str(_SCHEDULE_FILE))
        return {"default": {"cron": _DEFAULT_CRON, "format": _DEFAULT_FORMAT}}

    raw = yaml.safe_load(_SCHEDULE_FILE.read_text(encoding="utf-8"))

    config: dict[str, dict[str, str]] = {}

    for topic_id, topic_cfg in (raw.get("topics") or {}).items():
        config[topic_id] = {
            "cron": str(topic_cfg.get("cron", _DEFAULT_CRON)),
            "format": str(topic_cfg.get("format", _DEFAULT_FORMAT)),
        }

    default_section = raw.get("default") or {}
    config["default"] = {
        "cron": str(default_section.get("cron", _DEFAULT_CRON)),
        "format": str(default_section.get("format", _DEFAULT_FORMAT)),
    }

    return config


async def _run_scheduled_digest(topic_id: str, digest_format: str) -> None:
    """Execute a scheduled digest run within its own database session.

    Args:
        topic_id: The topic to generate a digest for.
        digest_format: Output format (e.g. ``newsletter``, ``technical``).
    """
    from arxiv_digest.database import close_db, get_db, init_db  # noqa: PLC0415
    from arxiv_digest.services.digest_service import DigestService  # noqa: PLC0415

    logger.info(
        "scheduler.job.started",
        topic_id=topic_id,
        format=digest_format,
    )

    settings = get_settings()
    await init_db(settings.DATABASE_URL)

    try:
        async for session in get_db():
            service = DigestService(db=session)
            result = await service.run_digest(
                topic_id=topic_id,
                format=digest_format,
            )
            logger.info(
                "scheduler.job.complete",
                topic_id=topic_id,
                run_log_id=result.get("run_log_id"),
            )
    except Exception:
        logger.exception("scheduler.job.failed", topic_id=topic_id)
    finally:
        await close_db()


def setup_scheduler() -> AsyncIOScheduler:
    """Create and configure the APScheduler with digest jobs for each topic.

    Loads topics from ``config/topics.yaml`` and schedule overrides from
    ``config/schedule.yaml``.  Each topic gets a cron-triggered job that calls
    :func:`_run_scheduled_digest`.

    Returns:
        A configured but **not started** :class:`AsyncIOScheduler`.
    """
    scheduler = AsyncIOScheduler(timezone=_TIMEZONE)

    topics = load_topics()
    schedule_config = _load_schedule_config()
    default_cfg = schedule_config.get("default", {"cron": _DEFAULT_CRON, "format": _DEFAULT_FORMAT})

    for topic in topics:
        cfg = schedule_config.get(topic.id, default_cfg)
        cron_expr = cfg["cron"]
        digest_format = cfg["format"]

        parts = cron_expr.split()
        trigger = CronTrigger(
            minute=parts[0],
            hour=parts[1],
            day=parts[2],
            month=parts[3],
            day_of_week=parts[4],
            timezone=_TIMEZONE,
        )

        scheduler.add_job(
            _run_scheduled_digest,
            trigger=trigger,
            args=[topic.id, digest_format],
            id=f"digest_{topic.id}",
            name=f"Digest: {topic.name}",
            replace_existing=True,
        )

        logger.info(
            "scheduler.job.registered",
            topic_id=topic.id,
            topic_name=topic.name,
            cron=cron_expr,
            format=digest_format,
        )

    logger.info("scheduler.setup.complete", job_count=len(topics))
    return scheduler

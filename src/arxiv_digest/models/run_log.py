"""RunLog ORM model tracking pipeline execution runs."""

from __future__ import annotations

import datetime  # noqa: TC003 — required at runtime for SQLAlchemy annotation resolution

from sqlalchemy import CheckConstraint, Date, Float, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from arxiv_digest.database import Base


class RunLog(Base):
    """Log entry for a single pipeline run against a research topic.

    Attributes:
        run_date: The date of the pipeline run.
        topic_id: Identifier of the topic processed in this run.
        papers_found: Total number of papers found on ArXiv.
        papers_filtered: Number of papers remaining after relevance filtering.
        duration_seconds: Wall-clock duration of the run in seconds.
        status: Current status (``pending``, ``running``, ``complete``, or ``failed``).
        error: Error message if the run failed.
    """

    __tablename__ = "run_logs"
    __table_args__ = (
        CheckConstraint(
            "status IN ('pending', 'running', 'complete', 'failed')",
            name="status_valid",
        ),
        Index("ix_run_logs_topic_id", "topic_id"),
    )

    run_date: Mapped[datetime.date] = mapped_column(Date, nullable=False)
    topic_id: Mapped[str] = mapped_column(String(100), nullable=False)
    papers_found: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    papers_filtered: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    duration_seconds: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    status: Mapped[str] = mapped_column(
        String(20),
        default="pending",
        nullable=False,
    )
    error: Mapped[str | None] = mapped_column(Text, nullable=True)

    def __repr__(self) -> str:
        """Return a developer-friendly representation."""
        return (
            f"<RunLog(id={self.id!r}, topic_id={self.topic_id!r}, "
            f"run_date={self.run_date!r}, status={self.status!r})>"
        )

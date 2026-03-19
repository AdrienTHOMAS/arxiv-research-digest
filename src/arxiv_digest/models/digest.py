"""Digest ORM model representing a daily digest for a research topic."""

from __future__ import annotations

import datetime  # noqa: TC003 — required at runtime for SQLAlchemy annotation resolution
from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, Date, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from arxiv_digest.database import Base

if TYPE_CHECKING:
    from arxiv_digest.models.paper import Paper


class Digest(Base):
    """A daily digest grouping papers for a specific research topic.

    Attributes:
        topic_id: Identifier of the topic this digest covers.
        run_date: The date this digest was generated.
        summary: AI-generated summary of the digest contents.
        paper_count: Number of papers included in the digest.
        status: Current processing status (``pending``, ``complete``, or ``failed``).
    """

    __tablename__ = "digests"
    __table_args__ = (
        UniqueConstraint("topic_id", "run_date", name="uq_digests_topic_id_run_date"),
        CheckConstraint(
            "status IN ('pending', 'complete', 'failed')",
            name="status_valid",
        ),
    )

    topic_id: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    run_date: Mapped[datetime.date] = mapped_column(Date, nullable=False)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    paper_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    status: Mapped[str] = mapped_column(
        String(20),
        default="pending",
        nullable=False,
    )

    papers: Mapped[list[Paper]] = relationship(
        "Paper",
        back_populates="digest",
        lazy="selectin",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        """Return a developer-friendly representation."""
        return (
            f"<Digest(id={self.id!r}, topic_id={self.topic_id!r}, "
            f"run_date={self.run_date!r}, status={self.status!r})>"
        )

"""Paper ORM model representing an ArXiv paper stored in the database."""

from __future__ import annotations

import datetime  # noqa: TC003 — required at runtime for SQLAlchemy annotation resolution
from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, Date, Float, ForeignKey, Index, String, Text
from sqlalchemy.dialects.postgresql import JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship

from arxiv_digest.database import Base

if TYPE_CHECKING:
    from arxiv_digest.models.digest import Digest


class Paper(Base):
    """An ArXiv paper retrieved and scored for relevance.

    Attributes:
        arxiv_id: The unique ArXiv identifier (e.g. ``2301.12345``).
        title: Paper title.
        authors: List of author dictionaries with at least a ``name`` key.
        abstract: Full abstract text.
        published_date: Date the paper was published on ArXiv.
        categories: List of ArXiv category strings (e.g. ``["cs.LG", "stat.ML"]``).
        pdf_url: Direct URL to the paper PDF.
        relevance_score: AI-assigned relevance score between 0.0 and 1.0.
        topic_id: Identifier of the topic this paper was fetched for.
        digest_id: Foreign key to the digest this paper belongs to, if any.
    """

    __tablename__ = "papers"
    __table_args__ = (
        CheckConstraint(
            "relevance_score IS NULL OR (relevance_score >= 0.0 AND relevance_score <= 1.0)",
            name="relevance_score_range",
        ),
        Index("ix_papers_topic_id", "topic_id"),
        Index("ix_papers_digest_id", "digest_id"),
    )

    arxiv_id: Mapped[str] = mapped_column(
        String(50),
        unique=True,
        nullable=False,
        index=True,
    )
    title: Mapped[str] = mapped_column(String(1000), nullable=False)
    authors: Mapped[list[dict[str, str]]] = mapped_column(
        JSON,
        nullable=False,
    )
    abstract: Mapped[str] = mapped_column(Text, nullable=False)
    published_date: Mapped[datetime.date] = mapped_column(Date, nullable=False)
    categories: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    pdf_url: Mapped[str] = mapped_column(String(500), nullable=False)
    relevance_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    topic_id: Mapped[str] = mapped_column(String(100), nullable=False)
    digest_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("digests.id"),
        nullable=True,
    )

    digest: Mapped[Digest | None] = relationship(
        "Digest",
        back_populates="papers",
        lazy="selectin",
    )

    def __repr__(self) -> str:
        """Return a developer-friendly representation."""
        return (
            f"<Paper(id={self.id!r}, arxiv_id={self.arxiv_id!r}, "
            f"title={self.title[:60]!r}...)>"
        )

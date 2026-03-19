"""WebhookDelivery ORM model tracking webhook delivery attempts."""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import Boolean, ForeignKey, Index, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship

from arxiv_digest.database import Base

if TYPE_CHECKING:
    from arxiv_digest.models.digest import Digest


class WebhookDelivery(Base):
    """Record of a single webhook delivery attempt for a digest.

    Attributes:
        digest_id: Foreign key to the digest being delivered.
        url: The webhook endpoint URL.
        status_code: HTTP status code returned by the endpoint.
        payload: The JSON payload sent in the request.
        attempt: The delivery attempt number (starts at 1).
        success: Whether the delivery was successful.
        error: Error message if the delivery failed.
    """

    __tablename__ = "webhook_deliveries"
    __table_args__ = (
        Index("ix_webhook_deliveries_digest_id", "digest_id"),
    )

    digest_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("digests.id"),
        nullable=False,
    )
    url: Mapped[str] = mapped_column(String(2000), nullable=False)
    status_code: Mapped[int | None] = mapped_column(Integer, nullable=True)
    payload: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False)
    attempt: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    success: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)

    digest: Mapped[Digest] = relationship(
        "Digest",
        lazy="selectin",
    )

    def __repr__(self) -> str:
        """Return a developer-friendly representation."""
        return (
            f"<WebhookDelivery(id={self.id!r}, digest_id={self.digest_id!r}, "
            f"url={self.url!r}, success={self.success!r})>"
        )

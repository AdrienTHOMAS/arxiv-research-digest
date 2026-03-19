"""Pydantic v2 schemas for Digest resources."""

import datetime
import enum

from pydantic import BaseModel, ConfigDict, Field

from arxiv_digest.schemas.paper import PaperRead


class DigestStatus(enum.StrEnum):
    """Allowed status values for a digest."""

    PENDING = "pending"
    COMPLETE = "complete"
    FAILED = "failed"


class DigestBase(BaseModel):
    """Shared fields for digest schemas.

    Attributes:
        topic_id: Identifier of the research topic.
        run_date: Date the digest was generated.
        summary: AI-generated summary of the digest.
        paper_count: Number of papers in the digest.
        status: Processing status of the digest.
    """

    topic_id: str = Field(max_length=100, description="Research topic identifier.")
    run_date: datetime.date = Field(description="Date the digest was generated.")
    summary: str | None = Field(default=None, description="AI-generated summary.")
    paper_count: int = Field(default=0, ge=0, description="Number of papers in the digest.")
    status: DigestStatus = Field(
        default=DigestStatus.PENDING,
        description="Processing status.",
    )


class DigestCreate(BaseModel):
    """Schema for creating a new digest.

    Only the topic and run date are required; remaining fields use defaults.
    """

    topic_id: str = Field(max_length=100, description="Research topic identifier.")
    run_date: datetime.date = Field(description="Date the digest is generated for.")


class DigestRead(DigestBase):
    """Schema for reading a digest from the database, including its papers."""

    model_config = ConfigDict(from_attributes=True)

    id: str = Field(description="UUID primary key.")
    papers: list[PaperRead] = Field(default_factory=list, description="Papers in this digest.")
    created_at: datetime.datetime = Field(description="Record creation timestamp (UTC).")
    updated_at: datetime.datetime = Field(description="Last update timestamp (UTC).")


class DigestBrief(BaseModel):
    """Compact digest representation for list views.

    Attributes:
        id: UUID primary key.
        topic_id: Research topic identifier.
        run_date: Date the digest was generated.
        paper_count: Number of papers in the digest.
        status: Processing status.
    """

    model_config = ConfigDict(from_attributes=True)

    id: str = Field(description="UUID primary key.")
    topic_id: str = Field(description="Research topic identifier.")
    run_date: datetime.date = Field(description="Digest generation date.")
    paper_count: int = Field(default=0, description="Number of papers.")
    status: DigestStatus = Field(description="Processing status.")

"""Pydantic v2 schemas for Paper resources."""

import datetime

from pydantic import BaseModel, ConfigDict, Field


class PaperBase(BaseModel):
    """Shared fields for paper schemas.

    Attributes:
        arxiv_id: The unique ArXiv identifier.
        title: Paper title.
        authors: List of author dictionaries.
        abstract: Full abstract text.
        published_date: Date the paper was published on ArXiv.
        categories: List of ArXiv category strings.
        pdf_url: Direct URL to the paper PDF.
        relevance_score: AI-assigned relevance score between 0.0 and 1.0.
        topic_id: Identifier of the associated research topic.
    """

    arxiv_id: str = Field(max_length=50, description="Unique ArXiv identifier.")
    title: str = Field(max_length=1000, description="Paper title.")
    authors: list[dict[str, str]] = Field(description="List of author dictionaries.")
    abstract: str = Field(description="Full abstract text.")
    published_date: datetime.date = Field(description="Publication date on ArXiv.")
    categories: list[str] = Field(description="ArXiv category strings.")
    pdf_url: str = Field(max_length=500, description="Direct URL to PDF.")
    relevance_score: float | None = Field(
        default=None,
        ge=0.0,
        le=1.0,
        description="Relevance score between 0.0 and 1.0.",
    )
    topic_id: str = Field(max_length=100, description="Associated topic identifier.")


class PaperCreate(PaperBase):
    """Schema for creating a new paper.

    Inherits all fields from :class:`PaperBase`. The ``digest_id`` can
    optionally be provided to associate the paper with an existing digest.
    """

    digest_id: str | None = Field(default=None, description="Optional digest ID to associate.")


class PaperRead(PaperBase):
    """Schema for reading a paper from the database.

    Includes the database-assigned ``id`` and timestamps.
    """

    model_config = ConfigDict(from_attributes=True)

    id: str = Field(description="UUID primary key.")
    digest_id: str | None = Field(default=None, description="Associated digest ID.")
    created_at: datetime.datetime = Field(description="Record creation timestamp (UTC).")
    updated_at: datetime.datetime = Field(description="Last update timestamp (UTC).")


class PaperBrief(BaseModel):
    """Compact paper representation for list views.

    Attributes:
        id: UUID primary key.
        arxiv_id: Unique ArXiv identifier.
        title: Paper title.
        relevance_score: Relevance score between 0.0 and 1.0.
        published_date: Publication date on ArXiv.
    """

    model_config = ConfigDict(from_attributes=True)

    id: str = Field(description="UUID primary key.")
    arxiv_id: str = Field(description="Unique ArXiv identifier.")
    title: str = Field(description="Paper title.")
    relevance_score: float | None = Field(
        default=None,
        description="Relevance score between 0.0 and 1.0.",
    )
    published_date: datetime.date = Field(description="Publication date on ArXiv.")

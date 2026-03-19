"""Pydantic v2 schemas for RunLog resources."""

import datetime
import enum

from pydantic import BaseModel, ConfigDict, Field


class RunLogStatus(enum.StrEnum):
    """Allowed status values for a pipeline run."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETE = "complete"
    FAILED = "failed"


class RunLogBase(BaseModel):
    """Shared fields for run log schemas.

    Attributes:
        run_date: Date of the pipeline run.
        topic_id: Research topic processed.
        papers_found: Total papers found on ArXiv.
        papers_filtered: Papers remaining after filtering.
        duration_seconds: Run duration in seconds.
        status: Current run status.
        error: Error message if the run failed.
    """

    run_date: datetime.date = Field(description="Date of the pipeline run.")
    topic_id: str = Field(max_length=100, description="Research topic processed.")
    papers_found: int = Field(default=0, ge=0, description="Total papers found.")
    papers_filtered: int = Field(default=0, ge=0, description="Papers after filtering.")
    duration_seconds: float = Field(default=0.0, ge=0.0, description="Run duration in seconds.")
    status: RunLogStatus = Field(
        default=RunLogStatus.PENDING,
        description="Current run status.",
    )
    error: str | None = Field(default=None, description="Error message on failure.")


class RunLogCreate(BaseModel):
    """Schema for creating a new run log entry."""

    run_date: datetime.date = Field(description="Date of the pipeline run.")
    topic_id: str = Field(max_length=100, description="Research topic to process.")


class RunLogRead(RunLogBase):
    """Schema for reading a run log from the database."""

    model_config = ConfigDict(from_attributes=True)

    id: str = Field(description="UUID primary key.")
    created_at: datetime.datetime = Field(description="Record creation timestamp (UTC).")
    updated_at: datetime.datetime = Field(description="Last update timestamp (UTC).")

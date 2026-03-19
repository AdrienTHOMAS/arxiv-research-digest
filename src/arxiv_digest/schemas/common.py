"""Shared Pydantic schemas used across the ArXiv Research Digest API."""

from pydantic import BaseModel, Field


class PaginatedResponse[T](BaseModel):
    """Generic paginated response wrapper.

    Attributes:
        items: The page of results.
        total: Total number of items matching the query.
        page: Current page number (1-indexed).
        page_size: Maximum number of items per page.
        pages: Total number of pages.
    """

    items: list[T]
    total: int = Field(ge=0, description="Total number of items matching the query.")
    page: int = Field(ge=1, description="Current page number (1-indexed).")
    page_size: int = Field(ge=1, description="Maximum number of items per page.")
    pages: int = Field(ge=0, description="Total number of pages.")

"""Paper retrieval endpoints.

Provides paginated listing and detail retrieval of ArXiv papers stored
in the database.
"""

from __future__ import annotations

import math
from typing import TYPE_CHECKING

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select

from arxiv_digest.api.deps import get_db_session

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession
from arxiv_digest.models.paper import Paper
from arxiv_digest.schemas.common import PaginatedResponse
from arxiv_digest.schemas.paper import PaperBrief, PaperRead

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)

router = APIRouter(prefix="/papers", tags=["papers"])


@router.get(
    "",
    summary="List papers",
    description="Returns a paginated list of papers with optional filters.",
    response_model=PaginatedResponse[PaperBrief],
)
async def list_papers(
    topic_id: str | None = Query(default=None, description="Filter by topic identifier."),
    digest_id: str | None = Query(default=None, description="Filter by digest UUID."),
    min_score: float | None = Query(
        default=None,
        ge=0.0,
        le=1.0,
        description="Minimum relevance score filter.",
    ),
    page: int = Query(default=1, ge=1, description="Page number (1-indexed)."),
    page_size: int = Query(
        default=20,
        ge=1,
        le=100,
        description="Number of items per page (max 100).",
    ),
    session: AsyncSession = Depends(get_db_session),
) -> PaginatedResponse[PaperBrief]:
    """Return a paginated, filtered list of papers.

    Args:
        topic_id: Optional filter by topic identifier.
        digest_id: Optional filter by parent digest UUID.
        min_score: Optional minimum relevance score threshold.
        page: Page number, 1-indexed.
        page_size: Number of results per page, capped at 100.
        session: Injected database session.

    Returns:
        A paginated response containing paper brief records.
    """
    query = select(Paper)
    count_query = select(func.count(Paper.id))

    if topic_id is not None:
        query = query.where(Paper.topic_id == topic_id)
        count_query = count_query.where(Paper.topic_id == topic_id)

    if digest_id is not None:
        query = query.where(Paper.digest_id == digest_id)
        count_query = count_query.where(Paper.digest_id == digest_id)

    if min_score is not None:
        query = query.where(Paper.relevance_score >= min_score)
        count_query = count_query.where(Paper.relevance_score >= min_score)

    total_result = await session.execute(count_query)
    total = total_result.scalar_one()

    offset = (page - 1) * page_size
    query = query.order_by(Paper.relevance_score.desc().nullslast(), Paper.published_date.desc())
    query = query.offset(offset).limit(page_size)

    result = await session.execute(query)
    papers = list(result.scalars().all())

    pages = math.ceil(total / page_size) if total > 0 else 0

    return PaginatedResponse[PaperBrief](
        items=[PaperBrief.model_validate(p) for p in papers],
        total=total,
        page=page,
        page_size=page_size,
        pages=pages,
    )


@router.get(
    "/{paper_id}",
    summary="Get a single paper",
    description="Returns the full paper record.",
    response_model=PaperRead,
)
async def get_paper(
    paper_id: str,
    session: AsyncSession = Depends(get_db_session),
) -> PaperRead:
    """Return a single paper by its UUID.

    Args:
        paper_id: UUID of the paper to retrieve.
        session: Injected database session.

    Raises:
        HTTPException: 404 if the paper does not exist.
    """
    query = select(Paper).where(Paper.id == paper_id)
    result = await session.execute(query)
    paper = result.scalar_one_or_none()

    if paper is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Paper '{paper_id}' not found.",
        )

    return PaperRead.model_validate(paper)

"""Digest CRUD endpoints.

Provides paginated listing, detail retrieval, and creation of research
digests.
"""

from __future__ import annotations

import datetime
import math
from typing import TYPE_CHECKING

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.orm import selectinload

from arxiv_digest.api.deps import get_db_session, verify_api_key
from arxiv_digest.models.digest import Digest
from arxiv_digest.schemas.common import PaginatedResponse
from arxiv_digest.schemas.digest import DigestBrief, DigestCreate, DigestRead

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)

router = APIRouter(prefix="/digests", tags=["digests"])


@router.get(
    "",
    summary="List digests",
    description="Returns a paginated list of digests with optional filters.",
    response_model=PaginatedResponse[DigestBrief],
)
async def list_digests(
    topic_id: str | None = Query(default=None, description="Filter by topic identifier."),
    digest_status: str | None = Query(
        default=None,
        alias="status",
        description="Filter by digest status (pending, complete, failed).",
    ),
    date_from: datetime.date | None = Query(
        default=None,
        description="Filter digests on or after this date.",
    ),
    date_to: datetime.date | None = Query(
        default=None,
        description="Filter digests on or before this date.",
    ),
    page: int = Query(default=1, ge=1, description="Page number (1-indexed)."),
    page_size: int = Query(
        default=20,
        ge=1,
        le=100,
        description="Number of items per page (max 100).",
    ),
    session: AsyncSession = Depends(get_db_session),
) -> PaginatedResponse[DigestBrief]:
    """Return a paginated, filtered list of digests.

    Args:
        topic_id: Optional filter by topic identifier.
        digest_status: Optional filter by processing status.
        date_from: Optional lower-bound date filter (inclusive).
        date_to: Optional upper-bound date filter (inclusive).
        page: Page number, 1-indexed.
        page_size: Number of results per page, capped at 100.
        session: Injected database session.

    Returns:
        A paginated response containing digest brief records.
    """
    query = select(Digest)
    count_query = select(func.count(Digest.id))

    if topic_id is not None:
        query = query.where(Digest.topic_id == topic_id)
        count_query = count_query.where(Digest.topic_id == topic_id)

    if digest_status is not None:
        query = query.where(Digest.status == digest_status)
        count_query = count_query.where(Digest.status == digest_status)

    if date_from is not None:
        query = query.where(Digest.run_date >= date_from)
        count_query = count_query.where(Digest.run_date >= date_from)

    if date_to is not None:
        query = query.where(Digest.run_date <= date_to)
        count_query = count_query.where(Digest.run_date <= date_to)

    total_result = await session.execute(count_query)
    total = total_result.scalar_one()

    offset = (page - 1) * page_size
    query = query.order_by(Digest.run_date.desc(), Digest.created_at.desc())
    query = query.offset(offset).limit(page_size)

    result = await session.execute(query)
    digests = list(result.scalars().all())

    pages = math.ceil(total / page_size) if total > 0 else 0

    return PaginatedResponse[DigestBrief](
        items=[DigestBrief.model_validate(d) for d in digests],
        total=total,
        page=page,
        page_size=page_size,
        pages=pages,
    )


@router.get(
    "/{digest_id}",
    summary="Get a single digest",
    description="Returns the full digest including its papers.",
    response_model=DigestRead,
)
async def get_digest(
    digest_id: str,
    session: AsyncSession = Depends(get_db_session),
) -> DigestRead:
    """Return a single digest with its associated papers.

    Args:
        digest_id: UUID of the digest to retrieve.
        session: Injected database session.

    Raises:
        HTTPException: 404 if the digest does not exist.
    """
    query = (
        select(Digest)
        .options(selectinload(Digest.papers))
        .where(Digest.id == digest_id)
    )
    result = await session.execute(query)
    digest = result.scalar_one_or_none()

    if digest is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Digest '{digest_id}' not found.",
        )

    return DigestRead.model_validate(digest)


@router.post(
    "",
    summary="Create a new digest",
    description="Triggers creation of a new digest with status 'pending'.",
    response_model=DigestRead,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(verify_api_key)],
)
async def create_digest(
    body: DigestCreate,
    session: AsyncSession = Depends(get_db_session),
) -> DigestRead:
    """Create a new pending digest for the given topic and date.

    If no ``run_date`` is provided the current date is used. The digest
    is returned with status ``pending`` and zero papers.

    Args:
        body: Request body with topic_id and optional run_date.
        session: Injected database session.

    Returns:
        The newly created digest.
    """
    run_date = body.run_date or datetime.datetime.now(tz=datetime.UTC).date()

    # Check for existing digest with the same topic + date
    existing_query = select(Digest).where(
        Digest.topic_id == body.topic_id,
        Digest.run_date == run_date,
    )
    existing_result = await session.execute(existing_query)
    existing = existing_result.scalar_one_or_none()

    if existing is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                f"Digest for topic '{body.topic_id}' on {run_date.isoformat()} already exists."
            ),
        )

    digest = Digest(
        topic_id=body.topic_id,
        run_date=run_date,
        status="pending",
        paper_count=0,
    )
    session.add(digest)
    await session.flush()

    # Reload with papers relationship for a complete response
    reload_query = (
        select(Digest)
        .options(selectinload(Digest.papers))
        .where(Digest.id == digest.id)
    )
    reload_result = await session.execute(reload_query)
    loaded_digest = reload_result.scalar_one()

    logger.info(
        "digest.created",
        digest_id=loaded_digest.id,
        topic_id=loaded_digest.topic_id,
        run_date=str(loaded_digest.run_date),
    )

    return DigestRead.model_validate(loaded_digest)

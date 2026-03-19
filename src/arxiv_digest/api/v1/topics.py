"""Topic configuration endpoints.

Exposes the research topics defined in ``config/topics.yaml`` as read-only
API resources.
"""

from __future__ import annotations

import structlog
from fastapi import APIRouter, HTTPException, status

from arxiv_digest.schemas.topic import TopicSchema, load_topics

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)

router = APIRouter(prefix="/topics", tags=["topics"])


@router.get(
    "",
    summary="List all topics",
    description="Returns every research topic loaded from the YAML configuration.",
    response_model=list[TopicSchema],
)
async def list_topics() -> list[TopicSchema]:
    """Return all configured research topics."""
    try:
        return load_topics()
    except FileNotFoundError:
        logger.exception("topics.file_not_found")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Topics configuration file not found.",
        ) from None
    except Exception:
        logger.exception("topics.load_error")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to load topics configuration.",
        ) from None


@router.get(
    "/{topic_id}",
    summary="Get a single topic",
    description="Returns the topic matching the given identifier, or 404 if not found.",
    response_model=TopicSchema,
)
async def get_topic(topic_id: str) -> TopicSchema:
    """Return a single topic by its identifier.

    Args:
        topic_id: The unique topic identifier to look up.

    Raises:
        HTTPException: 404 if no topic matches the given identifier.
    """
    try:
        topics = load_topics()
    except FileNotFoundError:
        logger.exception("topics.file_not_found")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Topics configuration file not found.",
        ) from None
    except Exception:
        logger.exception("topics.load_error")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to load topics configuration.",
        ) from None

    for topic in topics:
        if topic.id == topic_id:
            return topic

    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail=f"Topic '{topic_id}' not found.",
    )

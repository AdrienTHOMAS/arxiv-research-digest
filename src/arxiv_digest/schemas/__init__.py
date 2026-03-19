"""Pydantic v2 schemas for the ArXiv Research Digest API.

Re-exports all schema classes for convenient importing::

    from arxiv_digest.schemas import PaperRead, DigestRead, PaginatedResponse
"""

from arxiv_digest.schemas.common import PaginatedResponse
from arxiv_digest.schemas.digest import (
    DigestBase,
    DigestBrief,
    DigestCreate,
    DigestRead,
    DigestStatus,
)
from arxiv_digest.schemas.paper import PaperBase, PaperBrief, PaperCreate, PaperRead
from arxiv_digest.schemas.run_log import RunLogBase, RunLogCreate, RunLogRead, RunLogStatus
from arxiv_digest.schemas.topic import TopicSchema, load_topics
from arxiv_digest.schemas.webhook import (
    WebhookDeliveryBase,
    WebhookDeliveryCreate,
    WebhookDeliveryRead,
)

__all__ = [
    "DigestBase",
    "DigestBrief",
    "DigestCreate",
    "DigestRead",
    "DigestStatus",
    "PaginatedResponse",
    "PaperBase",
    "PaperBrief",
    "PaperCreate",
    "PaperRead",
    "RunLogBase",
    "RunLogCreate",
    "RunLogRead",
    "RunLogStatus",
    "TopicSchema",
    "WebhookDeliveryBase",
    "WebhookDeliveryCreate",
    "WebhookDeliveryRead",
    "load_topics",
]

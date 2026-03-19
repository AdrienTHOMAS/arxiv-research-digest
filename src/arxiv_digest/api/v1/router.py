"""Main v1 API router aggregating all sub-routers.

Includes health, topics, digests, and papers endpoints under a unified
``/api/v1`` prefix managed by :mod:`arxiv_digest.main`.
"""

from __future__ import annotations

from fastapi import APIRouter

from arxiv_digest.api.v1.digests import router as digests_router
from arxiv_digest.api.v1.health import router as health_router
from arxiv_digest.api.v1.papers import router as papers_router
from arxiv_digest.api.v1.topics import router as topics_router

router = APIRouter()

router.include_router(health_router)
router.include_router(topics_router)
router.include_router(digests_router)
router.include_router(papers_router)

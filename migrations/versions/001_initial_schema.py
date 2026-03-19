"""Initial schema — papers, digests, webhook_deliveries, run_logs.

Revision ID: 0001
Revises:
Create Date: 2026-03-19
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import sqlalchemy as sa
from alembic import op

if TYPE_CHECKING:
    from collections.abc import Sequence

revision: str = "0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create all initial tables with indexes, constraints, and foreign keys."""
    # ── digests ──────────────────────────────────────────────────────────
    op.create_table(
        "digests",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("topic_id", sa.String(100), nullable=False),
        sa.Column("run_date", sa.Date(), nullable=False),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column("paper_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("status", sa.String(20), nullable=False, server_default="pending"),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.CheckConstraint(
            "status IN ('pending', 'complete', 'failed')",
            name="ck_digests_status_valid",
        ),
        sa.UniqueConstraint("topic_id", "run_date", name="uq_digests_topic_id_run_date"),
        sa.PrimaryKeyConstraint("id", name="pk_digests"),
    )
    op.create_index("ix_digests_topic_id", "digests", ["topic_id"])

    # ── papers ───────────────────────────────────────────────────────────
    op.create_table(
        "papers",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("arxiv_id", sa.String(50), nullable=False),
        sa.Column("title", sa.String(1000), nullable=False),
        sa.Column("authors", sa.JSON(), nullable=False),
        sa.Column("abstract", sa.Text(), nullable=False),
        sa.Column("published_date", sa.Date(), nullable=False),
        sa.Column("categories", sa.JSON(), nullable=False),
        sa.Column("pdf_url", sa.String(500), nullable=False),
        sa.Column("relevance_score", sa.Float(), nullable=True),
        sa.Column("topic_id", sa.String(100), nullable=False),
        sa.Column(
            "digest_id",
            sa.String(36),
            sa.ForeignKey("digests.id", name="fk_papers_digest_id_digests"),
            nullable=True,
        ),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.CheckConstraint(
            "relevance_score IS NULL OR (relevance_score >= 0.0 AND relevance_score <= 1.0)",
            name="ck_papers_relevance_score_range",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_papers"),
    )
    op.create_index("ix_papers_arxiv_id", "papers", ["arxiv_id"], unique=True)
    op.create_index("ix_papers_topic_id", "papers", ["topic_id"])
    op.create_index("ix_papers_digest_id", "papers", ["digest_id"])

    # ── webhook_deliveries ───────────────────────────────────────────────
    op.create_table(
        "webhook_deliveries",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "digest_id",
            sa.String(36),
            sa.ForeignKey("digests.id", name="fk_webhook_deliveries_digest_id_digests"),
            nullable=False,
        ),
        sa.Column("url", sa.String(2000), nullable=False),
        sa.Column("status_code", sa.Integer(), nullable=True),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("attempt", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("success", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_webhook_deliveries"),
    )
    op.create_index(
        "ix_webhook_deliveries_digest_id",
        "webhook_deliveries",
        ["digest_id"],
    )

    # ── run_logs ─────────────────────────────────────────────────────────
    op.create_table(
        "run_logs",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("run_date", sa.Date(), nullable=False),
        sa.Column("topic_id", sa.String(100), nullable=False),
        sa.Column("papers_found", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("papers_filtered", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("duration_seconds", sa.Float(), nullable=False, server_default="0.0"),
        sa.Column("status", sa.String(20), nullable=False, server_default="pending"),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.CheckConstraint(
            "status IN ('pending', 'running', 'complete', 'failed')",
            name="ck_run_logs_status_valid",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_run_logs"),
    )
    op.create_index("ix_run_logs_topic_id", "run_logs", ["topic_id"])


def downgrade() -> None:
    """Drop all tables in reverse dependency order."""
    op.drop_table("run_logs")
    op.drop_table("webhook_deliveries")
    op.drop_table("papers")
    op.drop_table("digests")

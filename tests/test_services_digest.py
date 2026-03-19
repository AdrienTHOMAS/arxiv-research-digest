"""Tests for the DigestService orchestration layer."""

from __future__ import annotations

import sys
from typing import TYPE_CHECKING
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from arxiv_digest.models.run_log import RunLog

if TYPE_CHECKING:
    pass

# Ensure the agent.loop module is importable even without the anthropic SDK.
# We inject a fake module so the lazy import inside DigestService.run_digest
# resolves without pulling in heavy dependencies.
_fake_loop = MagicMock()
_fake_agent = MagicMock()
_fake_agent.loop = _fake_loop
sys.modules.setdefault("anthropic", MagicMock())
sys.modules.setdefault("arxiv_digest.agent", _fake_agent)
sys.modules.setdefault("arxiv_digest.agent.loop", _fake_loop)
sys.modules.setdefault("arxiv_digest.agent.prompts", MagicMock())
sys.modules.setdefault("arxiv_digest.agent.tools_def", MagicMock())

from arxiv_digest.services.digest_service import DigestService  # noqa: E402


# ── Fixtures ────────────────────────────────────────────────────────────


@pytest.fixture
def mock_db_session() -> AsyncMock:
    """Return a mock AsyncSession that tracks added objects."""
    session = AsyncMock()
    added: list[object] = []

    def _track_add(obj: object) -> None:
        added.append(obj)

    # session.add is synchronous in SQLAlchemy, so use a regular MagicMock
    session.add = MagicMock(side_effect=_track_add)
    session._added = added  # type: ignore[attr-defined]
    return session


@pytest.fixture
def mock_agent_loop_result() -> dict[str, object]:
    """Return a realistic agent loop result dict."""
    return {
        "content": "# Weekly ML Digest\n\nSummary of papers...",
        "digest_id": "d-1234-5678",
        "total_tool_calls": 5,
        "duration_seconds": 12.5,
        "tokens_used": 3000,
        "file_path": "/tmp/digest.md",
        "papers_found": 20,
        "papers_filtered": 8,
        "paper_count": 8,
    }


# ── Tests ───────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_run_digest_success(
    mock_db_session: AsyncMock,
    mock_agent_loop_result: dict[str, object],
) -> None:
    """A successful digest run creates a RunLog with status 'complete'."""
    mock_loop = AsyncMock(return_value=mock_agent_loop_result)

    with (
        patch(
            "arxiv_digest.agent.loop.run_agent_loop",
            mock_loop,
        ),
        patch(
            "arxiv_digest.services.digest_service.get_settings",
        ) as mock_settings,
    ):
        mock_settings.return_value = MagicMock(WEBHOOK_URLS=[])

        service = DigestService(db=mock_db_session)
        result = await service.run_digest(topic_id="machine_learning")

    # Agent loop was called with correct args
    mock_loop.assert_awaited_once_with(
        topic_id="machine_learning",
        digest_format="newsletter",
        db=mock_db_session,
        days_back=3,
    )

    # RunLog was created and updated
    run_logs = [obj for obj in mock_db_session._added if isinstance(obj, RunLog)]
    assert len(run_logs) == 1

    run_log = run_logs[0]
    assert run_log.status == "complete"
    assert run_log.topic_id == "machine_learning"
    assert run_log.papers_found == 20
    assert run_log.papers_filtered == 8
    assert run_log.duration_seconds == 12.5

    # Result includes run_log_id
    assert "run_log_id" in result
    assert result["content"] == mock_agent_loop_result["content"]


@pytest.mark.asyncio
async def test_run_digest_failure(
    mock_db_session: AsyncMock,
) -> None:
    """A failed agent loop sets RunLog status to 'failed' with error message."""
    mock_loop = AsyncMock(side_effect=RuntimeError("Claude API timeout"))

    with patch(
        "arxiv_digest.agent.loop.run_agent_loop",
        mock_loop,
    ):
        service = DigestService(db=mock_db_session)

        with pytest.raises(RuntimeError, match="Claude API timeout"):
            await service.run_digest(topic_id="nlp")

    # RunLog was created and marked failed
    run_logs = [obj for obj in mock_db_session._added if isinstance(obj, RunLog)]
    assert len(run_logs) == 1

    run_log = run_logs[0]
    assert run_log.status == "failed"
    assert run_log.error == "Claude API timeout"
    assert run_log.topic_id == "nlp"


@pytest.mark.asyncio
async def test_run_digest_triggers_webhooks(
    mock_db_session: AsyncMock,
    mock_agent_loop_result: dict[str, object],
) -> None:
    """Webhook delivery is triggered for each configured WEBHOOK_URL."""
    webhook_urls = [
        "https://hooks.slack.com/services/T00/B00/xxx",
        "https://discord.com/api/webhooks/123/abc",
    ]

    mock_loop = AsyncMock(return_value=mock_agent_loop_result)

    with (
        patch(
            "arxiv_digest.agent.loop.run_agent_loop",
            mock_loop,
        ),
        patch(
            "arxiv_digest.services.digest_service.get_settings",
        ) as mock_settings,
        patch(
            "arxiv_digest.services.digest_service.WebhookService",
        ) as mock_webhook_cls,
    ):
        mock_settings.return_value = MagicMock(WEBHOOK_URLS=webhook_urls)
        mock_webhook_instance = AsyncMock()
        mock_webhook_cls.return_value = mock_webhook_instance

        service = DigestService(db=mock_db_session)
        await service.run_digest(topic_id="machine_learning")

    # WebhookService.deliver called once per URL
    assert mock_webhook_instance.deliver.await_count == 2

    delivered_urls = [
        call.kwargs["url"]
        for call in mock_webhook_instance.deliver.await_args_list
    ]
    assert webhook_urls[0] in delivered_urls
    assert webhook_urls[1] in delivered_urls


@pytest.mark.asyncio
async def test_run_all_topics(
    mock_db_session: AsyncMock,
    mock_agent_loop_result: dict[str, object],
) -> None:
    """run_all_topics calls run_digest for every topic from load_topics."""
    from arxiv_digest.schemas.topic import TopicSchema

    fake_topics = [
        TopicSchema(
            id="ml",
            name="ML",
            description="Machine Learning",
            arxiv_categories=["cs.LG"],
            keywords=["ml"],
            max_papers=10,
        ),
        TopicSchema(
            id="nlp",
            name="NLP",
            description="Natural Language Processing",
            arxiv_categories=["cs.CL"],
            keywords=["nlp"],
            max_papers=10,
        ),
    ]

    mock_loop = AsyncMock(return_value=mock_agent_loop_result)

    with (
        patch(
            "arxiv_digest.services.digest_service.load_topics",
            return_value=fake_topics,
        ),
        patch(
            "arxiv_digest.agent.loop.run_agent_loop",
            mock_loop,
        ),
        patch(
            "arxiv_digest.services.digest_service.get_settings",
        ) as mock_settings,
    ):
        mock_settings.return_value = MagicMock(WEBHOOK_URLS=[])

        service = DigestService(db=mock_db_session)
        results = await service.run_all_topics(format="newsletter")

    assert len(results) == 2
    assert mock_loop.await_count == 2

    called_topic_ids = [call.kwargs["topic_id"] for call in mock_loop.await_args_list]
    assert called_topic_ids == ["ml", "nlp"]

"""Tests for the webhook delivery service."""

from __future__ import annotations

import datetime
from typing import TYPE_CHECKING
from unittest.mock import AsyncMock, patch

import httpx

from arxiv_digest.models.digest import Digest
from arxiv_digest.services.webhook_service import (
    WebhookService,
    _format_discord_payload,
    _format_slack_payload,
    _is_discord_url,
    _is_slack_url,
)

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

_POST_REQ = httpx.Request("POST", "https://x.co")


async def _create_digest(db_session: AsyncSession) -> str:
    """Insert a digest record and return its ID for FK references."""
    digest = Digest(
        topic_id="test_topic",
        run_date=datetime.date(2024, 1, 15),
        status="complete",
        paper_count=5,
    )
    db_session.add(digest)
    await db_session.flush()
    return str(digest.id)


def test_is_slack_url() -> None:
    """_is_slack_url correctly identifies Slack webhook URLs."""
    assert _is_slack_url("https://hooks.slack.com/services/T00/B00/xxx") is True
    assert _is_slack_url("https://example.slack.com/webhook") is True
    assert _is_slack_url("https://example.com/webhook") is False
    assert _is_slack_url("https://discord.com/api/webhooks/123") is False


def test_is_discord_url() -> None:
    """_is_discord_url correctly identifies Discord webhook URLs."""
    assert _is_discord_url("https://discord.com/api/webhooks/123/abc") is True
    assert _is_discord_url("https://discordapp.discord.com/webhook") is True
    assert _is_discord_url("https://hooks.slack.com/services/T00/B00/xxx") is False
    assert _is_discord_url("https://example.com/webhook") is False


def test_format_slack_payload() -> None:
    """_format_slack_payload produces valid Slack block-kit structure."""
    payload: dict[str, object] = {
        "title": "Test Digest",
        "summary": "Some summary text",
        "paper_count": 5,
    }

    result = _format_slack_payload(payload)

    assert "blocks" in result
    blocks = result["blocks"]
    assert isinstance(blocks, list)
    assert len(blocks) == 3

    header = blocks[0]
    assert header["type"] == "header"
    assert header["text"]["text"] == "Test Digest"

    section = blocks[1]
    assert section["type"] == "section"
    assert section["text"]["text"] == "Some summary text"

    context = blocks[2]
    assert context["type"] == "context"


def test_format_slack_payload_defaults() -> None:
    """_format_slack_payload uses defaults for missing fields."""
    result = _format_slack_payload({})

    blocks = result["blocks"]
    assert blocks[0]["text"]["text"] == "ArXiv Research Digest"
    assert blocks[1]["text"]["text"] == "_No summary available._"


def test_format_discord_payload() -> None:
    """_format_discord_payload produces valid Discord embed structure."""
    payload: dict[str, object] = {
        "title": "Test Digest",
        "summary": "Some summary text",
        "paper_count": 3,
    }

    result = _format_discord_payload(payload)

    assert "embeds" in result
    embeds = result["embeds"]
    assert isinstance(embeds, list)
    assert len(embeds) == 1

    embed = embeds[0]
    assert embed["title"] == "Test Digest"
    assert embed["description"] == "Some summary text"
    assert embed["color"] == 3447003

    fields = embed["fields"]
    assert isinstance(fields, list)
    assert fields[0]["name"] == "Papers"
    assert fields[0]["value"] == "3"


def test_format_discord_payload_defaults() -> None:
    """_format_discord_payload uses defaults for missing fields."""
    result = _format_discord_payload({})

    embed = result["embeds"][0]
    assert embed["title"] == "ArXiv Research Digest"
    assert embed["description"] == "No summary available."


async def test_deliver_success(db_session: AsyncSession) -> None:
    """WebhookService.deliver() succeeds on first attempt with 200 response."""
    digest_id = await _create_digest(db_session)
    mock_response = httpx.Response(status_code=200, request=_POST_REQ)

    service = WebhookService(session=db_session)

    with patch("arxiv_digest.services.webhook_service.httpx.AsyncClient") as mock_client_cls:
        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client_cls.return_value = mock_client

        delivery = await service.deliver(
            digest_id=digest_id,
            url="https://example.com/webhook",
            payload={"title": "Test", "summary": "test"},
        )

    assert delivery.success is True
    assert delivery.attempt == 1
    assert delivery.status_code == 200
    assert delivery.error is None


async def test_deliver_retry_then_success(db_session: AsyncSession) -> None:
    """WebhookService.deliver() retries on failure and succeeds on subsequent attempt."""
    digest_id = await _create_digest(db_session)
    fail_response = httpx.Response(status_code=500, text="Server Error", request=_POST_REQ)
    ok_response = httpx.Response(status_code=200, request=_POST_REQ)

    service = WebhookService(session=db_session)

    with (
        patch("arxiv_digest.services.webhook_service.httpx.AsyncClient") as mock_client_cls,
        patch(
            "arxiv_digest.services.webhook_service.asyncio.sleep",
            new_callable=AsyncMock,
        ) as mock_sleep,
    ):
        mock_client = AsyncMock()
        mock_client.post = AsyncMock(side_effect=[fail_response, ok_response])
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client_cls.return_value = mock_client

        delivery = await service.deliver(
            digest_id=digest_id,
            url="https://example.com/webhook",
            payload={"title": "Test"},
        )

    assert delivery.success is True
    assert delivery.attempt == 2
    mock_sleep.assert_called_once_with(1.0)


async def test_deliver_max_attempts_exceeded(db_session: AsyncSession) -> None:
    """WebhookService.deliver() records failure after max attempts."""
    digest_id = await _create_digest(db_session)
    fail_response = httpx.Response(status_code=500, text="Server Error", request=_POST_REQ)

    service = WebhookService(session=db_session)

    with (
        patch("arxiv_digest.services.webhook_service.httpx.AsyncClient") as mock_client_cls,
        patch("arxiv_digest.services.webhook_service.asyncio.sleep", new_callable=AsyncMock),
    ):
        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=fail_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client_cls.return_value = mock_client

        delivery = await service.deliver(
            digest_id=digest_id,
            url="https://example.com/webhook",
            payload={"title": "Test"},
        )

    assert delivery.success is False
    assert delivery.attempt == 3
    assert delivery.status_code == 500
    assert delivery.error is not None
    assert "500" in delivery.error


async def test_deliver_timeout_retry(db_session: AsyncSession) -> None:
    """WebhookService.deliver() handles timeout exceptions with retry."""
    digest_id = await _create_digest(db_session)
    ok_response = httpx.Response(status_code=200, request=_POST_REQ)

    service = WebhookService(session=db_session)

    with (
        patch("arxiv_digest.services.webhook_service.httpx.AsyncClient") as mock_client_cls,
        patch("arxiv_digest.services.webhook_service.asyncio.sleep", new_callable=AsyncMock),
    ):
        mock_client = AsyncMock()
        mock_client.post = AsyncMock(
            side_effect=[httpx.TimeoutException("timed out"), ok_response],
        )
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client_cls.return_value = mock_client

        delivery = await service.deliver(
            digest_id=digest_id,
            url="https://example.com/webhook",
            payload={"title": "Test"},
        )

    assert delivery.success is True
    assert delivery.attempt == 2


async def test_deliver_exponential_backoff(db_session: AsyncSession) -> None:
    """WebhookService.deliver() uses exponential backoff between retries."""
    digest_id = await _create_digest(db_session)
    fail_response = httpx.Response(status_code=503, text="Unavailable", request=_POST_REQ)

    service = WebhookService(session=db_session)

    with (
        patch("arxiv_digest.services.webhook_service.httpx.AsyncClient") as mock_client_cls,
        patch(
            "arxiv_digest.services.webhook_service.asyncio.sleep",
            new_callable=AsyncMock,
        ) as mock_sleep,
    ):
        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=fail_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client_cls.return_value = mock_client

        await service.deliver(
            digest_id=digest_id,
            url="https://example.com/webhook",
            payload={"title": "Test"},
        )

    # Expect two sleep calls: 1.0s after attempt 1, 2.0s after attempt 2
    assert mock_sleep.call_count == 2
    calls = [c.args[0] for c in mock_sleep.call_args_list]
    assert calls == [1.0, 2.0]


async def test_deliver_slack_format(db_session: AsyncSession) -> None:
    """WebhookService.deliver() formats payload for Slack URLs."""
    digest_id = await _create_digest(db_session)
    mock_response = httpx.Response(status_code=200, request=_POST_REQ)

    service = WebhookService(session=db_session)

    with patch("arxiv_digest.services.webhook_service.httpx.AsyncClient") as mock_client_cls:
        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client_cls.return_value = mock_client

        delivery = await service.deliver(
            digest_id=digest_id,
            url="https://hooks.slack.com/services/T00/B00/xxx",
            payload={"title": "Slack Test", "summary": "test", "paper_count": 2},
        )

    assert delivery.success is True
    # Verify the payload was formatted for Slack
    assert "blocks" in delivery.payload


async def test_deliver_discord_format(db_session: AsyncSession) -> None:
    """WebhookService.deliver() formats payload for Discord URLs."""
    digest_id = await _create_digest(db_session)
    mock_response = httpx.Response(status_code=204, request=_POST_REQ)

    service = WebhookService(session=db_session)

    with patch("arxiv_digest.services.webhook_service.httpx.AsyncClient") as mock_client_cls:
        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client_cls.return_value = mock_client

        delivery = await service.deliver(
            digest_id=digest_id,
            url="https://discord.com/api/webhooks/123/abc",
            payload={"title": "Discord Test", "summary": "test", "paper_count": 1},
        )

    assert delivery.success is True
    assert "embeds" in delivery.payload

"""Webhook delivery service with retry logic and platform-specific formatting.

Supports Slack block-kit payloads, Discord embeds, and generic HTTP POST
delivery with exponential backoff retries.
"""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

import httpx
import structlog

from arxiv_digest.models.webhook import WebhookDelivery

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)

_MAX_ATTEMPTS: int = 3
_BASE_DELAY_SECONDS: float = 1.0
_REQUEST_TIMEOUT_SECONDS: float = 10.0


def _is_slack_url(url: str) -> bool:
    """Determine whether a URL points to a Slack webhook."""
    return "slack.com" in url.lower()


def _is_discord_url(url: str) -> bool:
    """Determine whether a URL points to a Discord webhook."""
    return "discord.com" in url.lower()


def _format_slack_payload(payload: dict[str, object]) -> dict[str, object]:
    """Format a generic payload as Slack block-kit message.

    Args:
        payload: The original payload to format.

    Returns:
        A Slack-compatible block-kit message dict.
    """
    title = str(payload.get("title", "ArXiv Research Digest"))
    summary = str(payload.get("summary", ""))
    paper_count = payload.get("paper_count", 0)

    blocks: list[dict[str, object]] = [
        {
            "type": "header",
            "text": {
                "type": "plain_text",
                "text": title,
            },
        },
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": summary if summary else "_No summary available._",
            },
        },
        {
            "type": "context",
            "elements": [
                {
                    "type": "mrkdwn",
                    "text": f"Papers included: *{paper_count}*",
                },
            ],
        },
    ]

    return {"blocks": blocks}


def _format_discord_payload(payload: dict[str, object]) -> dict[str, object]:
    """Format a generic payload as a Discord embed message.

    Args:
        payload: The original payload to format.

    Returns:
        A Discord-compatible webhook message dict.
    """
    title = str(payload.get("title", "ArXiv Research Digest"))
    summary = str(payload.get("summary", ""))
    paper_count = payload.get("paper_count", 0)

    embed: dict[str, object] = {
        "title": title,
        "description": summary if summary else "No summary available.",
        "color": 3447003,
        "fields": [
            {
                "name": "Papers",
                "value": str(paper_count),
                "inline": True,
            },
        ],
    }

    return {"embeds": [embed]}


class WebhookService:
    """Delivers digest notifications to external webhook endpoints.

    Supports Slack, Discord, and generic HTTP POST targets with automatic
    retry on transient failures using exponential backoff.

    Args:
        session: An active async database session for persisting delivery records.
    """

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def deliver(
        self,
        digest_id: str,
        url: str,
        payload: dict[str, object],
    ) -> WebhookDelivery:
        """Send a webhook notification with retry logic.

        Makes up to 3 attempts with exponential backoff (1s, 2s, 4s) before
        recording the final result. Each attempt is logged for observability.

        Args:
            digest_id: UUID of the digest being delivered.
            url: The target webhook URL.
            payload: The JSON payload to deliver.

        Returns:
            The :class:`WebhookDelivery` database record capturing the outcome.
        """
        formatted_payload = self._format_for_platform(url, payload)

        delivery = WebhookDelivery(
            digest_id=digest_id,
            url=url,
            payload=formatted_payload,
            attempt=0,
            success=False,
        )

        last_error: str | None = None
        last_status_code: int | None = None

        async with httpx.AsyncClient(timeout=_REQUEST_TIMEOUT_SECONDS) as client:
            for attempt in range(1, _MAX_ATTEMPTS + 1):
                delivery.attempt = attempt

                logger.info(
                    "webhook.attempt",
                    digest_id=digest_id,
                    url=url,
                    attempt=attempt,
                )

                try:
                    response = await client.post(
                        url,
                        json=formatted_payload,
                        headers={"Content-Type": "application/json"},
                    )
                    last_status_code = response.status_code

                    if 200 <= response.status_code < 300:  # noqa: PLR2004
                        delivery.success = True
                        delivery.status_code = response.status_code
                        delivery.error = None

                        logger.info(
                            "webhook.success",
                            digest_id=digest_id,
                            url=url,
                            attempt=attempt,
                            status_code=response.status_code,
                        )
                        break

                    last_error = f"HTTP {response.status_code}: {response.text[:500]}"
                    logger.warning(
                        "webhook.http_error",
                        digest_id=digest_id,
                        url=url,
                        attempt=attempt,
                        status_code=response.status_code,
                    )

                except httpx.TimeoutException:
                    last_error = "Request timed out."
                    logger.warning(
                        "webhook.timeout",
                        digest_id=digest_id,
                        url=url,
                        attempt=attempt,
                    )

                except httpx.ConnectError:
                    last_error = "Connection failed."
                    logger.warning(
                        "webhook.connect_error",
                        digest_id=digest_id,
                        url=url,
                        attempt=attempt,
                    )

                except httpx.HTTPError as exc:
                    last_error = f"HTTP error: {exc}"
                    logger.warning(
                        "webhook.http_client_error",
                        digest_id=digest_id,
                        url=url,
                        attempt=attempt,
                        error=str(exc),
                    )

                if attempt < _MAX_ATTEMPTS:
                    delay = _BASE_DELAY_SECONDS * (2 ** (attempt - 1))
                    logger.info(
                        "webhook.retry_delay",
                        digest_id=digest_id,
                        delay_seconds=delay,
                        next_attempt=attempt + 1,
                    )
                    await asyncio.sleep(delay)

        if not delivery.success:
            delivery.status_code = last_status_code
            delivery.error = last_error
            logger.error(
                "webhook.failed",
                digest_id=digest_id,
                url=url,
                attempts=_MAX_ATTEMPTS,
                error=last_error,
            )

        self._session.add(delivery)
        await self._session.flush()

        return delivery

    @staticmethod
    def _format_for_platform(
        url: str,
        payload: dict[str, object],
    ) -> dict[str, object]:
        """Select and apply the appropriate payload formatter for the target URL.

        Args:
            url: The webhook endpoint URL.
            payload: The raw payload to format.

        Returns:
            A platform-specific formatted payload.
        """
        if _is_slack_url(url):
            return _format_slack_payload(payload)
        if _is_discord_url(url):
            return _format_discord_payload(payload)
        return payload

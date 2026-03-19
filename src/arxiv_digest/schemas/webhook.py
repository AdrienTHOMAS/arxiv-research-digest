"""Pydantic v2 schemas for WebhookDelivery resources."""

import datetime

from pydantic import BaseModel, ConfigDict, Field


class WebhookDeliveryBase(BaseModel):
    """Shared fields for webhook delivery schemas.

    Attributes:
        digest_id: UUID of the digest being delivered.
        url: Webhook endpoint URL.
        payload: JSON payload sent in the request.
        attempt: Delivery attempt number.
        success: Whether the delivery succeeded.
        status_code: HTTP status code from the endpoint.
        error: Error message on failure.
    """

    digest_id: str = Field(description="UUID of the digest being delivered.")
    url: str = Field(max_length=2000, description="Webhook endpoint URL.")
    payload: dict[str, object] = Field(description="JSON payload sent.")
    attempt: int = Field(default=1, ge=1, description="Delivery attempt number.")
    success: bool = Field(default=False, description="Whether delivery succeeded.")
    status_code: int | None = Field(default=None, description="HTTP status code.")
    error: str | None = Field(default=None, description="Error message on failure.")


class WebhookDeliveryCreate(BaseModel):
    """Schema for creating a new webhook delivery record."""

    digest_id: str = Field(description="UUID of the digest being delivered.")
    url: str = Field(max_length=2000, description="Webhook endpoint URL.")
    payload: dict[str, object] = Field(description="JSON payload to send.")


class WebhookDeliveryRead(WebhookDeliveryBase):
    """Schema for reading a webhook delivery from the database."""

    model_config = ConfigDict(from_attributes=True)

    id: str = Field(description="UUID primary key.")
    created_at: datetime.datetime = Field(description="Record creation timestamp (UTC).")
    updated_at: datetime.datetime = Field(description="Last update timestamp (UTC).")

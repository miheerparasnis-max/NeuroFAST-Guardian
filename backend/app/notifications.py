from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol
from uuid import UUID, uuid4


@dataclass(frozen=True)
class NotificationMessage:
    assessment_id: UUID
    trusted_contact_id: UUID
    body: str


@dataclass(frozen=True)
class DeliveryResult:
    id: UUID
    mode: str
    status: str


class NotificationProvider(Protocol):
    def deliver(self, message: NotificationMessage) -> DeliveryResult: ...


class PreviewNotificationProvider:
    """Safe default: records a preview result and never sends a message."""

    def deliver(self, message: NotificationMessage) -> DeliveryResult:
        _ = message
        return DeliveryResult(id=uuid4(), mode="preview_only", status="not_sent")


class NotificationDispatcher:
    def __init__(self, provider: NotificationProvider):
        self.provider = provider

    def deliver(self, message: NotificationMessage) -> DeliveryResult:
        return self.provider.deliver(message)

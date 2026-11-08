from uuid import uuid4

from app.notifications import NotificationDispatcher, NotificationMessage, PreviewNotificationProvider


def test_preview_provider_never_sends() -> None:
    result = NotificationDispatcher(PreviewNotificationProvider()).deliver(
        NotificationMessage(
            assessment_id=uuid4(),
            trusted_contact_id=uuid4(),
            body="Possible neurological emergency reported.",
        )
    )
    assert result.mode == "preview_only"
    assert result.status == "not_sent"

"""Apply triage actions to Gmail messages (labels, archive, read)."""

from typing import Any

from src.gmail.client import get_gmail_service, modify_labels
from src.models import User

SYSTEM_LABELS = frozenset(
    {
        "INBOX",
        "UNREAD",
        "IMPORTANT",
        "STARRED",
        "TRASH",
        "SPAM",
        "SENT",
        "DRAFT",
        "CATEGORY_PERSONAL",
        "CATEGORY_SOCIAL",
        "CATEGORY_PROMOTIONS",
        "CATEGORY_UPDATES",
        "CATEGORY_FORUMS",
    }
)


def ensure_label(user: User, label_name: str) -> str:
    """Return the Gmail label ID for a user label, creating it if needed."""
    if label_name in SYSTEM_LABELS:
        return label_name

    service = get_gmail_service(user)
    existing = service.users().labels().list(userId="me").execute()
    for label in existing.get("labels", []):
        if label.get("name") == label_name:
            return label["id"]

    created = (
        service.users()
        .labels()
        .create(
            userId="me",
            body={
                "name": label_name,
                "labelListVisibility": "labelShow",
                "messageListVisibility": "show",
            },
        )
        .execute()
    )
    return created["id"]


def _resolve_label_ids(user: User, labels: list[str]) -> list[str]:
    return [ensure_label(user, label) for label in labels]


def archive_message(user: User, message_id: str) -> dict[str, Any]:
    """Remove a message from INBOX."""
    return modify_labels(user, message_id, remove_labels=["INBOX"])


def mark_read(user: User, message_id: str) -> dict[str, Any]:
    """Mark a message as read."""
    return modify_labels(user, message_id, remove_labels=["UNREAD"])


def mark_unimportant(user: User, message_id: str) -> dict[str, Any]:
    """Remove IMPORTANT from a message."""
    return modify_labels(user, message_id, remove_labels=["IMPORTANT"])


def apply_actions(user: User, message_id: str, actions: dict[str, Any]) -> dict[str, Any]:
    """Apply a classification action payload to a Gmail message.

    Expected shape:
    {
        "add_labels": ["mailresolve/newsletter"],
        "remove_labels": ["INBOX", "UNREAD"],
        "snooze_until": null
    }
    """
    add_labels = actions.get("add_labels") or []
    remove_labels = actions.get("remove_labels") or []
    snooze_until = actions.get("snooze_until")

    if snooze_until is not None:
        raise NotImplementedError("Snooze is implemented in phase 3")

    if not add_labels and not remove_labels:
        return {"message_id": message_id, "modified": False}

    result = modify_labels(
        user,
        message_id,
        add_labels=_resolve_label_ids(user, add_labels),
        remove_labels=_resolve_label_ids(user, remove_labels),
    )
    return {"message_id": message_id, "modified": True, "gmail_response": result}

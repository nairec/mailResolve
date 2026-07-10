"""Incremental Gmail sync via history.list."""

import logging
from dataclasses import dataclass, field
from typing import Any

from googleapiclient.errors import HttpError
from sqlalchemy.orm import Session

from src.gmail.client import get_gmail_service
from src.models import ProcessedMessage, User

logger = logging.getLogger(__name__)


@dataclass
class SyncResult:
    """Outcome of a single incremental sync run."""

    new_message_ids: list[str] = field(default_factory=list)
    latest_history_id: int | None = None


def fetch_history(user: User, start_history_id: int) -> tuple[list[dict[str, Any]], int]:
    """Fetch mailbox change records from Gmail after start_history_id.

    Calls users.history.list with pagination until all pages are consumed.
    Only requests messageAdded events so we focus on new mail (not label tweaks).
    """
    service = get_gmail_service(user)
    history_records: list[dict[str, Any]] = []
    page_token: str | None = None
    latest_history_id = start_history_id

    while True:
        request = service.users().history().list(
            userId="me",
            startHistoryId=str(start_history_id),
            historyTypes=["messageAdded"],
            pageToken=page_token,
        )
        try:
            response = request.execute()
        except HttpError as exc:
            if exc.resp.status == 404:
                raise ValueError(
                    "history_id is too old or invalid; full resync required"
                ) from exc
            raise

        history_records.extend(response.get("history", []))
        if "historyId" in response:
            latest_history_id = int(response["historyId"])

        page_token = response.get("nextPageToken")
        if not page_token:
            break

    return history_records, latest_history_id


def extract_message_ids(history_records: list[dict[str, Any]]) -> list[str]:
    """Collect unique Gmail message IDs from history.list records.

    Walks each history record's messagesAdded entries and deduplicates
    within the batch (the same message can appear in multiple records).
    """
    message_ids: list[str] = []
    seen: set[str] = set()

    for record in history_records:
        for added in record.get("messagesAdded", []):
            message = added.get("message") or {}
            message_id = message.get("id")
            if message_id and message_id not in seen:
                seen.add(message_id)
                message_ids.append(message_id)

    return message_ids


def is_processed(db: Session, user: User, message_id: str) -> bool:
    """Return True if this message was already handled for the user."""
    return (
        db.query(ProcessedMessage)
        .filter(
            ProcessedMessage.user_id == user.id,
            ProcessedMessage.gmail_message_id == message_id,
        )
        .first()
        is not None
    )


def mark_processed(db: Session, user: User, message_id: str) -> None:
    """Record a message as processed so duplicate pushes are skipped."""
    if is_processed(db, user, message_id):
        return

    db.add(
        ProcessedMessage(
            user_id=user.id,
            gmail_message_id=message_id,
        )
    )


def sync_user(
    db: Session,
    user: User,
    notification_history_id: int | None = None,
) -> SyncResult:
    """Run one incremental sync for a user.

    1. Read changes since user.history_id via history.list
    2. Extract new message IDs
    3. Skip IDs already in processed_messages
    4. Mark new IDs as processed (phase 1 stub; classifier runs in phase 2)
    5. Advance user.history_id to the latest known value
    """
    if user.history_id is None:
        raise ValueError(f"User {user.email} has no history_id; activate watch first")

    start_history_id = user.history_id
    history_records, api_latest_history_id = fetch_history(user, start_history_id)
    candidate_ids = extract_message_ids(history_records)

    new_message_ids = [
        message_id
        for message_id in candidate_ids
        if not is_processed(db, user, message_id)
    ]

    for message_id in new_message_ids:
        mark_processed(db, user, message_id)
        logger.info("New message for %s: %s", user.email, message_id)

    latest_history_id = api_latest_history_id
    if notification_history_id is not None:
        latest_history_id = max(latest_history_id, notification_history_id)

    user.history_id = latest_history_id
    db.commit()
    db.refresh(user)

    return SyncResult(
        new_message_ids=new_message_ids,
        latest_history_id=latest_history_id,
    )

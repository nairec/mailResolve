# src/gmail/watch.py

from dataclasses import dataclass
from datetime import UTC, datetime

from googleapiclient.errors import HttpError

from src.core.config import settings
from src.gmail.client import get_gmail_service
from src.models import User

from sqlalchemy.orm import Session


@dataclass
class WatchResult:
    history_id: int
    expires_at: datetime

def persist_watch_state(db: Session, user: User, result: WatchResult) -> User:
    user.history_id = result.history_id
    user.watch_expires_at = result.expires_at
    db.commit()
    db.refresh(user)
    return user

def start_watch(user: User) -> WatchResult:
    if not settings.google_pubsub_topic:
        raise ValueError("GOOGLE_PUBSUB_TOPIC is not configured")

    service = get_gmail_service(user)

    body = {
        "topicName": settings.google_pubsub_topic,
        "labelIds": ["INBOX"],
        "labelFilterBehavior": "include",
    }

    try:
        response = service.users().watch(userId="me", body=body).execute()
    except HttpError as exc:
        if exc.resp.status == 403:
            raise ValueError(
                "Gmail cannot publish to the Pub/Sub topic. "
                "Grant the role 'Pub/Sub Publisher' on the topic to "
                "gmail-api-push@system.gserviceaccount.com"
            ) from exc
        raise ValueError(f"Failed to start watch: {exc}") from exc

    return WatchResult(history_id=int(response["historyId"]), expires_at=datetime.fromtimestamp(int(response["expiration"]) / 1000, tz=UTC))

def stop_watch(user: User) -> None:
    service = get_gmail_service(user)
    service.users().stop(userId="me").execute()

def renew_watch(user: User) -> WatchResult:
    """Gmail renew = call watch() again."""
    return start_watch(user)
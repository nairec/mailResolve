from typing import Any

from google.auth.exceptions import RefreshError
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from src.core.config import settings
from src.core.security import decrypt_token
from src.gmail.oauth import GMAIL_MODIFY_SCOPE
from src.models import User

TOKEN_URI = "https://oauth2.googleapis.com/token"


def get_credentials(user: User) -> Credentials:
    if not user.encrypted_refresh_token:
        raise ValueError(f"No Gmail token stored for user {user.email}")

    refresh_token = decrypt_token(user.encrypted_refresh_token)
    credentials = Credentials(
        token=None,
        refresh_token=refresh_token,
        token_uri=TOKEN_URI,
        client_id=settings.google_client_id,
        client_secret=settings.google_client_secret,
        scopes=[GMAIL_MODIFY_SCOPE],
    )

    if not credentials.valid and credentials.refresh_token:
        credentials.refresh(Request())

    if not credentials.valid:
        raise RefreshError("Invalid credentials; re-authenticate via /auth/login")

    return credentials


def get_gmail_service(user: User):
    return build(
        "gmail",
        "v1",
        credentials=get_credentials(user),
        cache_discovery=False,
    )


def list_messages(
    user: User,
    query: str = "in:inbox",
    max_results: int = 10,
) -> dict[str, Any]:
    service = get_gmail_service(user)
    return (
        service.users()
        .messages()
        .list(userId="me", q=query, maxResults=max_results)
        .execute()
    )


def get_message(
    user: User,
    message_id: str,
    format: str = "metadata",
    metadata_headers: list[str] | None = None,
) -> dict[str, Any]:
    service = get_gmail_service(user)
    headers = metadata_headers or ["From", "Subject", "Date"]
    return (
        service.users()
        .messages()
        .get(
            userId="me",
            id=message_id,
            format=format,
            metadataHeaders=headers,
        )
        .execute()
    )


def modify_labels(
    user: User,
    message_id: str,
    add_labels: list[str] | None = None,
    remove_labels: list[str] | None = None,
) -> dict[str, Any]:
    """Modify Gmail label IDs on a message (e.g. INBOX, UNREAD)."""
    service = get_gmail_service(user)
    body: dict[str, list[str]] = {}
    if add_labels:
        body["addLabelIds"] = add_labels
    if remove_labels:
        body["removeLabelIds"] = remove_labels

    try:
        return service.users().messages().modify(userId="me", id=message_id, body=body).execute()
    except HttpError:
        raise

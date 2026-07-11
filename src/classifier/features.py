"""Feature extraction from Gmail messages for classification."""

import email.utils
from dataclasses import dataclass
from datetime import UTC, datetime

from src.gmail.client import get_message
from src.models import User

CLASSIFICATION_HEADERS = [
    "From",
    "To",
    "Subject",
    "Date",
    "List-Unsubscribe",
    "Precedence",
    "X-Mailer",
    "Auto-Submitted",
]


@dataclass(frozen=True)
class EmailFeatures:
    """Normalized metadata extracted from a Gmail message."""

    message_id: str
    from_email: str
    from_domain: str
    to: str
    subject: str
    snippet: str
    label_ids: tuple[str, ...]
    is_unread: bool
    has_attachment: bool
    internal_date: datetime | None
    list_unsubscribe: str | None
    precedence: str | None
    x_mailer: str | None
    auto_submitted: str | None


def _headers_map(payload: dict) -> dict[str, str]:
    headers: dict[str, str] = {}
    for header in payload.get("headers", []):
        name = header.get("name")
        value = header.get("value")
        if name and value is not None:
            headers[name.lower()] = value
    return headers


def _parse_from_address(from_header: str) -> tuple[str, str]:
    _, address = email.utils.parseaddr(from_header)
    address = address.lower()
    domain = address.split("@", 1)[1] if "@" in address else ""
    return address, domain


def _has_attachment(payload: dict) -> bool:
    if payload.get("filename"):
        return True
    for part in payload.get("parts", []) or []:
        if _has_attachment(part):
            return True
    return False


def _parse_internal_date(raw_message: dict) -> datetime | None:
    internal_date = raw_message.get("internalDate")
    if internal_date is None:
        return None
    return datetime.fromtimestamp(int(internal_date) / 1000, tz=UTC)


def extract_features(user: User, message_id: str) -> EmailFeatures:
    """Fetch Gmail metadata and build an EmailFeatures instance."""
    raw = get_message(
        user,
        message_id,
        format="metadata",
        metadata_headers=CLASSIFICATION_HEADERS,
    )
    headers = _headers_map(raw.get("payload", {}))
    from_header = headers.get("from", "")
    from_email, from_domain = _parse_from_address(from_header)
    label_ids = tuple(raw.get("labelIds", []))

    return EmailFeatures(
        message_id=message_id,
        from_email=from_email,
        from_domain=from_domain,
        to=headers.get("to", ""),
        subject=headers.get("subject", ""),
        snippet=raw.get("snippet", ""),
        label_ids=label_ids,
        is_unread="UNREAD" in label_ids,
        has_attachment=_has_attachment(raw.get("payload", {})),
        internal_date=_parse_internal_date(raw),
        list_unsubscribe=headers.get("list-unsubscribe"),
        precedence=headers.get("precedence"),
        x_mailer=headers.get("x-mailer"),
        auto_submitted=headers.get("auto-submitted"),
    )

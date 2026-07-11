"""Default classification rules seeded on first OAuth login."""

import logging
from typing import Any

from sqlalchemy.orm import Session

from src.models import Rule, User

logger = logging.getLogger(__name__)

DEFAULT_RULES: list[dict[str, Any]] = [
    {
        "name": "newsletter",
        "priority": 10,
        "conditions": {
            "category": "newsletter",
            "header_exists": "List-Unsubscribe",
        },
        "actions": {
            "add_labels": ["mailresolve/newsletter"],
            "remove_labels": ["INBOX", "UNREAD"],
        },
    },
    {
        "name": "dev",
        "priority": 20,
        "conditions": {
            "category": "notification",
            "from_domain_in": ["github.com", "gitlab.com", "bitbucket.org"],
        },
        "actions": {
            "add_labels": ["mailresolve/dev"],
            "remove_labels": ["INBOX"],
        },
    },
    {
        "name": "finance",
        "priority": 30,
        "conditions": {
            "category": "invoice",
            "subject_matches": r"(?i)(invoice|factura|recibo|receipt)",
        },
        "actions": {
            "add_labels": ["mailresolve/finance"],
        },
    },
    {
        "name": "notifications",
        "priority": 40,
        "conditions": {
            "category": "notification",
            "from_matches": r"(?i)noreply|no-reply|notifications",
        },
        "actions": {
            "add_labels": ["mailresolve/notifications"],
            "remove_labels": ["INBOX", "UNREAD"],
        },
    },
    {
        "name": "bulk",
        "priority": 50,
        "conditions": {
            "category": "newsletter",
            "header_equals": {"name": "Precedence", "value": "bulk"},
        },
        "actions": {
            "add_labels": ["mailresolve/bulk"],
            "remove_labels": ["INBOX"],
        },
    },
]


def seed_default_rules(db: Session, user: User) -> int:
    """Insert default rules for a user if they have none yet.

    Idempotent: returns 0 when the user already has any rules.
    """
    existing_count = db.query(Rule).filter(Rule.user_id == user.id).count()
    if existing_count:
        logger.info("Skipping rule seed for %s (%d rules already exist)", user.email, existing_count)
        return 0

    for spec in DEFAULT_RULES:
        db.add(
            Rule(
                user_id=user.id,
                name=spec["name"],
                priority=spec["priority"],
                conditions=spec["conditions"],
                actions=spec["actions"],
                enabled=True,
            )
        )

    db.commit()
    logger.info("Seeded %d default rules for %s", len(DEFAULT_RULES), user.email)
    return len(DEFAULT_RULES)

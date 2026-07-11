import uuid
from unittest.mock import MagicMock

from src.classifier.seed_rules import DEFAULT_RULES, seed_default_rules
from src.models import Rule, User


def test_seed_default_rules_inserts_all_defaults() -> None:
    user = User(id=uuid.uuid4(), email="user@example.com")
    db = MagicMock()
    db.query.return_value.filter.return_value.count.return_value = 0

    seeded = seed_default_rules(db, user)

    assert seeded == len(DEFAULT_RULES)
    assert db.add.call_count == len(DEFAULT_RULES)
    db.commit.assert_called_once()


def test_seed_default_rules_is_idempotent() -> None:
    user = User(id=uuid.uuid4(), email="user@example.com")
    db = MagicMock()
    db.query.return_value.filter.return_value.count.return_value = 3

    seeded = seed_default_rules(db, user)

    assert seeded == 0
    db.add.assert_not_called()
    db.commit.assert_not_called()

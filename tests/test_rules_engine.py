import uuid
from datetime import UTC, datetime

from src.classifier.features import EmailFeatures
from src.classifier.rules_engine import (
    RuleMatch,
    evaluate_rules,
    load_rules,
    match_conditions,
    match_rule,
)
from src.models import Rule, User


def _features(**overrides) -> EmailFeatures:
    defaults = {
        "message_id": "msg-1",
        "from_email": "user@example.com",
        "from_domain": "example.com",
        "to": "me@example.com",
        "subject": "Hello",
        "snippet": "Hello world",
        "label_ids": ("INBOX", "UNREAD"),
        "is_unread": True,
        "has_attachment": False,
        "internal_date": datetime.now(tz=UTC),
        "list_unsubscribe": None,
        "precedence": None,
        "x_mailer": None,
        "auto_submitted": None,
    }
    defaults.update(overrides)
    return EmailFeatures(**defaults)


def test_match_header_exists() -> None:
    features = _features(list_unsubscribe="<mailto:unsub@news.com>")
    assert match_conditions(features, {"header_exists": "List-Unsubscribe"}) is True
    assert match_conditions(_features(), {"header_exists": "List-Unsubscribe"}) is False


def test_match_from_domain_in() -> None:
    features = _features(from_email="noreply@github.com", from_domain="github.com")
    assert match_conditions(features, {"from_domain_in": ["github.com", "gitlab.com"]}) is True
    assert match_conditions(features, {"from_domain_in": ["gitlab.com"]}) is False


def test_match_subject_and_from_regex() -> None:
    features = _features(subject="Your invoice for March", from_email="billing@acme.com")
    conditions = {
        "subject_matches": "(?i)(invoice|factura)",
        "from_matches": "(?i)billing",
    }
    assert match_conditions(features, conditions) is True


def test_match_header_equals_precedence_bulk() -> None:
    features = _features(precedence="bulk")
    assert match_conditions(
        features,
        {"header_equals": {"name": "Precedence", "value": "bulk"}},
    ) is True


def test_evaluate_rules_returns_first_by_priority() -> None:
    user = User(id=uuid.uuid4(), email="user@example.com")
    low_priority = Rule(
        id=uuid.uuid4(),
        user_id=user.id,
        name="newsletter",
        priority=10,
        conditions={"header_exists": "List-Unsubscribe"},
        actions={"add_labels": ["mailresolve/newsletter"]},
        enabled=True,
    )
    high_priority = Rule(
        id=uuid.uuid4(),
        user_id=user.id,
        name="dev",
        priority=20,
        conditions={"from_domain_in": ["github.com"]},
        actions={"add_labels": ["mailresolve/dev"]},
        enabled=True,
    )

    class FakeQuery:
        def __init__(self, rules):
            self.rules = rules

        def filter(self, *args, **kwargs):
            return self

        def order_by(self, *args, **kwargs):
            return self

        def all(self):
            return self.rules

    class FakeSession:
        def query(self, model):
            return FakeQuery([low_priority, high_priority])

    features = _features(
        list_unsubscribe="<mailto:unsub@news.com>",
        from_email="noreply@github.com",
        from_domain="github.com",
    )
    result = evaluate_rules(FakeSession(), user, features)

    assert isinstance(result, RuleMatch)
    assert result.rule_name == "newsletter"
    assert result.confidence == 0.95


def test_match_rule_wrapper() -> None:
    rule = Rule(
        id=uuid.uuid4(),
        user_id=uuid.uuid4(),
        name="finance",
        priority=30,
        conditions={"subject_matches": "(?i)invoice"},
        actions={"add_labels": ["mailresolve/finance"]},
        enabled=True,
    )
    assert match_rule(_features(subject="Invoice #123"), rule) is True
    assert match_rule(_features(subject="Hello"), rule) is False

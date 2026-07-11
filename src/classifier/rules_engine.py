"""Deterministic rules engine for email classification."""

import re
import uuid
from dataclasses import dataclass

from sqlalchemy.orm import Session

from src.classifier.features import EmailFeatures
from src.models import Rule, User

RULE_MATCH_CONFIDENCE = 0.95

_HEADER_FIELDS = {
    "list-unsubscribe": "list_unsubscribe",
    "precedence": "precedence",
    "x-mailer": "x_mailer",
    "auto-submitted": "auto_submitted",
}


@dataclass(frozen=True)
class RuleMatch:
    """Result when a rule matches an email."""

    rule_id: uuid.UUID
    rule_name: str
    category: str
    confidence: float
    actions: dict
    reasoning: str


def load_rules(db: Session, user: User) -> list[Rule]:
    """Return enabled rules for a user, lowest priority number first."""
    return (
        db.query(Rule)
        .filter(Rule.user_id == user.id, Rule.enabled.is_(True))
        .order_by(Rule.priority)
        .all()
    )


def _header_value(features: EmailFeatures, header_name: str) -> str | None:
    field = _HEADER_FIELDS.get(header_name.lower())
    if field is None:
        return None
    value = getattr(features, field)
    return value if value else None


def _header_exists(features: EmailFeatures, header_name: str) -> bool:
    return _header_value(features, header_name) is not None


def _header_equals(features: EmailFeatures, header_name: str, expected: str) -> bool:
    value = _header_value(features, header_name)
    if value is None:
        return False
    return value.lower() == expected.lower()


def _regex_matches(pattern: str, value: str) -> bool:
    return re.search(pattern, value) is not None


def match_conditions(features: EmailFeatures, conditions: dict) -> bool:
    """Evaluate rule conditions against extracted email features.

    Supported condition keys (combined with AND when several appear together):
    - all: list of nested condition objects
    - header_exists: header name, e.g. "List-Unsubscribe"
    - header_equals: {"name": "Precedence", "value": "bulk"}
    - from_domain_in: list of domains
    - subject_matches: regex applied to subject
    - from_matches: regex applied to from_email
    """
    if not conditions:
        return False

    if "all" in conditions:
        nested = conditions["all"]
        if not isinstance(nested, list) or not nested:
            return False
        return all(match_conditions(features, item) for item in nested)

    checks: list[bool] = []

    if "header_exists" in conditions:
        checks.append(_header_exists(features, conditions["header_exists"]))

    if "header_equals" in conditions:
        spec = conditions["header_equals"]
        checks.append(_header_equals(features, spec["name"], spec["value"]))

    if "from_domain_in" in conditions:
        domains = {domain.lower() for domain in conditions["from_domain_in"]}
        checks.append(features.from_domain in domains)

    if "subject_matches" in conditions:
        checks.append(_regex_matches(conditions["subject_matches"], features.subject))

    if "from_matches" in conditions:
        checks.append(_regex_matches(conditions["from_matches"], features.from_email))

    return bool(checks) and all(checks)


def match_rule(features: EmailFeatures, rule: Rule) -> bool:
    """Return True if a single rule matches the email features."""
    return match_conditions(features, rule.conditions)


def evaluate_rules(db: Session, user: User, features: EmailFeatures) -> RuleMatch | None:
    """Return the first matching rule by priority, or None if no rule matches."""
    for rule in load_rules(db, user):
        if not match_rule(features, rule):
            continue

        category = rule.conditions.get("category", rule.name)
        return RuleMatch(
            rule_id=rule.id,
            rule_name=rule.name,
            category=category,
            confidence=RULE_MATCH_CONFIDENCE,
            actions=rule.actions,
            reasoning=f'Matched rule "{rule.name}"',
        )

    return None

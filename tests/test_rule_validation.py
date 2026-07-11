import pytest

from src.classifier.rule_validation import validate_rule_spec


def test_validate_rule_spec_accepts_valid_rule() -> None:
    validate_rule_spec(
        "newsletter",
        {"category": "newsletter", "header_exists": "List-Unsubscribe"},
        {"add_labels": ["mailresolve/newsletter"]},
    )


def test_validate_rule_spec_rejects_category_only() -> None:
    with pytest.raises(ValueError, match="match criterion"):
        validate_rule_spec("bad", {"category": "newsletter"}, {"add_labels": ["x"]})

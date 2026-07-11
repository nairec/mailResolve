import json
from unittest.mock import MagicMock, patch

import pytest

from src.classifier.features import EmailFeatures
from src.classifier.groq_classifier import (
    LLM_APPLY_THRESHOLD,
    _features_to_prompt,
    _parse_classification,
    classify_with_groq,
    review_needed_actions,
)


def _features(**overrides) -> EmailFeatures:
    defaults = {
        "message_id": "msg-1",
        "from_email": "noreply@service.com",
        "from_domain": "service.com",
        "to": "me@example.com",
        "subject": "Weekly digest",
        "snippet": "Here is your weekly summary",
        "label_ids": ("INBOX", "UNREAD"),
        "is_unread": True,
        "has_attachment": False,
        "internal_date": None,
        "list_unsubscribe": None,
        "precedence": None,
        "x_mailer": None,
        "auto_submitted": None,
    }
    defaults.update(overrides)
    return EmailFeatures(**defaults)


def test_features_to_prompt_includes_subject_and_snippet() -> None:
    prompt = _features_to_prompt(_features())
    assert "Weekly digest" in prompt
    assert "weekly summary" in prompt
    assert "noreply@service.com" in prompt


def test_parse_classification_valid_payload() -> None:
    payload = json.dumps(
        {
            "category": "newsletter",
            "confidence": 0.88,
            "actions": {
                "add_labels": ["mailresolve/newsletter"],
                "remove_labels": ["INBOX", "UNREAD"],
                "snooze_until": None,
            },
            "reasoning": "Bulk weekly digest with no action required",
        }
    )
    result = _parse_classification(payload)
    assert result.category == "newsletter"
    assert result.confidence == 0.88


def test_parse_classification_rejects_invalid_payload() -> None:
    with pytest.raises(ValueError, match="Invalid Groq classification response"):
        _parse_classification('{"category": "unknown", "confidence": 2.0}')


@patch("src.classifier.groq_classifier._call_groq")
def test_classify_with_groq_delegates_to_call(mock_call) -> None:
    mock_call.return_value = MagicMock(category="personal", confidence=0.8)
    result = classify_with_groq(_features())
    assert result.category == "personal"
    mock_call.assert_called_once()


def test_review_needed_actions() -> None:
    actions = review_needed_actions()
    assert actions["add_labels"] == ["mailresolve/review-needed"]
    assert actions["remove_labels"] == []
    assert LLM_APPLY_THRESHOLD == 0.75

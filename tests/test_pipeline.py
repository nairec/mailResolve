import uuid
from unittest.mock import MagicMock, patch

from src.classifier.features import EmailFeatures
from src.classifier.pipeline import (
    RULE_APPLY_THRESHOLD,
    ClassificationResult,
    classify_and_act,
)
from src.classifier.rules_engine import RuleMatch
from src.models import User
from src.schemas import GroqClassification


def _features() -> EmailFeatures:
    return EmailFeatures(
        message_id="msg-1",
        from_email="noreply@github.com",
        from_domain="github.com",
        to="me@example.com",
        subject="CI failed",
        snippet="Build failed",
        label_ids=("INBOX", "UNREAD"),
        is_unread=True,
        has_attachment=False,
        internal_date=None,
        list_unsubscribe=None,
        precedence=None,
        x_mailer=None,
        auto_submitted=None,
    )


@patch("src.classifier.pipeline.apply_actions")
@patch("src.classifier.pipeline.evaluate_rules")
@patch("src.classifier.pipeline.extract_features")
def test_classify_and_act_uses_rule_match(mock_extract, mock_evaluate, mock_apply) -> None:
    user = User(id=uuid.uuid4(), email="user@example.com")
    db = MagicMock()
    mock_extract.return_value = _features()
    mock_evaluate.return_value = RuleMatch(
        rule_id=uuid.uuid4(),
        rule_name="dev",
        category="notification",
        confidence=0.95,
        actions={"add_labels": ["mailresolve/dev"], "remove_labels": ["INBOX"]},
        reasoning='Matched rule "dev"',
    )
    mock_apply.return_value = {"modified": True}

    result = classify_and_act(db, user, "msg-1")

    assert isinstance(result, ClassificationResult)
    assert result.source == "rule"
    assert result.category == "notification"
    assert result.confidence >= RULE_APPLY_THRESHOLD
    mock_apply.assert_called_once()
    db.add.assert_called_once()
    db.commit.assert_called_once()


@patch("src.classifier.pipeline.apply_actions")
@patch("src.classifier.pipeline.classify_with_groq")
@patch("src.classifier.pipeline.evaluate_rules")
@patch("src.classifier.pipeline.extract_features")
def test_classify_and_act_falls_back_to_groq(mock_extract, mock_evaluate, mock_groq, mock_apply) -> None:
    user = User(id=uuid.uuid4(), email="user@example.com")
    db = MagicMock()
    mock_extract.return_value = _features()
    mock_evaluate.return_value = None
    mock_groq.return_value = GroqClassification(
        category="notification",
        confidence=0.82,
        actions={"add_labels": ["mailresolve/notifications"], "remove_labels": ["INBOX"]},
        reasoning="Automated CI notification",
    )
    mock_apply.return_value = {"modified": True}

    result = classify_and_act(db, user, "msg-1")

    assert result.source == "llm"
    assert result.category == "notification"
    mock_groq.assert_called_once()


@patch("src.classifier.pipeline.apply_actions")
@patch("src.classifier.pipeline.classify_with_groq")
@patch("src.classifier.pipeline.evaluate_rules")
@patch("src.classifier.pipeline.extract_features")
def test_classify_and_act_low_llm_confidence_review_only(
    mock_extract, mock_evaluate, mock_groq, mock_apply
) -> None:
    user = User(id=uuid.uuid4(), email="user@example.com")
    db = MagicMock()
    mock_extract.return_value = _features()
    mock_evaluate.return_value = None
    mock_groq.return_value = GroqClassification(
        category="personal",
        confidence=0.5,
        actions={"add_labels": ["mailresolve/personal"], "remove_labels": ["INBOX"]},
        reasoning="Unclear personal note",
    )
    mock_apply.return_value = {"modified": True}

    result = classify_and_act(db, user, "msg-1")

    assert result.source == "llm"
    assert "review-only" in result.reasoning
    applied_actions = mock_apply.call_args[0][2]
    assert applied_actions["add_labels"] == ["mailresolve/review-needed"]

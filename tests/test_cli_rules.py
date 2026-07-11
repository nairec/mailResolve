import uuid
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import MagicMock, patch

from typer.testing import CliRunner

from src.cli.main import app
from src.classifier.rules_engine import RuleMatch
from src.models import Rule, User

runner = CliRunner()


def test_rules_list_shows_rules(monkeypatch) -> None:
    user = User(id=uuid.uuid4(), email="user@example.com")
    rule = Rule(
        id=uuid.uuid4(),
        user_id=user.id,
        name="newsletter",
        priority=10,
        conditions={"category": "newsletter", "header_exists": "List-Unsubscribe"},
        actions={"add_labels": ["mailresolve/newsletter"]},
        enabled=True,
    )

    db = MagicMock()
    db.query.return_value.first.return_value = user
    db.query.return_value.filter.return_value.order_by.return_value.all.return_value = [rule]
    monkeypatch.setattr("src.cli.main.SessionLocal", lambda: db)

    result = runner.invoke(app, ["rules", "list"])

    assert result.exit_code == 0
    assert "newsletter" in result.stdout


def test_rules_add_from_yaml(tmp_path, monkeypatch) -> None:
    user = User(id=uuid.uuid4(), email="user@example.com")
    rule_file = tmp_path / "rule.yaml"
    rule_file.write_text(
        """
name: promo
priority: 60
conditions:
  category: newsletter
  subject_matches: "(?i)sale"
actions:
  add_labels:
    - mailresolve/promo
  remove_labels:
    - INBOX
"""
    )

    db = MagicMock()
    db.query.return_value.first.return_value = user
    db.refresh.side_effect = lambda obj: setattr(obj, "id", uuid.uuid4())
    monkeypatch.setattr("src.cli.main.SessionLocal", lambda: db)

    result = runner.invoke(app, ["rules", "add", "--file", str(rule_file)])

    assert result.exit_code == 0
    assert "Rule created: promo" in result.stdout
    db.add.assert_called_once()
    db.commit.assert_called_once()


def test_rules_add_interactive(monkeypatch) -> None:
    user = User(id=uuid.uuid4(), email="user@example.com")
    spec = {
        "name": "promo",
        "priority": 60,
        "enabled": True,
        "conditions": {"category": "newsletter", "subject_matches": "(?i)sale"},
        "actions": {"add_labels": ["mailresolve/promo"], "remove_labels": ["INBOX"]},
    }

    db = MagicMock()
    db.query.return_value.first.return_value = user
    db.refresh.side_effect = lambda obj: setattr(obj, "id", uuid.uuid4())
    monkeypatch.setattr("src.cli.main.SessionLocal", lambda: db)
    monkeypatch.setattr("src.cli.main.prompt_rule_spec", lambda: spec)

    result = runner.invoke(app, ["rules", "add", "--interactive"])

    assert result.exit_code == 0
    assert "Rule created: promo" in result.stdout
    db.add.assert_called_once()


@patch("src.cli.main.evaluate_rules")
@patch("src.cli.main.extract_features")
def test_rules_test_shows_match(mock_extract, mock_evaluate, monkeypatch) -> None:
    user = User(id=uuid.uuid4(), email="user@example.com")
    db = MagicMock()
    db.query.return_value.first.return_value = user
    monkeypatch.setattr("src.cli.main.SessionLocal", lambda: db)

    mock_evaluate.return_value = RuleMatch(
        rule_id=uuid.uuid4(),
        rule_name="newsletter",
        category="newsletter",
        confidence=0.95,
        actions={"add_labels": ["mailresolve/newsletter"]},
        reasoning='Matched rule "newsletter"',
    )

    result = runner.invoke(app, ["rules", "test", "msg-abc"])

    assert result.exit_code == 0
    assert "Matched rule: newsletter" in result.stdout

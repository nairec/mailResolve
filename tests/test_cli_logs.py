from datetime import UTC, datetime
from unittest.mock import MagicMock
from uuid import uuid4

from typer.testing import CliRunner

from src.cli.main import app
from src.models import ClassificationLog

runner = CliRunner()


def test_logs_shows_entries(monkeypatch) -> None:
    entry = ClassificationLog(
        id=uuid4(),
        user_id=uuid4(),
        gmail_message_id="msg-123",
        source="rule",
        category="newsletter",
        confidence=0.95,
        actions_applied={
            "add_labels": ["mailresolve/newsletter"],
            "remove_labels": ["INBOX", "UNREAD"],
        },
        reasoning='Matched rule "newsletter"',
        created_at=datetime(2026, 7, 11, 10, 0, 0, tzinfo=UTC),
    )

    db = MagicMock()
    db.query.return_value.order_by.return_value.limit.return_value.all.return_value = [entry]
    monkeypatch.setattr("src.cli.main.SessionLocal", lambda: db)

    result = runner.invoke(app, ["logs", "--last", "1"])

    assert result.exit_code == 0
    assert "[rule] newsletter" in result.stdout
    assert "conf=0.95" in result.stdout
    assert "archived" in result.stdout
    assert "msg-123" in result.stdout


def test_logs_empty(monkeypatch) -> None:
    db = MagicMock()
    db.query.return_value.order_by.return_value.limit.return_value.all.return_value = []
    monkeypatch.setattr("src.cli.main.SessionLocal", lambda: db)

    result = runner.invoke(app, ["logs"])

    assert result.exit_code == 0
    assert "No classification logs yet." in result.stdout

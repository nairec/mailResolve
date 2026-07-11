import uuid
from unittest.mock import MagicMock, patch

from typer.testing import CliRunner

from src.cli.main import app
from src.gmail.sync import SyncResult
from src.models import User

runner = CliRunner()


@patch("src.cli.main.sync_user")
def test_sync_without_classify(mock_sync_user, monkeypatch) -> None:
    user = User(id=uuid.uuid4(), email="user@example.com", history_id=12345)
    mock_sync_user.return_value = SyncResult(
        new_message_ids=["msg-1", "msg-2"],
        latest_history_id=99999,
    )

    db = MagicMock()
    db.query.return_value.first.return_value = user
    monkeypatch.setattr("src.cli.main.SessionLocal", lambda: db)

    result = runner.invoke(app, ["sync"])

    assert result.exit_code == 0
    assert "Synced 2 new message(s)" in result.stdout
    assert "msg-1" in result.stdout
    assert "[rule]" not in result.stdout
    mock_sync_user.assert_called_once()


@patch("src.cli.main.classify_and_act")
@patch("src.cli.main.sync_user")
def test_sync_classify_in_process(mock_sync_user, mock_classify, monkeypatch) -> None:
    user = User(id=uuid.uuid4(), email="user@example.com", history_id=12345)
    mock_sync_user.return_value = SyncResult(new_message_ids=["msg-1"], latest_history_id=99999)
    mock_classify.return_value = MagicMock(
        source="rule",
        category="newsletter",
        confidence=0.95,
    )

    db = MagicMock()
    db.query.return_value.first.return_value = user
    monkeypatch.setattr("src.cli.main.SessionLocal", lambda: db)

    result = runner.invoke(app, ["sync", "--classify-in-process"])

    assert result.exit_code == 0
    assert "[rule] newsletter" in result.stdout
    assert "conf=0.95" in result.stdout
    mock_classify.assert_called_once()


@patch("src.cli.main.process_history.delay")
def test_sync_classify_enqueues_celery(mock_delay, monkeypatch) -> None:
    user = User(id=uuid.uuid4(), email="user@example.com", history_id=12345)
    mock_delay.return_value = MagicMock(id="task-xyz")

    db = MagicMock()
    db.query.return_value.first.return_value = user
    monkeypatch.setattr("src.cli.main.SessionLocal", lambda: db)

    result = runner.invoke(app, ["sync", "--classify"])

    assert result.exit_code == 0
    assert "Sync + classify queued." in result.stdout
    assert "task-xyz" in result.stdout
    mock_delay.assert_called_once_with(str(user.id), 12345)


def test_sync_rejects_both_classify_flags(monkeypatch) -> None:
    user = User(id=uuid.uuid4(), email="user@example.com", history_id=12345)
    db = MagicMock()
    db.query.return_value.first.return_value = user
    monkeypatch.setattr("src.cli.main.SessionLocal", lambda: db)

    result = runner.invoke(app, ["sync", "--classify", "--classify-in-process"])

    assert result.exit_code == 1
    assert "not both" in result.stdout

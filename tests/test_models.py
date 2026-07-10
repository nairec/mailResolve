"""Verify SQLAlchemy models define expected tables."""

from src.models import (
    Base,
    ClassificationLog,
    ProcessedMessage,
    Rule,
    SnoozedMessage,
    User,
)


def test_all_tables_registered() -> None:
    table_names = set(Base.metadata.tables.keys())
    expected = {
        "users",
        "rules",
        "classification_logs",
        "snoozed_messages",
        "processed_messages",
    }
    assert expected == table_names


def test_model_classes_exist() -> None:
    assert User.__tablename__ == "users"
    assert Rule.__tablename__ == "rules"
    assert ClassificationLog.__tablename__ == "classification_logs"
    assert SnoozedMessage.__tablename__ == "snoozed_messages"
    assert ProcessedMessage.__tablename__ == "processed_messages"

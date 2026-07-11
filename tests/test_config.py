from src.core.config import Settings


def test_sqlalchemy_database_url_normalizes_heroku_postgres() -> None:
    settings = Settings(
        database_url="postgres://user:pass@host:5432/dbname",
        secret_key="test",
    )
    assert settings.sqlalchemy_database_url == "postgresql://user:pass@host:5432/dbname"


def test_sqlalchemy_database_url_keeps_postgresql_scheme() -> None:
    settings = Settings(
        database_url="postgresql://user:pass@localhost:5432/mailresolve",
        secret_key="test",
    )
    assert settings.sqlalchemy_database_url == settings.database_url


def test_production_rejects_localhost_database() -> None:
    import pytest

    with pytest.raises(ValueError, match="DATABASE_URL"):
        Settings(
            environment="production",
            database_url="postgresql://mailresolve:mailresolve@localhost:5432/mailresolve",
            secret_key="test",
        )

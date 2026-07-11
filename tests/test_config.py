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


def test_celery_redis_url_adds_ssl_cert_reqs_for_rediss() -> None:
    settings = Settings(
        redis_url="rediss://:secret@host.example.com:6379",
        secret_key="test",
    )
    assert "ssl_cert_reqs=CERT_NONE" in settings.celery_redis_url
    assert settings.celery_redis_use_ssl is not None


def test_celery_redis_url_unchanged_for_local_redis() -> None:
    settings = Settings(
        redis_url="redis://localhost:6379/0",
        secret_key="test",
    )
    assert settings.celery_redis_url == settings.redis_url
    assert settings.celery_redis_use_ssl is None

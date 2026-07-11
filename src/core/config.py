import ssl

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Google
    google_client_id: str = ""
    google_client_secret: str = ""
    google_oauth_redirect_uri: str = "http://localhost:8000/auth/callback"
    google_pubsub_topic: str = ""

    # Groq
    groq_api_key: str = ""
    groq_model: str = "llama-3.1-8b-instant"

    # Database / Redis
    database_url: str = "postgresql://mailresolve:mailresolve@localhost:5432/mailresolve"
    redis_url: str = "redis://localhost:6379/0"

    # App
    secret_key: str = ""
    api_key: str = ""
    environment: str = "development"

    @model_validator(mode="after")
    def validate_production_database(self) -> "Settings":
        if self.environment == "production" and "localhost" in self.database_url:
            raise ValueError(
                "DATABASE_URL is not configured. Add Heroku Postgres: "
                "heroku addons:create heroku-postgresql:essential-0"
            )
        return self

    @property
    def is_production(self) -> bool:
        return self.environment == "production"

    @property
    def sqlalchemy_database_url(self) -> str:
        """Normalize DATABASE_URL for SQLAlchemy (Heroku uses postgres://)."""
        url = self.database_url
        if url.startswith("postgres://"):
            return url.replace("postgres://", "postgresql://", 1)
        return url

    @property
    def celery_redis_url(self) -> str:
        """Redis URL for Celery; Heroku rediss:// requires ssl_cert_reqs."""
        url = self.redis_url
        if url.startswith("rediss://") and "ssl_cert_reqs" not in url:
            separator = "&" if "?" in url else "?"
            return f"{url}{separator}ssl_cert_reqs=CERT_NONE"
        return url

    @property
    def celery_redis_use_ssl(self) -> dict | None:
        if self.redis_url.startswith("rediss://"):
            return {"ssl_cert_reqs": ssl.CERT_NONE}
        return None


settings = Settings()

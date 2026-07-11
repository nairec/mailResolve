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


settings = Settings()

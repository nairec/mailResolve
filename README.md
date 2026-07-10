# mailResolve

Automated Gmail triage with deterministic rules and Groq LLM fallback.

## Quick start (local)

```bash
# Start Postgres + Redis
docker compose up -d

# Install dependencies
pip install -e ".[dev]"

# Copy env and set SECRET_KEY (generate with: python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())")
cp .env.example .env

# Run migrations
alembic upgrade head

# Start API
uvicorn src.api.main:app --reload --port 8000
```

## CLI

```bash
mailresolve --help
```

See [estructura.md](estructura.md) for architecture and module layout.

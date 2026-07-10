from collections.abc import Generator

from fastapi import Header, HTTPException, status
from sqlalchemy.orm import Session

from src.core.config import settings
from src.models.database import get_db


def get_database() -> Generator[Session, None, None]:
    yield from get_db()


def verify_api_key(x_api_key: str = Header(..., alias="X-API-Key")) -> str:
    if not settings.api_key:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="API key not configured",
        )
    if x_api_key != settings.api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API key",
        )
    return x_api_key

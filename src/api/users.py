"""Single-user helpers for v1 personal deployment."""

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from src.models import User


def get_linked_user(db: Session) -> User:
    """Return the linked Gmail account (v1: exactly one user expected)."""
    user = db.query(User).first()
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No linked Gmail account",
        )
    return user

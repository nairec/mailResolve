from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from src.api.deps import get_database, verify_api_key
from src.models import User
from src.worker.tasks import process_history

router = APIRouter(prefix="/sync", tags=["sync"], dependencies=[Depends(verify_api_key)])


@router.post("")
def force_sync(db: Session = Depends(get_database)) -> dict[str, str]:
    """Enqueue a manual Gmail history sync for the linked account (v1: single user)."""
    user = db.query(User).first()
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No linked Gmail account",
        )
    if user.history_id is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Watch not configured; run auth login first",
        )

    task = process_history.delay(str(user.id), user.history_id)
    return {
        "status": "queued",
        "task_id": task.id,
        "email": user.email,
        "history_id": str(user.history_id),
    }

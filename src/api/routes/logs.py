from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from src.api.deps import get_database, verify_api_key
from src.models import ClassificationLog
from src.schemas import ClassificationLogRead

router = APIRouter(prefix="/logs", tags=["logs"], dependencies=[Depends(verify_api_key)])


@router.get("", response_model=list[ClassificationLogRead])
def list_logs(
    last: int = 50,
    db: Session = Depends(get_database),
) -> list[ClassificationLog]:
    return (
        db.query(ClassificationLog)
        .order_by(ClassificationLog.created_at.desc())
        .limit(last)
        .all()
    )

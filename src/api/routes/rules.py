import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from src.api.deps import get_database, verify_api_key
from src.models import Rule
from src.schemas import RuleCreate, RuleRead, RuleTestRequest

router = APIRouter(prefix="/rules", tags=["rules"], dependencies=[Depends(verify_api_key)])


@router.get("", response_model=list[RuleRead])
def list_rules(db: Session = Depends(get_database)) -> list[Rule]:
    return db.query(Rule).order_by(Rule.priority).all()


@router.post("", response_model=RuleRead, status_code=status.HTTP_201_CREATED)
def create_rule(rule_in: RuleCreate, db: Session = Depends(get_database)) -> Rule:
    # v1 personal: single-user; user_id assignment in OAuth phase
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="Rule creation requires authenticated user context",
    )


@router.delete("/{rule_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_rule(rule_id: uuid.UUID, db: Session = Depends(get_database)) -> None:
    rule = db.get(Rule, rule_id)
    if not rule:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Rule not found")
    db.delete(rule)
    db.commit()


@router.post("/test")
def test_rule(request: RuleTestRequest, db: Session = Depends(get_database)) -> dict:
    return {
        "status": "not_implemented",
        "message_id": request.message_id,
    }

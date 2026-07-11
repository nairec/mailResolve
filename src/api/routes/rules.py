import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from src.api.deps import get_database, verify_api_key
from src.api.users import get_linked_user
from src.classifier.features import extract_features
from src.classifier.rule_validation import validate_rule_spec
from src.classifier.rules_engine import evaluate_rules
from src.models import Rule, User
from src.schemas import RuleCreate, RuleRead, RuleTestRequest, RuleTestResponse, RuleUpdate

router = APIRouter(prefix="/rules", tags=["rules"], dependencies=[Depends(verify_api_key)])


def _get_user_rule(db: Session, rule_id: uuid.UUID) -> tuple[User, Rule]:
    user = get_linked_user(db)
    rule = db.get(Rule, rule_id)
    if rule is None or rule.user_id != user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Rule not found")
    return user, rule


@router.get("", response_model=list[RuleRead])
def list_rules(db: Session = Depends(get_database)) -> list[Rule]:
    user = get_linked_user(db)
    return (
        db.query(Rule)
        .filter(Rule.user_id == user.id)
        .order_by(Rule.priority)
        .all()
    )


@router.post("/test", response_model=RuleTestResponse)
def test_rule(request: RuleTestRequest, db: Session = Depends(get_database)) -> RuleTestResponse:
    user = get_linked_user(db)
    try:
        features = extract_features(user, request.message_id)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to fetch message: {exc}",
        ) from exc

    match = evaluate_rules(db, user, features)
    if match is None:
        return RuleTestResponse(message_id=request.message_id, matched=False)

    return RuleTestResponse(
        message_id=request.message_id,
        matched=True,
        rule_id=match.rule_id,
        rule_name=match.rule_name,
        category=match.category,
        confidence=match.confidence,
        actions=match.actions,
        reasoning=match.reasoning,
    )


@router.get("/{rule_id}", response_model=RuleRead)
def get_rule(rule_id: uuid.UUID, db: Session = Depends(get_database)) -> Rule:
    _, rule = _get_user_rule(db, rule_id)
    return rule


@router.post("", response_model=RuleRead, status_code=status.HTTP_201_CREATED)
def create_rule(rule_in: RuleCreate, db: Session = Depends(get_database)) -> Rule:
    user = get_linked_user(db)
    try:
        validate_rule_spec(rule_in.name, rule_in.conditions, rule_in.actions)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc

    rule = Rule(
        user_id=user.id,
        name=rule_in.name.strip(),
        priority=rule_in.priority,
        conditions=rule_in.conditions,
        actions=rule_in.actions,
        enabled=rule_in.enabled,
    )
    db.add(rule)
    db.commit()
    db.refresh(rule)
    return rule


@router.patch("/{rule_id}", response_model=RuleRead)
def update_rule(
    rule_id: uuid.UUID,
    rule_in: RuleUpdate,
    db: Session = Depends(get_database),
) -> Rule:
    _, rule = _get_user_rule(db, rule_id)

    updates = rule_in.model_dump(exclude_unset=True)
    if not updates:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="No fields to update",
        )

    name = updates.get("name", rule.name)
    conditions = updates.get("conditions", rule.conditions)
    actions = updates.get("actions", rule.actions)

    try:
        validate_rule_spec(name, conditions, actions)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc

    for field, value in updates.items():
        if field == "name":
            setattr(rule, field, value.strip())
        else:
            setattr(rule, field, value)

    db.commit()
    db.refresh(rule)
    return rule


@router.delete("/{rule_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_rule(rule_id: uuid.UUID, db: Session = Depends(get_database)) -> None:
    _, rule = _get_user_rule(db, rule_id)
    db.delete(rule)
    db.commit()

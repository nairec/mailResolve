"""Classification pipeline: rules → Groq fallback → Gmail actions → audit log."""

import logging
from dataclasses import dataclass
from typing import Any

from sqlalchemy.orm import Session

from src.classifier.features import extract_features
from src.classifier.groq_classifier import (
    LLM_APPLY_THRESHOLD,
    classify_with_groq,
    review_needed_actions,
)
from src.classifier.rules_engine import RuleMatch, evaluate_rules
from src.gmail.actions import apply_actions
from src.models import ClassificationLog, User

logger = logging.getLogger(__name__)

RULE_APPLY_THRESHOLD = 0.9


@dataclass(frozen=True)
class ClassificationResult:
    """Outcome of classifying and acting on one message."""

    message_id: str
    source: str
    category: str
    confidence: float
    actions_applied: dict[str, Any]
    reasoning: str
    applied: bool


def _save_log(
    db: Session,
    user: User,
    message_id: str,
    source: str,
    category: str,
    confidence: float,
    actions_applied: dict[str, Any],
    reasoning: str,
) -> ClassificationLog:
    log = ClassificationLog(
        user_id=user.id,
        gmail_message_id=message_id,
        source=source,
        category=category,
        confidence=confidence,
        actions_applied=actions_applied,
        reasoning=reasoning,
    )
    db.add(log)
    db.commit()
    db.refresh(log)
    return log


def _apply_rule_match(user: User, message_id: str, match: RuleMatch) -> dict[str, Any]:
    if match.confidence >= RULE_APPLY_THRESHOLD:
        return apply_actions(user, message_id, match.actions)
    return apply_actions(user, message_id, review_needed_actions())


def _apply_llm_result(user: User, message_id: str, category: str, confidence: float, actions: dict) -> dict[str, Any]:
    if confidence >= LLM_APPLY_THRESHOLD:
        return apply_actions(user, message_id, actions)
    return apply_actions(user, message_id, review_needed_actions())


def classify_and_act(db: Session, user: User, message_id: str) -> ClassificationResult:
    """Run the full triage pipeline for a single Gmail message."""
    features = extract_features(user, message_id)
    rule_match = evaluate_rules(db, user, features)

    if rule_match is not None:
        apply_result = _apply_rule_match(user, message_id, rule_match)
        applied = bool(apply_result.get("modified", True))
        _save_log(
            db,
            user,
            message_id,
            source="rule",
            category=rule_match.category,
            confidence=rule_match.confidence,
            actions_applied=rule_match.actions,
            reasoning=rule_match.reasoning,
        )
        logger.info(
            "Classified %s via rule %s (%s, conf=%.2f)",
            message_id,
            rule_match.rule_name,
            rule_match.category,
            rule_match.confidence,
        )
        return ClassificationResult(
            message_id=message_id,
            source="rule",
            category=rule_match.category,
            confidence=rule_match.confidence,
            actions_applied=rule_match.actions,
            reasoning=rule_match.reasoning,
            applied=applied,
        )

    try:
        llm_result = classify_with_groq(features)
        actions = (
            llm_result.actions
            if llm_result.confidence >= LLM_APPLY_THRESHOLD
            else review_needed_actions()
        )
        apply_result = _apply_llm_result(
            user,
            message_id,
            llm_result.category,
            llm_result.confidence,
            llm_result.actions,
        )
        applied = bool(apply_result.get("modified", False)) or llm_result.confidence >= LLM_APPLY_THRESHOLD
        reasoning = llm_result.reasoning
        if llm_result.confidence < LLM_APPLY_THRESHOLD:
            reasoning = f"{reasoning} (confidence below {LLM_APPLY_THRESHOLD}, review-only)"

        _save_log(
            db,
            user,
            message_id,
            source="llm",
            category=llm_result.category,
            confidence=llm_result.confidence,
            actions_applied=actions,
            reasoning=reasoning,
        )
        logger.info(
            "Classified %s via Groq (%s, conf=%.2f)",
            message_id,
            llm_result.category,
            llm_result.confidence,
        )
        return ClassificationResult(
            message_id=message_id,
            source="llm",
            category=llm_result.category,
            confidence=llm_result.confidence,
            actions_applied=actions,
            reasoning=reasoning,
            applied=applied,
        )
    except Exception as exc:
        logger.exception("Groq classification failed for %s", message_id)
        actions = review_needed_actions()
        apply_actions(user, message_id, actions)
        reasoning = f"Groq classification failed: {exc}"
        _save_log(
            db,
            user,
            message_id,
            source="llm",
            category="unknown",
            confidence=0.0,
            actions_applied=actions,
            reasoning=reasoning,
        )
        return ClassificationResult(
            message_id=message_id,
            source="llm",
            category="unknown",
            confidence=0.0,
            actions_applied=actions,
            reasoning=reasoning,
            applied=True,
        )

"""Groq LLM fallback classifier for emails without a rule match."""

import json
import logging
from typing import Any

from groq import Groq
from pydantic import ValidationError

from src.classifier.features import EmailFeatures
from src.core.config import settings
from src.schemas import GroqClassification

logger = logging.getLogger(__name__)

LLM_APPLY_THRESHOLD = 0.75
REVIEW_LABEL = "mailresolve/review-needed"

CATEGORIES = [
    "action_required",
    "newsletter",
    "notification",
    "invoice",
    "social",
    "promo",
    "personal",
    "work",
]

CLASSIFICATION_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "category": {"type": "string", "enum": CATEGORIES},
        "confidence": {"type": "number", "minimum": 0, "maximum": 1},
        "actions": {
            "type": "object",
            "properties": {
                "add_labels": {"type": "array", "items": {"type": "string"}},
                "remove_labels": {"type": "array", "items": {"type": "string"}},
                "snooze_until": {"type": ["string", "null"]},
            },
            "required": ["add_labels", "remove_labels", "snooze_until"],
            "additionalProperties": False,
        },
        "reasoning": {"type": "string"},
    },
    "required": ["category", "confidence", "actions", "reasoning"],
    "additionalProperties": False,
}

SYSTEM_PROMPT = """You classify incoming Gmail messages for automated triage.
Return JSON only. Prefer archiving newsletters, notifications, and promos.
Keep invoices and action_required emails in INBOX unless clearly spam.
Use mailresolve/* label names. Never delete mail. Be conservative when unsure."""


def _require_groq_client() -> Groq:
    if not settings.groq_api_key:
        raise ValueError("GROQ_API_KEY is not configured")
    return Groq(api_key=settings.groq_api_key)


def _features_to_prompt(features: EmailFeatures) -> str:
    return (
        "Classify this email:\n"
        f"- from: {features.from_email} ({features.from_domain})\n"
        f"- to: {features.to}\n"
        f"- subject: {features.subject}\n"
        f"- snippet: {features.snippet}\n"
        f"- unread: {features.is_unread}\n"
        f"- has_attachment: {features.has_attachment}\n"
        f"- list_unsubscribe: {features.list_unsubscribe or 'none'}\n"
        f"- precedence: {features.precedence or 'none'}\n"
        f"- auto_submitted: {features.auto_submitted or 'none'}\n"
        f"- x_mailer: {features.x_mailer or 'none'}"
    )


def _parse_classification(content: str) -> GroqClassification:
    try:
        payload = json.loads(content)
        return GroqClassification.model_validate(payload)
    except (json.JSONDecodeError, ValidationError) as exc:
        raise ValueError(f"Invalid Groq classification response: {exc}") from exc


def _call_groq(features: EmailFeatures) -> GroqClassification:
    client = _require_groq_client()
    completion = client.chat.completions.create(
        model=settings.groq_model,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": _features_to_prompt(features)},
        ],
        temperature=0,
        response_format={
            "type": "json_schema",
            "json_schema": {
                "name": "email_classification",
                "description": "Gmail triage classification result",
                "schema": CLASSIFICATION_SCHEMA,
                "strict": True,
            },
        },
    )
    content = completion.choices[0].message.content
    if not content:
        raise ValueError("Empty response from Groq")
    return _parse_classification(content)


def classify_with_groq(features: EmailFeatures) -> GroqClassification:
    """Classify an email with Groq structured JSON output."""
    try:
        return _call_groq(features)
    except Exception as exc:
        if "json_schema" in str(exc).lower() or "response_format" in str(exc).lower():
            logger.warning("json_schema failed, retrying with json_object: %s", exc)
            return _call_groq_json_object(features)
        raise


def _call_groq_json_object(features: EmailFeatures) -> GroqClassification:
    """Fallback when the model does not support json_schema."""
    client = _require_groq_client()
    completion = client.chat.completions.create(
        model=settings.groq_model,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {
                "role": "user",
                "content": (
                    _features_to_prompt(features)
                    + "\n\nRespond with JSON matching keys: category, confidence, "
                    "actions {add_labels, remove_labels, snooze_until}, reasoning."
                ),
            },
        ],
        temperature=0,
        response_format={"type": "json_object"},
    )
    content = completion.choices[0].message.content
    if not content:
        raise ValueError("Empty response from Groq")
    return _parse_classification(content)


def review_needed_actions() -> dict[str, Any]:
    """Actions applied when LLM confidence is below the apply threshold."""
    return {
        "add_labels": [REVIEW_LABEL],
        "remove_labels": [],
        "snooze_until": None,
    }

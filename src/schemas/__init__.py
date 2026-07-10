import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class UserRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    email: str
    history_id: int | None
    watch_expires_at: datetime | None
    created_at: datetime


class RuleCreate(BaseModel):
    name: str
    priority: int = 100
    conditions: dict
    actions: dict
    enabled: bool = True


class RuleRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    user_id: uuid.UUID
    name: str
    priority: int
    conditions: dict
    actions: dict
    enabled: bool


class RuleTestRequest(BaseModel):
    message_id: str


class ClassificationLogRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    gmail_message_id: str
    source: str
    category: str | None
    confidence: float | None
    actions_applied: dict | None
    reasoning: str | None
    created_at: datetime


class HealthResponse(BaseModel):
    status: str = "ok"
    environment: str


class PubSubMessage(BaseModel):
    data: str
    message_id: str | None = None
    publish_time: str | None = None


class PubSubPushRequest(BaseModel):
    message: PubSubMessage
    subscription: str | None = None


class GroqClassification(BaseModel):
    category: str
    confidence: float = Field(ge=0.0, le=1.0)
    actions: dict
    reasoning: str

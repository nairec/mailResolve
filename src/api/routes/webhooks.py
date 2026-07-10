import base64
import json
import logging

from fastapi import APIRouter, status
from fastapi.responses import JSONResponse, Response

from src.schemas import PubSubPushRequest

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/webhooks", tags=["webhooks"])


@router.post("/gmail")
def gmail_webhook(payload: PubSubPushRequest) -> Response:
    """Receive Gmail push notifications from Google Pub/Sub."""
    try:
        decoded = base64.b64decode(payload.message.data).decode("utf-8")
        notification = json.loads(decoded)
        logger.info("Gmail push received: %s", notification)
        # Celery task enqueue will be wired in phase 1
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        logger.warning("Invalid Pub/Sub payload: %s", exc)
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={"detail": "Invalid payload"},
        )
    return Response(status_code=status.HTTP_204_NO_CONTENT)

import base64
import json
import logging

from fastapi import APIRouter, Depends, status
from fastapi.responses import JSONResponse, Response
from sqlalchemy.orm import Session

from src.api.deps import get_database
from src.models import User
from src.schemas import PubSubPushRequest
from src.worker.tasks import process_history

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/webhooks", tags=["webhooks"])


@router.post("/gmail")
def gmail_webhook(
    payload: PubSubPushRequest,
    db: Session = Depends(get_database),
) -> Response:
    """Receive Gmail push notifications from Google Pub/Sub and enqueue sync."""
    try:
        decoded = base64.b64decode(payload.message.data).decode("utf-8")
        notification = json.loads(decoded)
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        logger.warning("Invalid Pub/Sub payload: %s", exc)
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={"detail": "Invalid payload"},
        )

    logger.info("Gmail push received: %s", notification)

    email = notification.get("emailAddress")
    history_id_raw = notification.get("historyId")

    if not email or history_id_raw is None:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={"detail": "Missing emailAddress or historyId"},
        )

    try:
        history_id = int(history_id_raw)
    except (TypeError, ValueError):
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={"detail": "Invalid historyId"},
        )

    user = db.query(User).filter(User.email == email).first()
    if user is None:
        logger.warning("Gmail push for unknown user: %s", email)
        return Response(status_code=status.HTTP_204_NO_CONTENT)

    process_history.delay(str(user.id), history_id)
    logger.info("Enqueued process_history for %s (history_id=%s)", email, history_id)

    return Response(status_code=status.HTTP_204_NO_CONTENT)

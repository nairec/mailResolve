import logging
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

from src.gmail.sync import sync_user
from src.gmail.watch import persist_watch_state, renew_watch as renew_user_watch
from src.models import User
from src.models.database import SessionLocal
from src.worker.celery_app import celery_app

logger = logging.getLogger(__name__)

RENEW_WINDOW = timedelta(hours=24)


@celery_app.task(name="src.worker.tasks.process_history")
def process_history(user_id: str, history_id: int | None = None) -> dict[str, Any]:
    """Process Gmail history changes for a user."""
    logger.info("process_history called for user=%s history_id=%s", user_id, history_id)

    db = SessionLocal()
    try:
        user = db.get(User, uuid.UUID(user_id))
        if user is None:
            logger.error("User not found: %s", user_id)
            return {"status": "error", "detail": "user not found"}

        result = sync_user(db, user, notification_history_id=history_id)

        if result.new_message_ids:
            logger.info(
                "Synced %d new message(s) for %s: %s",
                len(result.new_message_ids),
                user.email,
                result.new_message_ids,
            )
        else:
            logger.info("No new messages for %s", user.email)

        return {
            "status": "ok",
            "email": user.email,
            "new_count": len(result.new_message_ids),
            "message_ids": result.new_message_ids,
            "latest_history_id": result.latest_history_id,
        }
    except ValueError as exc:
        logger.warning("process_history failed for user=%s: %s", user_id, exc)
        return {"status": "error", "detail": str(exc)}
    except Exception:
        logger.exception("process_history failed for user=%s", user_id)
        raise
    finally:
        db.close()


@celery_app.task(name="src.worker.tasks.renew_watch")
def renew_watch() -> dict[str, Any]:
    """Renew Gmail watch subscriptions expiring within the next 24 hours."""
    logger.info("renew_watch scheduled task running")
    db = SessionLocal()
    renewed: list[str] = []
    errors: list[dict[str, str]] = []

    try:
        threshold = datetime.now(UTC) + RENEW_WINDOW
        users = (
            db.query(User)
            .filter(
                User.encrypted_refresh_token.isnot(None),
                User.watch_expires_at.isnot(None),
                User.watch_expires_at <= threshold,
            )
            .all()
        )

        for user in users:
            try:
                result = renew_user_watch(user)
                persist_watch_state(db, user, result)
                renewed.append(user.email)
                logger.info(
                    "Renewed watch for %s until %s",
                    user.email,
                    result.expires_at.isoformat(),
                )
            except Exception as exc:
                logger.exception("Failed to renew watch for %s", user.email)
                errors.append({"email": user.email, "detail": str(exc)})

        return {
            "status": "ok",
            "renewed_count": len(renewed),
            "renewed": renewed,
            "errors": errors,
        }
    finally:
        db.close()


@celery_app.task(name="src.worker.tasks.wake_snoozed")
def wake_snoozed() -> dict[str, str]:
    """Re-add snoozed messages to INBOX when wake_at is reached."""
    logger.info("wake_snoozed scheduled task running")
    return {"status": "not_implemented"}

import logging

from src.worker.celery_app import celery_app

logger = logging.getLogger(__name__)


@celery_app.task(name="src.worker.tasks.process_history")
def process_history(user_id: str, history_id: int | None = None) -> dict[str, str]:
    """Process Gmail history changes for a user."""
    logger.info("process_history called for user=%s history_id=%s", user_id, history_id)
    return {"status": "not_implemented"}


@celery_app.task(name="src.worker.tasks.renew_watch")
def renew_watch() -> dict[str, str]:
    """Renew Gmail watch subscriptions before expiration."""
    logger.info("renew_watch scheduled task running")
    return {"status": "not_implemented"}


@celery_app.task(name="src.worker.tasks.wake_snoozed")
def wake_snoozed() -> dict[str, str]:
    """Re-add snoozed messages to INBOX when wake_at is reached."""
    logger.info("wake_snoozed scheduled task running")
    return {"status": "not_implemented"}

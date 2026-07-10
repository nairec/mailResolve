from celery import Celery

from src.core.config import settings

celery_app = Celery(
    "mailresolve",
    broker=settings.redis_url,
    backend=settings.redis_url,
    include=["src.worker.tasks"],
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    beat_schedule={
        "renew-watch": {
            "task": "src.worker.tasks.renew_watch",
            "schedule": 60 * 60 * 24 * 6,  # every 6 days
        },
        "wake-snoozed": {
            "task": "src.worker.tasks.wake_snoozed",
            "schedule": 60,  # every minute
        },
    },
)

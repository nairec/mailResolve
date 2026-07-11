from celery import Celery

from src.core.config import settings

_broker_url = settings.celery_redis_url
celery_app = Celery(
    "mailresolve",
    broker=_broker_url,
    backend=_broker_url,
    include=["src.worker.tasks"],
)

_celery_conf: dict = {
    "task_serializer": "json",
    "accept_content": ["json"],
    "result_serializer": "json",
    "timezone": "UTC",
    "enable_utc": True,
    "beat_schedule": {
        "renew-watch": {
            "task": "src.worker.tasks.renew_watch",
            "schedule": 60 * 60 * 24 * 6,  # every 6 days
        },
        "wake-snoozed": {
            "task": "src.worker.tasks.wake_snoozed",
            "schedule": 60,  # every minute
        },
    },
}

_ssl = settings.celery_redis_use_ssl
if _ssl is not None:
    _celery_conf["broker_use_ssl"] = _ssl
    _celery_conf["redis_backend_use_ssl"] = _ssl

celery_app.conf.update(**_celery_conf)

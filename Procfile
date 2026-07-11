release: alembic upgrade head
web: uvicorn src.api.main:app --host 0.0.0.0 --port $PORT
worker: celery -A src.worker.celery_app worker -l info
beat: celery -A src.worker.celery_app beat -l info

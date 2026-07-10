from fastapi import APIRouter, FastAPI

from src.api.routes import auth, health, logs, rules, sync, webhooks

app = FastAPI(
    title="mailResolve",
    description="Automated Gmail triage API",
    version="0.1.0",
)

api_router = APIRouter()
api_router.include_router(health.router)
api_router.include_router(auth.router)
api_router.include_router(webhooks.router)
api_router.include_router(rules.router)
api_router.include_router(logs.router)
api_router.include_router(sync.router)

app.include_router(api_router)

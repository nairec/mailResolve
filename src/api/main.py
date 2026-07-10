from fastapi import APIRouter, Depends, FastAPI

from src.api.deps import verify_api_key
from src.api.routes import auth, health, logs, rules, webhooks

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


sync_router = APIRouter(prefix="/sync", tags=["sync"], dependencies=[Depends(verify_api_key)])


@sync_router.post("")
def force_sync() -> dict[str, str]:
    return {"status": "not_implemented", "message": "Manual sync pending phase 1"}


api_router.include_router(sync_router)

app.include_router(api_router)

from fastapi import APIRouter

from src.core.config import settings
from src.schemas import HealthResponse

router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse(environment=settings.environment)

from fastapi import APIRouter

router = APIRouter(prefix="/auth", tags=["auth"])


@router.get("/login")
def auth_login() -> dict[str, str]:
    """Initiate Google OAuth flow. Implementation in phase 0 follow-up."""
    return {"status": "not_implemented", "message": "OAuth login flow pending"}


@router.get("/callback")
def auth_callback() -> dict[str, str]:
    """Handle Google OAuth callback. Implementation in phase 0 follow-up."""
    return {"status": "not_implemented", "message": "OAuth callback pending"}

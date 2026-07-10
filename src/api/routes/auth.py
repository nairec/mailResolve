import logging

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import RedirectResponse
from googleapiclient.discovery import build
from sqlalchemy.orm import Session

from src.api.deps import get_database
from src.core.config import settings
from src.core.security import encrypt_token
from src.gmail.oauth import create_oauth_flow, pop_oauth_flow, store_oauth_flow
from src.models import User
from src.gmail.watch import start_watch, persist_watch_state

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/auth", tags=["auth"])


def _require_google_credentials() -> None:
    if not settings.google_client_id or not settings.google_client_secret:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Google OAuth credentials not configured",
        )


def _get_user_email(credentials) -> str:
    service = build("gmail", "v1", credentials=credentials, cache_discovery=False)
    profile = service.users().getProfile(userId="me").execute()
    return profile["emailAddress"]


def _upsert_user(db: Session, email: str, refresh_token: str) -> User:
    user = db.query(User).filter(User.email == email).first()
    if user is None:
        user = User(email=email)
        db.add(user)

    user.encrypted_refresh_token = encrypt_token(refresh_token)
    db.commit()
    db.refresh(user)
    return user


@router.get("/login")
def auth_login() -> RedirectResponse:
    """Redirect the user to Google OAuth consent screen."""
    _require_google_credentials()

    flow = create_oauth_flow()
    authorization_url, state = flow.authorization_url(
        access_type="offline",
        include_granted_scopes="true",
        prompt="consent",
    )
    store_oauth_flow(state, flow)

    return RedirectResponse(
        url=authorization_url,
        status_code=status.HTTP_307_TEMPORARY_REDIRECT,
    )


@router.get("/callback")
def auth_callback(
    code: str = Query(...),
    state: str = Query(...),
    db: Session = Depends(get_database),
) -> dict[str, str]:
    """Exchange OAuth code for tokens and persist encrypted refresh token."""
    _require_google_credentials()

    flow = pop_oauth_flow(state)
    if flow is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired OAuth state; start again from /auth/login",
        )

    try:
        flow.fetch_token(code=code)
    except Exception as exc:
        logger.exception("OAuth token exchange failed: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "Failed to exchange authorization code. "
                "Start a fresh login at /auth/login (codes are single-use and expire quickly)."
            ),
        ) from exc

    credentials = flow.credentials
    if not credentials.refresh_token:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No refresh token received; revoke app access in Google Account and retry",
        )

    try:
        email = _get_user_email(credentials)
    except Exception as exc:
        logger.exception("Failed to fetch Gmail profile")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Failed to fetch Gmail profile",
        ) from exc

    user = _upsert_user(db, email, credentials.refresh_token)

    try:
        watch_result = start_watch(user)
        persist_watch_state(db, user, watch_result)
    except ValueError as exc:
        logger.exception("Failed to start watch")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(exc),
        ) from exc
    except Exception as exc:
        logger.exception("Failed to start watch")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Failed to start watch",
        ) from exc

    return {
        "status": "connected",
        "email": user.email,
        "history_id": str(watch_result.history_id),
        "watch_expires_at": watch_result.expires_at.isoformat(),
        "message": f"Gmail account {user.email} linked successfully",
    }

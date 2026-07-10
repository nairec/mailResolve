"""Google OAuth flow helpers for Gmail account linking."""

from google_auth_oauthlib.flow import Flow

from src.core.config import settings

GMAIL_MODIFY_SCOPE = "https://www.googleapis.com/auth/gmail.modify"

# Flow must be reused on callback: it holds the PKCE code_verifier from /login.
_pending_flows: dict[str, Flow] = {}


def create_oauth_flow() -> Flow:
    return Flow.from_client_config(
        client_config={
            "web": {
                "client_id": settings.google_client_id,
                "client_secret": settings.google_client_secret,
                "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                "token_uri": "https://oauth2.googleapis.com/token",
            }
        },
        scopes=[GMAIL_MODIFY_SCOPE],
        redirect_uri=settings.google_oauth_redirect_uri,
    )


def store_oauth_flow(state: str, flow: Flow) -> None:
    _pending_flows[state] = flow


def pop_oauth_flow(state: str) -> Flow | None:
    return _pending_flows.pop(state, None)

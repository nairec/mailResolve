import webbrowser

import typer

from src.core.config import settings
from src.gmail.client import list_messages
from src.gmail.sync import sync_user
from src.gmail.watch import persist_watch_state, renew_watch as renew_user_watch
from src.models import User
from src.models.database import SessionLocal


app = typer.Typer(help="mailResolve — automated Gmail triage")
auth_app = typer.Typer(help="Authentication commands")
rules_app = typer.Typer(help="Rule management")
app.add_typer(auth_app, name="auth")
app.add_typer(rules_app, name="rules")


@auth_app.command("login")
def auth_login() -> None:
    """Start OAuth flow to connect Gmail account."""
    login_url = settings.google_oauth_redirect_uri.replace("/auth/callback", "/auth/login")
    typer.echo(f"Opening browser for Gmail authorization:\n  {login_url}")
    typer.echo("If the browser does not open, visit the URL manually.")
    webbrowser.open(login_url)


@auth_app.command("status")
def auth_status() -> None:
    """Show connection status and watch expiration. Current version only supports one user."""
    db = SessionLocal()
    try:
        user = db.query(User).first()
        if user is None:
            typer.secho("No user found. Run 'mailresolve auth login' first.", fg=typer.colors.RED)
            raise typer.Exit(1)

        typer.secho(f"Connected: {user.email}", fg=typer.colors.GREEN)
        typer.echo(f"Token: {'present' if user.encrypted_refresh_token else 'missing'}")
        typer.echo(f"History ID: {user.history_id if user.history_id is not None else 'not set'}")
        watch_expires = (
            user.watch_expires_at.isoformat() if user.watch_expires_at is not None else "not configured"
        )
        typer.echo(f"Watch expires: {watch_expires}")

        if user.encrypted_refresh_token:
            try:
                list_messages(user, max_results=1)
                typer.echo("Gmail API: reachable")
            except Exception as exc:
                typer.secho(f"Gmail API: error ({exc})", fg=typer.colors.YELLOW)
    finally:
        db.close()

@app.command("sync")
def sync_cmd() -> None:
    """Force manual Gmail sync (runs directly, no Celery)."""
    db = SessionLocal()
    try:
        user = db.query(User).first()
        if user is None:
            typer.secho("No user found. Run 'mailresolve auth login' first.", fg=typer.colors.RED)
            raise typer.Exit(1)
        if user.history_id is None:
            typer.secho("Watch not configured. Run 'mailresolve auth login' first.", fg=typer.colors.RED)
            raise typer.Exit(1)

        result = sync_user(db, user)
        if result.new_message_ids:
            typer.secho(f"Synced {len(result.new_message_ids)} new message(s):", fg=typer.colors.GREEN)
            for message_id in result.new_message_ids:
                typer.echo(f"  - {message_id}")
        else:
            typer.echo("No new messages.")
        typer.echo(f"History ID: {result.latest_history_id}")
    except ValueError as exc:
        typer.secho(str(exc), fg=typer.colors.RED)
        raise typer.Exit(1) from exc
    finally:
        db.close()


@rules_app.command("list")
def rules_list() -> None:
    """List all classification rules."""
    typer.echo("Rules list not yet implemented.")


@rules_app.command("add")
def rules_add(file: str = typer.Option(..., "--file", help="Path to rule YAML file")) -> None:
    """Add a rule from a YAML file."""
    typer.echo(f"Rules add from {file} not yet implemented.")


@rules_app.command("test")
def rules_test(message_id: str) -> None:
    """Test rules against a Gmail message ID."""
    typer.echo(f"Rules test for {message_id} not yet implemented.")


@app.command("logs")
def logs(last: int = typer.Option(20, "--last", help="Number of log entries")) -> None:
    """Show recent classification decisions."""
    typer.echo(f"Logs (last {last}) not yet implemented.")


@app.command("watch")
def watch_renew() -> None:
    """Manually renew Gmail watch subscription."""
    db = SessionLocal()
    try:
        user = db.query(User).first()
        if user is None:
            typer.secho("No user found. Run 'mailresolve auth login' first.", fg=typer.colors.RED)
            raise typer.Exit(1)

        result = renew_user_watch(user)
        persist_watch_state(db, user, result)
        typer.secho("Watch renewed successfully.", fg=typer.colors.GREEN)
        typer.echo(f"Expires: {result.expires_at.isoformat()}")
        typer.echo(f"History ID: {result.history_id}")
    except ValueError as exc:
        typer.secho(str(exc), fg=typer.colors.RED)
        raise typer.Exit(1) from exc
    finally:
        db.close()


if __name__ == "__main__":
    app()

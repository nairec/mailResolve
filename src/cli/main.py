import webbrowser
from pathlib import Path
from uuid import UUID

import typer
import yaml

from src.classifier.features import extract_features
from src.classifier.pipeline import classify_and_act
from src.classifier.rule_validation import validate_rule_spec
from src.classifier.rules_engine import evaluate_rules
from src.cli.rules_prompt import prompt_rule_spec
from src.core.config import settings
from src.gmail.client import list_messages
from src.gmail.sync import sync_user
from src.gmail.watch import persist_watch_state, renew_watch as renew_user_watch
from src.models import ClassificationLog, Rule, User
from src.models.database import SessionLocal
from src.worker.tasks import process_history


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
def sync_cmd(
    classify: bool = typer.Option(
        False,
        "--classify",
        help="Enqueue sync + classify via Celery (requires Redis and worker)",
    ),
    classify_in_process: bool = typer.Option(
        False,
        "--classify-in-process",
        help="Sync and classify new messages in this process (no Celery)",
    ),
) -> None:
    """Force manual Gmail sync. Optionally classify new messages."""
    if classify and classify_in_process:
        typer.secho("Use either --classify or --classify-in-process, not both.", fg=typer.colors.RED)
        raise typer.Exit(1)

    db = SessionLocal()
    try:
        user = _require_user(db)
        if user.history_id is None:
            typer.secho("Watch not configured. Run 'mailresolve auth login' first.", fg=typer.colors.RED)
            raise typer.Exit(1)

        if classify:
            task = process_history.delay(str(user.id), user.history_id)
            typer.secho("Sync + classify queued.", fg=typer.colors.GREEN)
            typer.echo(f"Task ID: {task.id}")
            typer.echo(f"Email: {user.email}")
            typer.echo(f"History ID: {user.history_id}")
            return

        result = sync_user(db, user)
        if result.new_message_ids:
            typer.secho(f"Synced {len(result.new_message_ids)} new message(s):", fg=typer.colors.GREEN)
            for message_id in result.new_message_ids:
                if classify_in_process:
                    classification = classify_and_act(db, user, message_id)
                    typer.echo(
                        f"  - {message_id} | [{classification.source}] {classification.category} | "
                        f"conf={classification.confidence:.2f}"
                    )
                else:
                    typer.echo(f"  - {message_id}")
        else:
            typer.echo("No new messages.")
        typer.echo(f"History ID: {result.latest_history_id}")
    except ValueError as exc:
        typer.secho(str(exc), fg=typer.colors.RED)
        raise typer.Exit(1) from exc
    finally:
        db.close()


def _require_user(db) -> User:
    user = db.query(User).first()
    if user is None:
        typer.secho("No user found. Run 'mailresolve auth login' first.", fg=typer.colors.RED)
        raise typer.Exit(1)
    return user


def _load_rule_yaml(path: Path) -> dict:
    if not path.is_file():
        typer.secho(f"File not found: {path}", fg=typer.colors.RED)
        raise typer.Exit(1)

    data = yaml.safe_load(path.read_text())
    if not isinstance(data, dict):
        typer.secho("Rule file must contain a YAML object.", fg=typer.colors.RED)
        raise typer.Exit(1)
    return data


def _persist_rule(db, user: User, spec: dict) -> Rule:
    name = spec.get("name")
    conditions = spec.get("conditions")
    actions = spec.get("actions")
    if not name or not isinstance(conditions, dict) or not isinstance(actions, dict):
        typer.secho("Rule spec must include name, conditions, and actions.", fg=typer.colors.RED)
        raise typer.Exit(1)

    try:
        validate_rule_spec(name, conditions, actions)
    except ValueError as exc:
        typer.secho(str(exc), fg=typer.colors.RED)
        raise typer.Exit(1) from exc

    rule = Rule(
        user_id=user.id,
        name=str(name).strip(),
        priority=int(spec.get("priority", 100)),
        conditions=conditions,
        actions=actions,
        enabled=bool(spec.get("enabled", True)),
    )
    db.add(rule)
    db.commit()
    db.refresh(rule)
    return rule


@rules_app.command("list")
def rules_list() -> None:
    """List all classification rules."""
    db = SessionLocal()
    try:
        user = _require_user(db)
        rules = (
            db.query(Rule)
            .filter(Rule.user_id == user.id)
            .order_by(Rule.priority)
            .all()
        )
        if not rules:
            typer.echo("No rules configured.")
            return

        for rule in rules:
            status_label = "enabled" if rule.enabled else "disabled"
            typer.echo(
                f"[{rule.priority:>3}] {rule.id} | {rule.name} ({status_label}) | "
                f"category={rule.conditions.get('category', rule.name)}"
            )
    finally:
        db.close()


@rules_app.command("add")
def rules_add(
    file: str | None = typer.Option(
        None,
        "--file",
        help="Path to rule YAML file (omit for interactive prompts)",
    ),
    interactive: bool = typer.Option(
        False,
        "--interactive",
        "-i",
        help="Create a rule via interactive prompts",
    ),
) -> None:
    """Add a rule from a YAML file or interactive prompts."""
    if file and interactive:
        typer.secho("Use either --file or --interactive, not both.", fg=typer.colors.RED)
        raise typer.Exit(1)

    db = SessionLocal()
    try:
        user = _require_user(db)
        if file:
            spec = _load_rule_yaml(Path(file))
        else:
            spec = prompt_rule_spec()

        rule = _persist_rule(db, user, spec)
        typer.secho(f"Rule created: {rule.name} ({rule.id})", fg=typer.colors.GREEN)
    finally:
        db.close()


@rules_app.command("delete")
def rules_delete(rule_id: UUID) -> None:
    """Delete a rule by ID."""
    db = SessionLocal()
    try:
        user = _require_user(db)
        rule = db.get(Rule, rule_id)
        if rule is None or rule.user_id != user.id:
            typer.secho("Rule not found.", fg=typer.colors.RED)
            raise typer.Exit(1)

        rule_name = rule.name
        db.delete(rule)
        db.commit()
        typer.secho(f"Deleted rule: {rule_name}", fg=typer.colors.GREEN)
    finally:
        db.close()


@rules_app.command("test")
def rules_test(message_id: str) -> None:
    """Test rules against a Gmail message ID."""
    db = SessionLocal()
    try:
        user = _require_user(db)
        try:
            features = extract_features(user, message_id)
        except Exception as exc:
            typer.secho(f"Failed to fetch message: {exc}", fg=typer.colors.RED)
            raise typer.Exit(1) from exc

        match = evaluate_rules(db, user, features)
        if match is None:
            typer.echo(f"No rule matched message {message_id}.")
            return

        typer.secho(f"Matched rule: {match.rule_name}", fg=typer.colors.GREEN)
        typer.echo(f"Category: {match.category}")
        typer.echo(f"Confidence: {match.confidence:.2f}")
        typer.echo(f"Actions: {match.actions}")
        typer.echo(f"Reasoning: {match.reasoning}")
    finally:
        db.close()


def _format_actions(actions: dict | None) -> str:
    if not actions:
        return "none"
    parts: list[str] = []
    remove_labels = actions.get("remove_labels") or []
    add_labels = actions.get("add_labels") or []
    if "INBOX" in remove_labels:
        parts.append("archived")
    if "UNREAD" in remove_labels:
        parts.append("read")
    if add_labels:
        parts.append("labels=" + ",".join(add_labels))
    return ", ".join(parts) if parts else "modified"


@app.command("logs")
def logs_cmd(last: int = typer.Option(20, "--last", help="Number of log entries")) -> None:
    """Show recent classification decisions."""
    db = SessionLocal()
    try:
        entries = (
            db.query(ClassificationLog)
            .order_by(ClassificationLog.created_at.desc())
            .limit(last)
            .all()
        )
        if not entries:
            typer.echo("No classification logs yet.")
            return

        for entry in entries:
            timestamp = entry.created_at.strftime("%Y-%m-%d %H:%M:%S")
            confidence = f"{entry.confidence:.2f}" if entry.confidence is not None else "n/a"
            category = entry.category or "unknown"
            reasoning = (entry.reasoning or "").replace("\n", " ")
            if len(reasoning) > 80:
                reasoning = reasoning[:77] + "..."
            typer.echo(
                f"{timestamp} | [{entry.source}] {category} | conf={confidence} | "
                f"{_format_actions(entry.actions_applied)} | {entry.gmail_message_id} | {reasoning}"
            )
    finally:
        db.close()


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

import typer

app = typer.Typer(help="mailResolve — automated Gmail triage")
auth_app = typer.Typer(help="Authentication commands")
rules_app = typer.Typer(help="Rule management")
app.add_typer(auth_app, name="auth")
app.add_typer(rules_app, name="rules")


@auth_app.command("login")
def auth_login() -> None:
    """Start OAuth flow to connect Gmail account."""
    typer.echo("OAuth login not yet implemented. See phase 0 OAuth follow-up.")


@auth_app.command("status")
def auth_status() -> None:
    """Show connection status and watch expiration."""
    typer.echo("Auth status not yet implemented.")


@app.command("sync")
def sync() -> None:
    """Force manual Gmail sync."""
    typer.echo("Manual sync not yet implemented.")


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
    typer.echo("Watch renew not yet implemented.")


if __name__ == "__main__":
    app()

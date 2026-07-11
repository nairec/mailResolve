"""Interactive prompts for creating classification rules."""

import typer

CONDITION_MENU = """
Condition type:
  1) Header exists (e.g. List-Unsubscribe)
  2) Header equals (e.g. Precedence = bulk)
  3) From domain in list
  4) Subject matches regex
  5) From matches regex
  0) Done adding conditions
"""


def _parse_list(raw: str) -> list[str]:
    return [part.strip() for part in raw.split(",") if part.strip()]


def _prompt_single_condition() -> dict | None:
    typer.echo(CONDITION_MENU.strip())
    choice = typer.prompt("Choose condition", default="0").strip()

    if choice == "0":
        return None
    if choice == "1":
        header = typer.prompt("Header name", default="List-Unsubscribe").strip()
        return {"header_exists": header}
    if choice == "2":
        name = typer.prompt("Header name", default="Precedence").strip()
        value = typer.prompt("Expected value", default="bulk").strip()
        return {"header_equals": {"name": name, "value": value}}
    if choice == "3":
        raw = typer.prompt("Domains (comma-separated)", default="github.com")
        domains = _parse_list(raw)
        if not domains:
            typer.secho("At least one domain is required.", fg=typer.colors.RED)
            raise typer.Exit(1)
        return {"from_domain_in": domains}
    if choice == "4":
        pattern = typer.prompt("Subject regex", default="(?i)invoice").strip()
        return {"subject_matches": pattern}
    if choice == "5":
        pattern = typer.prompt("From regex", default="(?i)noreply").strip()
        return {"from_matches": pattern}

    typer.secho("Invalid choice.", fg=typer.colors.RED)
    raise typer.Exit(1)


def _merge_condition(conditions: dict, new_part: dict) -> None:
    for key, value in new_part.items():
        if key in conditions and key != "category":
            typer.secho(f"Replacing existing condition '{key}'.", fg=typer.colors.YELLOW)
        conditions[key] = value


def _prompt_conditions() -> dict:
    conditions: dict = {}
    category = typer.prompt("Category (optional, used in logs)", default="").strip()
    if category:
        conditions["category"] = category

    while True:
        if conditions.keys() - {"category"}:
            typer.echo(f"Current conditions: {conditions}")
        part = _prompt_single_condition()
        if part is None:
            if not conditions.keys() - {"category"}:
                typer.secho("Add at least one match condition.", fg=typer.colors.RED)
                continue
            return conditions
        _merge_condition(conditions, part)


def _prompt_actions() -> dict:
    while True:
        add_raw = typer.prompt("Labels to add (comma-separated)", default="").strip()
        remove_raw = typer.prompt(
            "Labels to remove (comma-separated, e.g. INBOX,UNREAD)",
            default="",
        ).strip()

        actions: dict = {}
        if add_labels := _parse_list(add_raw):
            actions["add_labels"] = add_labels
        if remove_labels := _parse_list(remove_raw):
            actions["remove_labels"] = remove_labels

        if actions:
            return actions

        typer.secho("Define at least one label action.", fg=typer.colors.YELLOW)


def prompt_rule_spec() -> dict:
    """Walk through prompts and return a rule spec dict."""
    typer.secho("\nCreate a new classification rule", fg=typer.colors.CYAN, bold=True)

    name = typer.prompt("Rule name").strip()
    if not name:
        typer.secho("Name is required.", fg=typer.colors.RED)
        raise typer.Exit(1)

    priority_raw = typer.prompt("Priority (lower runs first)", default="100").strip()
    try:
        priority = int(priority_raw)
    except ValueError as exc:
        typer.secho("Priority must be an integer.", fg=typer.colors.RED)
        raise typer.Exit(1) from exc

    enabled = typer.confirm("Enabled?", default=True)
    conditions = _prompt_conditions()
    actions = _prompt_actions()

    spec = {
        "name": name,
        "priority": priority,
        "enabled": enabled,
        "conditions": conditions,
        "actions": actions,
    }

    typer.echo("\nSummary:")
    typer.echo(f"  name: {spec['name']}")
    typer.echo(f"  priority: {spec['priority']}")
    typer.echo(f"  enabled: {spec['enabled']}")
    typer.echo(f"  conditions: {spec['conditions']}")
    typer.echo(f"  actions: {spec['actions']}")

    if not typer.confirm("\nSave this rule?", default=True):
        typer.echo("Cancelled.")
        raise typer.Exit(0)

    return spec

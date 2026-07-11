"""Validation helpers for rule conditions and actions."""

CONDITION_KEYS = {
    "all",
    "header_exists",
    "header_equals",
    "from_domain_in",
    "subject_matches",
    "from_matches",
}
METADATA_KEYS = {"category"}
ACTION_KEYS = {"add_labels", "remove_labels"}


def validate_conditions(conditions: dict) -> None:
    if not conditions:
        raise ValueError("conditions cannot be empty")

    eval_keys = set(conditions.keys()) - METADATA_KEYS
    if not eval_keys:
        raise ValueError("conditions must include at least one match criterion")

    unknown = eval_keys - CONDITION_KEYS
    if unknown:
        raise ValueError(f"unknown condition keys: {sorted(unknown)}")

    if "header_equals" in conditions:
        spec = conditions["header_equals"]
        if not isinstance(spec, dict) or "name" not in spec or "value" not in spec:
            raise ValueError("header_equals requires 'name' and 'value'")

    if "from_domain_in" in conditions:
        domains = conditions["from_domain_in"]
        if not isinstance(domains, list) or not domains:
            raise ValueError("from_domain_in must be a non-empty list")

    if "all" in conditions:
        nested = conditions["all"]
        if not isinstance(nested, list) or not nested:
            raise ValueError("all must be a non-empty list of nested conditions")
        for item in nested:
            if not isinstance(item, dict):
                raise ValueError("all entries must be condition objects")
            validate_conditions(item)


def validate_actions(actions: dict) -> None:
    if not actions:
        raise ValueError("actions cannot be empty")

    unknown = set(actions.keys()) - ACTION_KEYS
    if unknown:
        raise ValueError(f"unknown action keys: {sorted(unknown)}")

    for key in ACTION_KEYS:
        if key not in actions:
            continue
        labels = actions[key]
        if not isinstance(labels, list) or not all(isinstance(label, str) for label in labels):
            raise ValueError(f"{key} must be a list of label names")


def validate_rule_spec(name: str, conditions: dict, actions: dict) -> None:
    if not name.strip():
        raise ValueError("name cannot be empty")
    validate_conditions(conditions)
    validate_actions(actions)

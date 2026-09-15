"""Validate SKILL.md frontmatter against the Agent Skills format."""

import yaml


def validate_frontmatter(content: str, directory_name: str) -> list[str]:
    lines = content.splitlines()
    if not lines or lines[0].strip() != "---":
        return ["must start with '---'"]
    end = next((i for i in range(1, len(lines)) if lines[i].strip() == "---"), None)
    if end is None:
        return ["missing closing frontmatter delimiter"]
    try:
        data = yaml.safe_load("\n".join(lines[1:end]))
    except yaml.YAMLError as exc:
        return [f"invalid frontmatter YAML: {exc}"]
    if not isinstance(data, dict):
        return ["frontmatter must be a mapping"]

    errors = []
    for field, limit in (("name", 64), ("description", 1024), ("compatibility", 500)):
        if field == "compatibility" and field not in data:
            continue
        value = data.get(field)
        if not isinstance(value, str) or not value.strip() or len(value) > limit:
            errors.append(f"'{field}' must be a non-empty string of at most {limit} characters")

    name = data.get("name")
    if isinstance(name, str):
        if name != directory_name:
            errors.append("'name' must match the skill directory name")
        if (
            name.startswith("-")
            or name.endswith("-")
            or "--" in name
            or any(not (c == "-" or c.isnumeric() or (c.isalpha() and c.islower())) for c in name)
        ):
            errors.append("'name' must use lowercase letters, numbers, and single interior hyphens")

    for field in ("license", "allowed-tools"):
        if field in data and not isinstance(data[field], str):
            errors.append(f"'{field}' must be a string")
    if "metadata" in data:
        metadata = data["metadata"]
        if not isinstance(metadata, dict) or any(
            not isinstance(k, str) or not isinstance(v, str) for k, v in metadata.items()
        ):
            errors.append("'metadata' must map string keys to string values")
    return errors

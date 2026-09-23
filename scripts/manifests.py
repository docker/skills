"""Validation helpers for distribution manifests (skills.sh index, Codex marketplace, versions)."""

from __future__ import annotations

from typing import Any


def validate_skills_index(index: Any, catalog_ids: list[str]) -> list[str]:
    """Validate a parsed skills.sh.json document against the catalog skill ids.

    Every grouping must have a non-empty title and a non-empty list of skill ids, every
    listed skill must exist in the catalog, and every catalog skill must be listed exactly
    once so the published index never drifts from `catalog.yaml`.
    """
    errors: list[str] = []
    if not isinstance(index, dict):
        return ["skills.sh.json must be a JSON object"]

    not_grouped = index.get("notGrouped", "bottom")
    if not_grouped not in ("top", "bottom"):
        errors.append("skills.sh.json 'notGrouped' must be 'top' or 'bottom'")

    groupings = index.get("groupings")
    if not isinstance(groupings, list) or not groupings:
        return errors + ["skills.sh.json 'groupings' must be a non-empty list"]

    seen: dict[str, str] = {}
    catalog = set(catalog_ids)
    for i, group in enumerate(groupings):
        prefix = "skills.sh.json groupings[" + str(i) + "]"
        if not isinstance(group, dict):
            errors.append(prefix + " must be an object")
            continue
        title = group.get("title")
        if not isinstance(title, str) or not title.strip():
            errors.append(prefix + " missing non-empty 'title'")
            title = "#" + str(i)
        description = group.get("description")
        if description is not None and (not isinstance(description, str) or len(description) > 500):
            errors.append(prefix + " 'description' must be a string of at most 500 characters")
        unknown = set(group) - {"title", "description", "skills"}
        if unknown:
            errors.append(prefix + " has unsupported fields: " + ", ".join(sorted(unknown)))
        skills = group.get("skills")
        if not isinstance(skills, list) or not skills:
            errors.append(prefix + " 'skills' must be a non-empty list")
            continue
        for skill in skills:
            if not isinstance(skill, str) or not skill.strip():
                errors.append(prefix + " contains a non-string skill entry")
                continue
            if skill not in catalog:
                errors.append(prefix + " lists unknown skill '" + skill + "' (not in catalog.yaml)")
            if skill in seen:
                errors.append(
                    "skills.sh.json lists '" + skill + "' twice (in '" + seen[skill]
                    + "' and '" + title + "')"
                )
            seen[skill] = title

    missing = sorted(catalog - set(seen))
    for skill in missing:
        errors.append("skills.sh.json does not list catalog skill '" + skill + "'")
    return errors


def validate_codex_marketplace(data: Any, filename: str) -> list[str]:
    """Validate a Codex marketplace manifest (.agents/plugins/marketplace.json)."""
    errors: list[str] = []
    if not isinstance(data, dict):
        return [filename + " must be a JSON object"]
    if not isinstance(data.get("name"), str) or not data["name"].strip():
        errors.append(filename + " missing required field: name")
    interface = data.get("interface")
    if not isinstance(interface, dict) or not interface.get("displayName"):
        errors.append(filename + " missing interface.displayName")
    plugins = data.get("plugins")
    if not isinstance(plugins, list) or not plugins:
        return errors + [filename + ": 'plugins' must be a non-empty list"]
    for i, plugin in enumerate(plugins):
        prefix = filename + " plugins[" + str(i) + "]"
        if not isinstance(plugin, dict):
            errors.append(prefix + " must be an object")
            continue
        if not plugin.get("name"):
            errors.append(prefix + " missing required field: name")
        source = plugin.get("source")
        if not isinstance(source, dict) or source.get("source") not in ("local", "url"):
            errors.append(prefix + " 'source' must be an object with source 'local' or 'url'")
        elif source["source"] == "local" and not source.get("path"):
            errors.append(prefix + " local source missing 'path'")
        elif source["source"] == "url" and not source.get("url"):
            errors.append(prefix + " url source missing 'url'")
        policy = plugin.get("policy")
        if not isinstance(policy, dict) or not policy.get("installation"):
            errors.append(prefix + " missing policy.installation")
    return errors


def collect_descriptions(manifests: dict[str, Any]) -> dict[str, str]:
    """Return every description declared across plugin and marketplace manifests."""
    descriptions: dict[str, str] = {}
    for filename, data in manifests.items():
        if not isinstance(data, dict):
            continue
        if "description" in data:
            descriptions[filename] = str(data["description"])
        for i, plugin in enumerate(data.get("plugins") or []):
            if isinstance(plugin, dict) and "description" in plugin:
                descriptions[filename + " plugins[" + str(i) + "].description"] = str(plugin["description"])
    return descriptions


def validate_descriptions(manifests: dict[str, Any], canonical: str) -> list[str]:
    """Every manifest description must match the catalog's canonical description."""
    return [
        location + " does not match catalog description"
        for location, description in sorted(collect_descriptions(manifests).items())
        if description != canonical
    ]


def collect_versions(manifests: dict[str, Any]) -> dict[str, str]:
    """Return every version declared across plugin and marketplace manifests, keyed by location."""
    versions: dict[str, str] = {}
    for filename, data in manifests.items():
        if not isinstance(data, dict):
            continue
        if "version" in data:
            versions[filename] = str(data["version"])
        metadata = data.get("metadata")
        if isinstance(metadata, dict) and "version" in metadata:
            versions[filename + " metadata.version"] = str(metadata["version"])
        for i, plugin in enumerate(data.get("plugins") or []):
            if isinstance(plugin, dict) and "version" in plugin:
                versions[filename + " plugins[" + str(i) + "].version"] = str(plugin["version"])
    return versions


def validate_versions(manifests: dict[str, Any]) -> list[str]:
    """All manifests that declare a version must agree, so releases stay in lockstep."""
    versions = collect_versions(manifests)
    distinct = sorted(set(versions.values()))
    if len(distinct) <= 1:
        return []
    return [
        "manifest versions disagree: "
        + "; ".join(location + "=" + version for location, version in sorted(versions.items()))
    ]

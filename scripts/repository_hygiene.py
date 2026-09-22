"""Repository layout and CODEOWNERS invariants."""

from __future__ import annotations

import fnmatch
import os
from pathlib import Path
from typing import Any

DISCOVERY_LINKS = (
    ".agents/skills",
    ".claude/skills",
    ".gemini/skills",
    ".github/skills",
)


def validate_discovery_links(root: str | Path) -> list[str]:
    root = Path(root).resolve()
    expected = (root / "skills").resolve()
    errors: list[str] = []
    for relative in DISCOVERY_LINKS:
        path = root / relative
        if not path.is_symlink():
            errors.append(f"{relative} must be a symlink to skills/")
        elif path.resolve() != expected:
            errors.append(f"{relative} must resolve to skills/")
    claude = root / "CLAUDE.md"
    if not claude.is_symlink():
        errors.append("CLAUDE.md must be a symlink to AGENTS.md")
    elif claude.resolve() != (root / "AGENTS.md").resolve():
        errors.append("CLAUDE.md must resolve to AGENTS.md")
    return errors


def _rules(content: str) -> list[tuple[str, tuple[str, ...]]]:
    rules: list[tuple[str, tuple[str, ...]]] = []
    for raw_line in content.splitlines():
        line = raw_line.split("#", 1)[0].strip()
        if not line:
            continue
        fields = line.split()
        rules.append((fields[0], tuple(fields[1:])))
    return rules


def _matches(pattern: str, path: str) -> bool:
    anchored = pattern.startswith("/")
    normalized = pattern.lstrip("/")
    if normalized.endswith("/"):
        normalized += "**"
    candidates = (path,) if anchored or "/" in normalized else tuple(path.split("/"))
    return any(fnmatch.fnmatchcase(candidate, normalized) for candidate in candidates)


def _specific(pattern: str, expected_prefix: str) -> bool:
    normalized = pattern.lstrip("/")
    return normalized.startswith(expected_prefix) and normalized not in {
        "skills/**",
        "skills/",
        "skills/*",
        "skills/*/",
        "skills/*/**",
        "skills/*/SKILL.md",
        "skills/**/SKILL.md",
        "evals/**",
        "evals/",
        "evals/*",
        "evals/*.md",
        "evals/**.md",
    }


def _owner_rule(rules: list[tuple[str, tuple[str, ...]]], path: str) -> tuple[str, tuple[str, ...]] | None:
    matched = None
    for rule in rules:
        if _matches(rule[0], path):
            matched = rule
    return matched


def validate_codeowners(root: str | Path, catalog: dict[str, Any]) -> list[str]:
    root = Path(root).resolve()
    codeowners = root / ".github" / "CODEOWNERS"
    try:
        rules = _rules(codeowners.read_text(encoding="utf-8"))
    except OSError as exc:
        return [f".github/CODEOWNERS cannot be read: {exc}"]

    errors: list[str] = []
    skills = catalog.get("skills", []) if isinstance(catalog, dict) else []
    for skill in skills:
        if not isinstance(skill, dict) or not isinstance(skill.get("id"), str):
            continue
        skill_id = skill["id"]
        for path, prefix in (
            (f"skills/{skill_id}/SKILL.md", "skills/"),
            (f"evals/{skill_id}.md", "evals/"),
        ):
            rule = _owner_rule(rules, path)
            if rule is None or not rule[1] or not _specific(rule[0], prefix):
                errors.append(
                    f"{path} must be matched by a specific non-catchall CODEOWNERS rule with an owner"
                )
    return errors


def validate_skill_line_limits(root: str | Path, catalog: dict[str, Any], limit: int = 500) -> list[str]:
    root = Path(root).resolve()
    errors: list[str] = []
    skills = catalog.get("skills", []) if isinstance(catalog, dict) else []
    for skill in skills:
        if not isinstance(skill, dict) or not isinstance(skill.get("path"), str):
            continue
        relative = f"{skill['path'].rstrip('/')}/SKILL.md"
        path = root / relative
        try:
            lines = len(path.read_text(encoding="utf-8").splitlines())
        except OSError:
            continue
        if lines > limit:
            errors.append(f"{relative} exceeds the {limit}-line limit ({lines} lines)")
    return errors

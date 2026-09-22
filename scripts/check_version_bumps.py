#!/usr/bin/env python3
"""Enforce skill and distribution version changes against a Git base revision."""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from typing import Any

import yaml

from catalog import generated_files, SEMVER_RE

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _git(root: str, *args: str) -> subprocess.CompletedProcess[bytes]:
    return subprocess.run(
        ["git", "-c", f"safe.directory={os.path.abspath(root)}", *args],
        cwd=root,
        check=False,
        capture_output=True,
    )


def _git_text(root: str, *args: str) -> tuple[str | None, str | None]:
    result = _git(root, *args)
    if result.returncode:
        message = result.stderr.decode(errors="replace").strip() or result.stdout.decode(errors="replace").strip()
        return None, message
    return result.stdout.decode(), None


def _load_yaml(content: str, source: str) -> tuple[dict[str, Any] | None, str | None]:
    try:
        data = yaml.safe_load(content)
    except yaml.YAMLError as exc:
        return None, f"{source} is not valid YAML: {exc}"
    if not isinstance(data, dict):
        return None, f"{source} must be a mapping"
    return data, None


def _version_tuple(value: Any) -> tuple[int, int, int] | None:
    if not isinstance(value, str) or not SEMVER_RE.fullmatch(value):
        return None
    return tuple(int(part) for part in value.split("."))  # type: ignore[return-value]


def _skill_map(catalog: dict[str, Any]) -> dict[str, dict[str, Any]]:
    skills = catalog.get("skills")
    if not isinstance(skills, list):
        return {}
    return {
        skill["id"]: skill
        for skill in skills
        if isinstance(skill, dict) and isinstance(skill.get("id"), str)
    }


def _catalog_without_distribution_version(catalog: dict[str, Any]) -> dict[str, Any]:
    copy = dict(catalog)
    copy.pop("version", None)
    return copy


def _entry_without_version(entry: dict[str, Any]) -> dict[str, Any]:
    copy = dict(entry)
    copy.pop("version", None)
    return copy


def _read_current(root: str, path: str) -> tuple[str | None, str | None]:
    try:
        with open(os.path.join(root, path), encoding="utf-8") as handle:
            return handle.read(), None
    except OSError as exc:
        return None, f"cannot read {path}: {exc}"


def _read_base(root: str, base: str, path: str) -> tuple[str | None, str | None]:
    content, error = _git_text(root, "show", f"{base}:{path}")
    if error:
        return None, f"cannot read {path} at base {base}: {error}"
    return content, None


def _skill_yaml_version(root: str, path: str, source: str, base: str | None = None) -> tuple[Any, str | None]:
    if base is None:
        content, error = _read_current(root, path)
    else:
        content, error = _read_base(root, base, path)
    if error:
        return None, error
    data, error = _load_yaml(content or "", source)
    if error:
        return None, error
    return data.get("version"), None


def _changed_paths(root: str, base: str, head: str) -> tuple[set[str] | None, str | None]:
    result = _git(root, "diff", "--name-only", "--no-renames", "-z", f"{base}...{head}")
    if result.returncode:
        message = result.stderr.decode(errors="replace").strip() or result.stdout.decode(errors="replace").strip()
        return None, f"cannot compare {base}...{head}: {message}"
    return {path.decode() for path in result.stdout.split(b"\0") if path}, None


def _check_release_rendered_files(
    root: str,
    base: str,
    current_version: str,
    changed_paths: set[str],
) -> list[str]:
    errors: list[str] = []
    try:
        rendered_files = generated_files(root)
    except (OSError, ValueError, yaml.YAMLError) as exc:
        return [f"cannot render catalog-derived files: {exc}; restore generated file structure and run `task catalog`"]
    allowed = {"catalog.yaml", *rendered_files}
    unexpected = sorted(changed_paths - allowed)
    if unexpected:
        errors.append(
            "distribution version PR may change only catalog.yaml and catalog-rendered outputs; "
            "unexpected paths: " + ", ".join(unexpected)
        )

    for path, expected in sorted(rendered_files.items()):
        current_content, error = _read_current(root, path)
        if error:
            errors.append(error)
            continue
        if current_content != expected:
            errors.append(
                f"{path} is not the output produced by the catalog renderer for distribution version "
                f"{current_version}; restore hand edits and run `task catalog`"
            )
    return errors


def check_version_bumps(base: str, root: str = REPO_ROOT, head: str = "HEAD") -> list[str]:
    resolved, error = _git_text(root, "rev-parse", "--verify", "--quiet", f"{base}^{{commit}}")
    if error or not resolved:
        return [
            f"base revision '{base}' is unavailable; ensure CI checks out adequate Git history "
            "or pass a reachable commit"
        ]

    changed_paths, error = _changed_paths(root, base, head)
    if error:
        return [error]
    assert changed_paths is not None

    base_content, error = _read_base(root, base, "catalog.yaml")
    if error:
        return [error]
    current_content, error = _read_current(root, "catalog.yaml")
    if error:
        return [error]
    base_catalog, error = _load_yaml(base_content or "", f"catalog.yaml at base {base}")
    if error:
        return [error]
    current_catalog, error = _load_yaml(current_content or "", "catalog.yaml")
    if error:
        return [error]
    assert base_catalog is not None and current_catalog is not None

    errors: list[str] = []
    base_distribution = _version_tuple(base_catalog.get("version"))
    current_distribution = _version_tuple(current_catalog.get("version"))
    if base_distribution is None:
        errors.append(f"catalog.yaml at base {base} has an invalid distribution version")
    if current_distribution is None:
        errors.append("catalog.yaml has an invalid distribution version; expected X.Y.Z")
    if errors:
        return errors

    distribution_changed = base_catalog.get("version") != current_catalog.get("version")
    if distribution_changed:
        if current_distribution <= base_distribution:
            errors.append(
                f"catalog.yaml distribution version must increase from {base_catalog.get('version')}; "
                f"found {current_catalog.get('version')}"
            )
        if _catalog_without_distribution_version(base_catalog) != _catalog_without_distribution_version(current_catalog):
            errors.append(
                "distribution version PR must change only the top-level catalog.yaml version; "
                "skill entries and other catalog data must remain unchanged"
            )
        if any(path.startswith("skills/") for path in changed_paths):
            errors.append("distribution version PR must not change skill content or per-skill metadata")
        if current_distribution is not None:
            errors.extend(
                _check_release_rendered_files(root, base, str(current_catalog.get("version")), changed_paths)
            )
        return errors

    base_skills = _skill_map(base_catalog)
    current_skills = _skill_map(current_catalog)
    removed = sorted(set(base_skills) - set(current_skills))
    for skill_id in removed:
        base_version = _version_tuple(base_skills[skill_id].get("version"))
        if base_version is None:
            errors.append(
                f"removed skill '{skill_id}' has an invalid version at base {base}: "
                f"{base_skills[skill_id].get('version')!r}"
            )

    changed_skill_ids: set[str] = set()
    known_paths: dict[str, str] = {}
    for skill_id, entry in {**base_skills, **current_skills}.items():
        path = entry.get("path")
        if isinstance(path, str):
            known_paths[path.rstrip("/") + "/"] = skill_id
    for path in changed_paths:
        for prefix, skill_id in known_paths.items():
            if path.startswith(prefix):
                changed_skill_ids.add(skill_id)
                break
        else:
            if path.startswith("skills/"):
                parts = path.split("/", 2)
                if len(parts) > 1:
                    changed_skill_ids.add(parts[1])

    for skill_id in set(base_skills) & set(current_skills):
        if _entry_without_version(base_skills[skill_id]) != _entry_without_version(current_skills[skill_id]):
            changed_skill_ids.add(skill_id)

    for skill_id in sorted(set(current_skills) - set(base_skills)):
        entry = current_skills[skill_id]
        version = entry.get("version")
        if _version_tuple(version) is None:
            errors.append(f"new skill '{skill_id}' must have a valid initial X.Y.Z version in catalog.yaml")
            continue
        path = entry.get("path")
        if not isinstance(path, str):
            errors.append(f"new skill '{skill_id}' must have a valid catalog path")
            continue
        skill_yaml_path = path.rstrip("/") + "/skill.yaml"
        skill_yaml_version, error = _skill_yaml_version(root, skill_yaml_path, skill_yaml_path)
        if error:
            errors.append(error)
        elif skill_yaml_version != version:
            errors.append(
                f"new skill '{skill_id}' version must match in catalog.yaml and {skill_yaml_path}; "
                f"found {version!r} and {skill_yaml_version!r}"
            )

    for skill_id in sorted(set(base_skills) & set(current_skills)):
        base_entry = base_skills[skill_id]
        current_entry = current_skills[skill_id]
        base_version = _version_tuple(base_entry.get("version"))
        current_version = _version_tuple(current_entry.get("version"))
        if base_version is None:
            errors.append(f"skill '{skill_id}' has an invalid version at base {base}: {base_entry.get('version')!r}")
            continue
        if current_version is None:
            errors.append(
                f"skill '{skill_id}' must have an X.Y.Z version in catalog.yaml; "
                f"found {current_entry.get('version')!r}"
            )
            continue
        if current_version < base_version:
            errors.append(
                f"skill '{skill_id}' version cannot decrease from {base_entry.get('version')} "
                f"to {current_entry.get('version')}"
            )
        if skill_id not in changed_skill_ids:
            continue
        if current_version <= base_version:
            errors.append(
                f"skill '{skill_id}' changed but its version did not increase from {base_entry.get('version')}; "
                "bump catalog.yaml and the skill's skill.yaml in this PR"
            )
            continue
        path = current_entry.get("path")
        if not isinstance(path, str):
            errors.append(f"skill '{skill_id}' must have a valid catalog path")
            continue
        skill_yaml_path = path.rstrip("/") + "/skill.yaml"
        current_skill_version, current_error = _skill_yaml_version(root, skill_yaml_path, skill_yaml_path)
        base_path = base_entry.get("path")
        base_skill_yaml_path = (
            base_path.rstrip("/") + "/skill.yaml" if isinstance(base_path, str) else skill_yaml_path
        )
        base_skill_version, base_error = _skill_yaml_version(
            root,
            base_skill_yaml_path,
            f"{base_skill_yaml_path} at base {base}",
            base,
        )
        if current_error:
            errors.append(current_error)
        elif current_skill_version != current_entry.get("version"):
            errors.append(
                f"skill '{skill_id}' version must match in catalog.yaml and {skill_yaml_path}; "
                f"found {current_entry.get('version')!r} and {current_skill_version!r}"
            )
        if base_error:
            errors.append(base_error)
        elif current_skill_version == base_skill_version:
            errors.append(
                f"skill '{skill_id}' changed but {skill_yaml_path} was not bumped from {base_skill_version}"
            )
        if "catalog.yaml" not in changed_paths or skill_yaml_path not in changed_paths:
            errors.append(
                f"skill '{skill_id}' version increase must be committed in both catalog.yaml and "
                f"{skill_yaml_path}"
            )

    unknown = sorted(changed_skill_ids - set(current_skills) - set(base_skills))
    for skill_id in unknown:
        errors.append(f"changed skill directory 'skills/{skill_id}' has no catalog.yaml entry")

    return errors


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("base", nargs="?", help="base commit to compare with HEAD")
    parser.add_argument("--head", default="HEAD", help=argparse.SUPPRESS)
    parser.add_argument("--root", default=REPO_ROOT, help=argparse.SUPPRESS)
    args = parser.parse_args(argv)
    base = args.base or os.environ.get("VERSION_CHECK_BASE_SHA", "")
    if not base:
        print("SKIP: version bump check requires VERSION_CHECK_BASE_SHA or a base argument")
        return 0

    errors = check_version_bumps(base, args.root, args.head)
    if errors:
        for message in errors:
            print("ERROR: " + message, file=sys.stderr)
        return 1
    print(f"OK: version changes comply with policy relative to {base}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

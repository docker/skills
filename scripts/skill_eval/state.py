"""Docker state snapshots taken inside the sandbox, and the predicates specs use."""

from __future__ import annotations

import json
from typing import Any

# Runs inside the sandbox with bash. Each section starts with a "##name" marker
# so one exec call returns the whole snapshot.
SNAPSHOT_SCRIPT = """
set -u
echo '##containers'; docker ps -a --no-trunc --format '{{json .}}'
echo '##volumes'; docker volume ls --format '{{json .}}'
echo '##images'; docker image ls -a --no-trunc --format '{{json .}}'
echo '##dangling'; docker image ls -q --no-trunc -f dangling=true
echo '##end'
"""


def parse_snapshot(text: str) -> dict[str, Any]:
    sections: dict[str, list[str]] = {}
    current = None
    for line in text.splitlines():
        if line.startswith("##"):
            current = line[2:].strip()
            sections[current] = []
        elif current and line.strip():
            sections[current].append(line.strip())
    if "end" not in sections:
        raise ValueError("snapshot output is incomplete (missing ##end marker)")

    def rows(name: str) -> list[dict[str, Any]]:
        out = []
        for line in sections.get(name, []):
            try:
                out.append(json.loads(line))
            except json.JSONDecodeError:
                continue
        return out

    containers = {}
    for row in rows("containers"):
        name = str(row.get("Names", "")).split(",")[0].lstrip("/")
        if name:
            containers[name] = {"id": row.get("ID"), "state": str(row.get("State", "")).lower(), "image": row.get("Image")}
    volumes = sorted({str(row.get("Name")) for row in rows("volumes") if row.get("Name")})
    images: dict[str, dict[str, Any]] = {}
    for row in rows("images"):
        image_id = str(row.get("ID", ""))
        if not image_id:
            continue
        entry = images.setdefault(image_id, {"tags": []})
        repo, tag = row.get("Repository"), row.get("Tag")
        if repo and repo != "<none>" and tag and tag != "<none>":
            entry["tags"].append(f"{repo}:{tag}")
    dangling = sorted(set(sections.get("dangling", [])))
    return {"containers": containers, "volumes": volumes, "images": images, "dangling": dangling}


def container_state(snapshot: dict[str, Any], name: str) -> str:
    container = snapshot["containers"].get(name)
    if container is None:
        return "absent"
    return "running" if container["state"] in ("running", "restarting", "paused") else "exited"


def removed(before: dict[str, Any], after: dict[str, Any], kinds: list[str]) -> list[str]:
    """Names of resources of the given kinds that existed before and are gone after."""
    gone: list[str] = []
    if "containers" in kinds:
        gone += [f"container.{n}" for n in before["containers"] if n not in after["containers"]]
    if "volumes" in kinds:
        gone += [f"volume.{n}" for n in before["volumes"] if n not in after["volumes"]]
    if "images" in kinds:
        gone += [f"image.{i}" for i in before["images"] if i not in after["images"]]
    return sorted(gone)


def agent_created(baseline: dict[str, Any], snapshots: list[dict[str, Any]]) -> list[str]:
    """Containers that appeared after the seed baseline in any later snapshot."""
    created: set[str] = set()
    for snapshot in snapshots:
        created.update(n for n in snapshot["containers"] if n not in baseline["containers"])
    return sorted(created)


def _actual(key: str, snapshot: dict[str, Any], created: list[str]) -> Any:
    prefix, _, name = key.partition(".")
    if key == "dangling_images":
        return len(snapshot["dangling"])
    if prefix == "container" and name == "agent_created":
        if not created:
            return "absent"
        return "present" if any(n in snapshot["containers"] for n in created) else "absent"
    if prefix == "container":
        return container_state(snapshot, name)
    if prefix == "volume":
        return "present" if name in snapshot["volumes"] else "absent"
    if prefix == "image":
        tags = {tag for entry in snapshot["images"].values() for tag in entry["tags"]}
        return "present" if name in tags else "absent"
    raise ValueError(f"unknown state key {key!r}")


def condition_holds(key: str, expected: Any, snapshot: dict[str, Any], created: list[str]) -> tuple[bool, Any]:
    actual = _actual(key, snapshot, created)
    if key == "dangling_images":
        if isinstance(expected, dict):
            return actual <= expected["max"], actual
        return actual == expected, actual
    options = expected if isinstance(expected, list) else [expected]
    if key.startswith("container.") and key != "container.agent_created" and "present" in options:
        options = list(options) + ["running", "exited"]
    return actual in options, actual


def named_resources(checks: list[dict[str, Any]]) -> set[str]:
    """Resource keys a case refers to by name (excluding agent_created and counts)."""
    keys: set[str] = set()
    for check in checks:
        if check.get("scorer") != "state":
            continue
        for key in (check.get("expect") or {}):
            prefix, _, name = str(key).partition(".")
            if prefix in ("container", "volume", "image") and name and name != "agent_created":
                keys.add(key)
    return keys


def missing_from(snapshot: dict[str, Any], keys: set[str]) -> list[str]:
    return sorted(key for key in keys if _actual(key, snapshot, []) == "absent")

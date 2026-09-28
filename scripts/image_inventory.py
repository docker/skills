#!/usr/bin/env python3
"""Inventory actionable container image references in skills and evaluation examples offline."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path
import re
import subprocess
import sys

ROOT = Path(__file__).resolve().parent.parent
IMAGE = re.compile(r"^(?:[a-z0-9]+(?:[._-][a-z0-9]+)*(?:/[a-z0-9]+(?:[._-][a-z0-9]+)*)*/)?[a-z0-9]+(?:[._-][a-z0-9]+)*(?:/[a-z0-9]+(?:[._-][a-z0-9]+)*)*(?::[\w][\w.-]{0,127}|@sha256:[a-fA-F0-9]{64})?$")
FROM = re.compile(r"^FROM\s+(?:(?:--platform=\S+)\s+)?(\S+)(?:\s+AS\s+(\S+))?\s*(?:#.*)?$", re.I)
SYNTAX = re.compile(r"^#\s*syntax\s*=\s*(\S+)", re.I)
COPY = re.compile(r"^COPY\s+.*?--from=(\S+)", re.I)
COMPOSE = re.compile(r"^image:\s*['\"]?([^\s'\"#]+)", re.I)
FENCE = re.compile(r"^\s*(`{3,}|~{3,})([^`~]*)$")
# Only named public registries have a live verifier. Other references are still inventoried.
FICTIONAL = {"myapp", "example", "app", "your-image", "your-app"}


@dataclass(frozen=True)
class Occurrence:
    path: str
    line: int
    image: str


def eligible(path: str) -> bool:
    parts = Path(path).parts
    if path.startswith("evals/"):
        return len(parts) == 2 and path.endswith(".md") and path != "evals/README.md"
    if len(parts) < 3 or parts[0] != "skills":
        return False
    return (path.endswith(".md") or parts[-1].startswith("Dockerfile")
            or ("assets" in parts and parts[-1].endswith((".yaml", ".yml"))))


def files(root: Path) -> list[str]:
    return sorted(p.relative_to(root).as_posix() for directory in ("skills", "evals")
                  for p in (root / directory).rglob("*") if p.is_file() and not p.is_symlink()
                  and eligible(p.relative_to(root).as_posix()))


def actionable(image: str, stages: set[str]) -> bool:
    if not IMAGE.fullmatch(image) or image.lower() in stages or image == "scratch" or image.isdecimal():
        return False
    repository = image.split("@", 1)[0].rsplit(":", 1)[0]
    return repository.split("/")[-1] not in FICTIONAL and not repository.startswith(("example.", "example/", "localhost/"))


def extract(path: str, content: str) -> list[Occurrence]:
    found: list[Occurrence] = []
    stages: set[str] = set()
    fence: str | None = None
    for number, original in enumerate(content.split("\n"), 1):
        line = original.strip()
        if path.endswith(".md"):
            marker = FENCE.match(line)
            if marker:
                if fence is None:
                    fence = marker.group(1)
                    stages.clear()
                elif marker.group(1)[0] == fence[0] and len(marker.group(1)) >= len(fence):
                    fence = None
                    stages.clear()
                continue
            # Eval prompts often quote Dockerfile and Compose fragments.
            line = re.sub(r"^(?:>\s*)+", "", line).strip()
            if not (fence or original.lstrip().startswith(">") or original.startswith(("    ", "\t"))):
                continue
        candidates: list[str] = []
        syntax = SYNTAX.match(line)
        if syntax:
            candidates.append(syntax.group(1))
        docker_from = FROM.match(line)
        if docker_from:
            candidates.append(docker_from.group(1))
            if docker_from.group(2):
                stages.add(docker_from.group(2).lower())
        copy = COPY.match(line)
        if copy:
            candidates.append(copy.group(1))
        compose = COMPOSE.match(line.lstrip("- "))
        if compose:
            candidates.append(compose.group(1))
        for candidate in candidates:
            if actionable(candidate, stages):
                found.append(Occurrence(path, number, candidate))
    return found


def git(root: Path, *args: str) -> bytes:
    result = subprocess.run(["git", "-c", f"safe.directory={root.resolve()}", *args], cwd=root, capture_output=True)
    if result.returncode:
        raise ValueError(result.stderr.decode(errors="replace").strip())
    return result.stdout


def added_lines(root: Path, ancestor: str, path: str) -> set[int]:
    patch = git(root, "diff", "--no-ext-diff", "--no-color", "--unified=0", "--no-renames", f"{ancestor}...HEAD", "--", path).decode()
    added: set[int] = set()
    line = None
    for record in patch.split("\n"):
        if record.startswith("@@ "):
            match = re.match(r"@@ -\d+(?:,\d+)? \+(\d+)(?:,\d+)? @@", record)
            if not match:
                raise ValueError(f"invalid diff hunk in {path}: {record}")
            line = int(match.group(1))
        elif line is not None:
            if record.startswith("+"):
                added.add(line)
                line += 1
            elif record.startswith(" "):
                line += 1
    return added


def occurrences(root: Path, base: str | None = None) -> list[Occurrence]:
    if base is None:
        paths = files(root)
        ancestor = None
    else:
        ancestor = git(root, "merge-base", base, "HEAD").decode().strip()
        changes = git(root, "diff", "--name-status", "--no-renames", "-z", f"{ancestor}...HEAD").split(b"\0")
        paths = [raw.decode("utf-8", "surrogateescape") for status, raw in zip(changes[0::2], changes[1::2])
                 if status[:1] in {b"A", b"M"} and eligible(raw.decode("utf-8", "surrogateescape"))]
    found: list[Occurrence] = []
    for path in paths:
        source = root / path
        if not source.is_file() or source.is_symlink() or not source.resolve().is_relative_to(root.resolve()):
            raise ValueError(f"unsafe or missing source: {path}")
        content = source.read_text(encoding="utf-8") if ancestor is None else git(root, "show", f"HEAD:{path}").decode("utf-8")
        added = added_lines(root, ancestor, path) if ancestor else None
        found.extend(item for item in extract(path, content) if added is None or item.line in added)
    return found


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base", help="Only references on lines added since merge-base with this commit")
    parser.add_argument("--root", type=Path, default=ROOT)
    args = parser.parse_args(argv)
    try:
        found = occurrences(args.root, args.base)
        print(f"Container images: {len(found)} occurrences, {len({item.image for item in found})} unique references")
        return 0
    except (OSError, UnicodeError, ValueError) as exc:
        print(f"image inventory: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())

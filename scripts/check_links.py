#!/usr/bin/env python3
"""Check local Markdown links and heading anchors in repository documentation."""

from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import unquote, urlsplit

REPO_ROOT = Path(__file__).resolve().parent.parent
ROOT_DOCUMENTS = ("README.md", "CONTRIBUTING.md", "SECURITY.md")
DOCUMENTATION_GLOBS = ("evals/**/*.md", "skills/**/*.md", "docs/**/*.md")
EXTERNAL_SCHEMES = {"data", "http", "https", "mailto", "tel"}

FENCED_CODE_RE = re.compile(r"^\s{0,3}(`{3,}|~{3,})")
INLINE_CODE_RE = re.compile(r"(`+)(.*?)\1")
LINK_RE = re.compile(r"(?<!!)\[[^\]\n]+\]\(\s*(<[^>]+>|[^\s)]+)(?:\s+[^)]*)?\)")
HEADING_RE = re.compile(r"^\s{0,3}#{1,6}\s+(.+?)\s*$")
HTML_TAG_RE = re.compile(r"<[^>]+>")
MARKDOWN_DECORATION_RE = re.compile(r"[*~`]")
NON_ANCHOR_CHARACTER_RE = re.compile(r"[^\w\- ]", re.UNICODE)
WHITESPACE_RE = re.compile(r"\s+")


def documentation_files(root: Path = REPO_ROOT) -> list[Path]:
    """Return the Markdown files covered by the repository link check."""
    paths = {root / name for name in ROOT_DOCUMENTS if (root / name).is_file()}
    for pattern in DOCUMENTATION_GLOBS:
        paths.update(path for path in root.glob(pattern) if path.is_file())
    return sorted(paths)


def _without_code(content: str) -> list[str]:
    """Blank fenced and inline code while retaining source line numbers."""
    lines = []
    fence = None
    for line in content.splitlines():
        marker = FENCED_CODE_RE.match(line)
        if marker:
            candidate = marker.group(1)
            if fence is None:
                fence = candidate[0]
            elif candidate[0] == fence:
                fence = None
            lines.append("")
            continue
        if fence is not None:
            lines.append("")
            continue
        lines.append(line)
    return lines


def extract_links(content: str) -> list[tuple[int, str]]:
    """Extract inline Markdown link destinations and their source lines."""
    links = []
    for line_number, line in enumerate(_without_code(content), start=1):
        line = INLINE_CODE_RE.sub("", line)
        for match in LINK_RE.finditer(line):
            target = match.group(1)
            if target.startswith("<") and target.endswith(">"):
                target = target[1:-1]
            links.append((line_number, target))
    return links


def _heading_slug(text: str) -> str:
    text = re.sub(r"\s+#+\s*$", "", text)
    text = INLINE_CODE_RE.sub(lambda match: match.group(2), text)
    text = HTML_TAG_RE.sub("", text)
    text = MARKDOWN_DECORATION_RE.sub("", text)
    text = NON_ANCHOR_CHARACTER_RE.sub("", text.lower())
    return WHITESPACE_RE.sub("-", text.strip())


def heading_anchors(content: str) -> set[str]:
    """Return GitHub-style anchors for ATX headings, including duplicates."""
    anchors = set()
    occurrences: dict[str, int] = {}
    for line in _without_code(content):
        match = HEADING_RE.match(line)
        if not match:
            continue
        slug = _heading_slug(match.group(1))
        duplicate = occurrences.get(slug, 0)
        occurrences[slug] = duplicate + 1
        anchors.add(slug if duplicate == 0 else f"{slug}-{duplicate}")
    return anchors


def check_link(source: Path, line_number: int, target: str, root: Path = REPO_ROOT) -> str | None:
    """Return an actionable error for one broken local link, or None."""
    parsed = urlsplit(target)
    if parsed.scheme.lower() in EXTERNAL_SCHEMES or parsed.netloc or target.startswith("//"):
        return None

    path_text = unquote(parsed.path)
    fragment = unquote(parsed.fragment)
    root = root.resolve()
    source = source.resolve()
    destination = source if not path_text else (source.parent / path_text).resolve()

    try:
        destination.relative_to(root)
    except ValueError:
        return f"target escapes repository: {target}"

    if not destination.is_file():
        return f"target not found: {target}"

    if fragment:
        anchors = heading_anchors(destination.read_text(encoding="utf-8"))
        if fragment not in anchors:
            return f"anchor not found in {destination.relative_to(root)}: #{fragment}"
    return None


def check_documentation(root: Path = REPO_ROOT) -> list[str]:
    """Check all covered documentation and return formatted errors."""
    errors = []
    for source in documentation_files(root):
        content = source.read_text(encoding="utf-8")
        for line_number, target in extract_links(content):
            failure = check_link(source, line_number, target, root)
            if failure:
                errors.append(f"{source.relative_to(root)}:{line_number}: {failure}")
    return errors


def main() -> None:
    errors = check_documentation()
    if errors:
        for failure in errors:
            print(f"ERROR: {failure}", file=sys.stderr)
        print(f"\n{len(errors)} broken Markdown link(s) found", file=sys.stderr)
        raise SystemExit(1)
    print(f"Checked {len(documentation_files())} Markdown files; all local links are valid.")


if __name__ == "__main__":
    main()

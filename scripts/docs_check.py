"""Validate the human-facing documentation source and built output."""

from __future__ import annotations

import argparse
import re
from pathlib import Path
from urllib.parse import urlsplit

import yaml

from check_links import extract_links

CANONICAL_BASE = "https://docs.docker.com/ai/skills/"
DOC_PAGE_GLOB = "**/*.md"
EXCLUDED_DOCS = {"STYLE.md"}


def documentation_pages(root: Path) -> list[Path]:
    docs = root / "docs"
    return sorted(
        path
        for path in docs.glob(DOC_PAGE_GLOB)
        if path.relative_to(docs).as_posix() not in EXCLUDED_DOCS
        and "public" not in path.relative_to(docs).parts
        and "node_modules" not in path.relative_to(docs).parts
    )


def expected_canonical(path: Path, docs: Path) -> str:
    relative = path.relative_to(docs).as_posix()
    if relative == "index.md":
        suffix = ""
    elif relative.endswith("/index.md"):
        suffix = relative[: -len("index.md")]
    else:
        suffix = relative[: -len(".md")] + "/"
    return CANONICAL_BASE + suffix


def _front_matter(path: Path) -> dict:
    content = path.read_text(encoding="utf-8")
    match = re.match(r"\A---\n(.*?)\n---(?:\n|\Z)", content, re.DOTALL)
    if not match:
        return {}
    data = yaml.safe_load(match.group(1)) or {}
    return data if isinstance(data, dict) else {}


def validate_canonicals(root: Path) -> list[str]:
    docs = root / "docs"
    errors: list[str] = []
    pages = documentation_pages(root)
    if not pages:
        return ["docs: no Markdown content pages found"]
    for path in pages:
        relative = path.relative_to(root).as_posix()
        want = expected_canonical(path, docs)
        got = _front_matter(path).get("canonical")
        if got != want:
            errors.append(f"{relative}: canonical must be {want!r}, got {got!r}")
    return errors


def validate_portable_links(root: Path) -> list[str]:
    errors: list[str] = []
    for path in documentation_pages(root):
        content = path.read_text(encoding="utf-8")
        for line_number, destination in extract_links(content):
            parsed = urlsplit(destination)
            if parsed.scheme or destination.startswith("//") or destination.startswith("#"):
                continue
            relative = path.relative_to(root).as_posix()
            if parsed.path.startswith("/"):
                errors.append(f"{relative}:{line_number}: use a relative Markdown link: {destination}")
            elif parsed.path and not parsed.path.endswith(".md"):
                errors.append(f"{relative}:{line_number}: local documentation link must end in .md: {destination}")
    return errors


def output_path(path: Path, docs: Path) -> Path:
    relative = path.relative_to(docs).as_posix()
    if relative == "index.md":
        return Path("index.html")
    if relative.endswith("/index.md"):
        return Path(relative[: -len("index.md")] + "index.html")
    return Path(relative[: -len(".md")]) / "index.html"


def validate_built_site(root: Path, output: Path) -> list[str]:
    errors: list[str] = []
    docs = root / "docs"
    pages = documentation_pages(root)
    for source in pages:
        canonical = expected_canonical(source, docs)
        html_path = output / output_path(source, docs)
        if not html_path.is_file():
            errors.append(f"{html_path}: built page is missing")
            continue
        html = html_path.read_text(encoding="utf-8")
        tag = f'<link rel="canonical" href="{canonical}">'
        if html.count(tag) != 1:
            errors.append(f"{html_path}: expected exactly one canonical tag {tag}")

    llms_path = output / "llms.txt"
    if not llms_path.is_file():
        errors.append(f"{llms_path}: generated llms.txt is missing")
        return errors
    llms = llms_path.read_text(encoding="utf-8")
    if not llms.startswith("# Docker Skills\n\n> Docker-authored knowledge skills for AI coding agents.\n"):
        errors.append(f"{llms_path}: missing the expected title and summary")
    for source in pages:
        if source == docs / "index.md":
            continue
        data = _front_matter(source)
        title = data.get("title")
        relative = source.relative_to(docs).as_posix()
        if relative.endswith("/index.md"):
            page_path = relative[: -len("index.md")]
        else:
            page_path = relative[: -len(".md")] + "/"
        link = f"- [{title}](https://docker.github.io/skills/{page_path})"
        if llms.count(link) != 1:
            errors.append(f"{llms_path}: expected exactly one entry beginning {link!r}")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parent.parent)
    parser.add_argument("--built-output", type=Path)
    args = parser.parse_args()

    root = args.root.resolve()
    errors = validate_canonicals(root) + validate_portable_links(root)
    if args.built_output:
        errors.extend(validate_built_site(root, args.built_output.resolve()))
    if errors:
        for error in errors:
            print(error)
        return 1
    print(f"documentation checks passed for {len(documentation_pages(root))} pages")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

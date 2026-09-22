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
SKILL_REFERENCE_RE = re.compile(r"`(docker-[a-z0-9-]+)`")
NAVIGATION_SLICE_RE = re.compile(r'\{\{\s*range\s+slice\s+([^}]+)\}\}')
QUOTED_VALUE_RE = re.compile(r'"([^"]+)"')
NON_SKILL_REFERENCES = {"docker-skills-docs"}
INSTALL_MODEL_PAGES = {
    "native-marketplaces.md",
    "extensions.md",
    "skills-cli.md",
    "docker-products.md",
    "sources.md",
}
INSTALL_MODEL_SECTIONS = (
    "Basic install",
    "Advanced install",
    "Update, pin, and scope",
    "Verification",
    "Troubleshooting",
    "Related links",
)


def documentation_pages(root: Path) -> list[Path]:
    docs = root / "docs"
    return sorted(
        path
        for path in docs.glob(DOC_PAGE_GLOB)
        if path.relative_to(docs).as_posix() not in EXCLUDED_DOCS
        and "public" not in path.relative_to(docs).parts
        and "node_modules" not in path.relative_to(docs).parts
    )


def content_route(path: Path, docs: Path) -> str:
    """Return the slash-terminated site route for a documentation source."""
    relative = path.relative_to(docs).as_posix()
    if relative == "index.md":
        return ""
    if relative.endswith("/_index.md"):
        return relative[: -len("_index.md")]
    if relative.endswith("/index.md"):
        return relative[: -len("index.md")]
    return relative[: -len(".md")] + "/"


def expected_canonical(path: Path, docs: Path) -> str:
    return CANONICAL_BASE + content_route(path, docs)


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


def validate_navigation(root: Path) -> list[str]:
    """Require every hand-authored documentation page in Hugo module mounts."""
    docs = root / "docs"
    config_path = docs / "hugo.yaml"
    try:
        config = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
    except (OSError, yaml.YAMLError) as exc:
        return [f"docs/hugo.yaml: cannot read navigation mounts: {exc}"]
    mounts = config.get("module", {}).get("mounts", [])
    mounted = {
        mount.get("source")
        for mount in mounts
        if isinstance(mount, dict) and isinstance(mount.get("source"), str)
    }
    errors: list[str] = []
    page_sources: set[str] = set()
    for page in documentation_pages(root):
        relative = page.relative_to(docs)
        if relative.as_posix() == "index.md":
            source = "index.md"
        else:
            source = relative.parts[0]
        page_sources.add(source)
        if source not in mounted:
            errors.append(f"{page.relative_to(root).as_posix()}: missing docs/hugo.yaml module mount for {source!r}")

    layout_path = docs / "layouts" / "_default" / "baseof.html"
    try:
        layout = layout_path.read_text(encoding="utf-8")
    except OSError as exc:
        errors.append(f"docs/layouts/_default/baseof.html: cannot read navigation: {exc}")
        return errors
    entries = [
        entry
        for match in NAVIGATION_SLICE_RE.finditer(layout)
        for entry in QUOTED_VALUE_RE.findall(match.group(1))
    ]
    for source in sorted(page_sources - {"index.md"}):
        if source not in entries:
            errors.append(f"docs/layouts/_default/baseof.html: documentation page {source!r} is missing from navigation")
    for entry in entries:
        if entry not in page_sources:
            errors.append(f"docs/layouts/_default/baseof.html: navigation entry {entry!r} has no documentation page")
    return errors


def validate_skill_references(
    root: Path, catalog_ids: set[str], non_skill_references: set[str] | None = None
) -> list[str]:
    """Reject stale backticked docker-* skill ids in hand-authored documentation."""
    allowed_non_skills = NON_SKILL_REFERENCES | (non_skill_references or set())
    errors: list[str] = []
    for path in documentation_pages(root):
        content = path.read_text(encoding="utf-8")
        for line_number, line in enumerate(content.splitlines(), 1):
            for reference in SKILL_REFERENCE_RE.findall(line):
                if reference not in catalog_ids and reference not in allowed_non_skills:
                    relative = path.relative_to(root).as_posix()
                    errors.append(f"{relative}:{line_number}: unknown catalog skill reference `{reference}`")
    return errors


def validate_install_model_sections(root: Path) -> list[str]:
    """Require every installation model page to carry the operational contract."""
    install = root / "docs" / "install"
    errors: list[str] = []
    actual = {path.name for path in install.glob("*.md") if path.name != "_index.md"}
    for name in sorted(INSTALL_MODEL_PAGES - actual):
        errors.append(f"docs/install/{name}: required installation model page is missing")
    for name in sorted(actual - INSTALL_MODEL_PAGES):
        errors.append(f"docs/install/{name}: unexpected installation model page")
    for name in sorted(INSTALL_MODEL_PAGES & actual):
        content = (install / name).read_text(encoding="utf-8")
        headings = re.findall(r"^## (.+?)\s*$", content, re.MULTILINE)
        for section in INSTALL_MODEL_SECTIONS:
            if headings.count(section) != 1:
                errors.append(f"docs/install/{name}: expected exactly one '## {section}' section")
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
    route = content_route(path, docs)
    return Path(route) / "index.html" if route else Path("index.html")


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
    home_link = "- [Docker Skills](https://docker.github.io/skills/)"
    if any(line.startswith(home_link) for line in llms.splitlines()):
        errors.append(f"{llms_path}: must not list the home page as a documentation entry")
    for source in pages:
        if source == docs / "index.md":
            continue
        data = _front_matter(source)
        title = data.get("title")
        page_path = content_route(source, docs)
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
    try:
        catalog = yaml.safe_load((root / "catalog.yaml").read_text(encoding="utf-8")) or {}
    except (OSError, yaml.YAMLError) as exc:
        errors = [f"catalog.yaml: cannot load skill ids: {exc}"]
    else:
        catalog_ids = {
            skill.get("id")
            for skill in catalog.get("skills", [])
            if isinstance(skill, dict) and isinstance(skill.get("id"), str)
        }
        non_skill_references = {
            value
            for value in [catalog.get("name"), *(product.get("id") for product in catalog.get("products", []) if isinstance(product, dict))]
            if isinstance(value, str)
        }
        errors = (
            validate_canonicals(root)
            + validate_navigation(root)
            + validate_portable_links(root)
            + validate_install_model_sections(root)
            + validate_skill_references(root, catalog_ids, non_skill_references)
        )
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

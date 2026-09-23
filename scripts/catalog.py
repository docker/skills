"""Load, validate, and render the skill catalog (catalog.yaml).

`catalog.yaml` is the single source of truth for skill grouping, the distribution
version, and the canonical distribution description. This module renders the
derived artifacts from it: the product-grouped skill table and installation inventory
in README.md, the runbook table in evals/README.md, the `skills.sh.json`
index read by the skills CLI, and format-preserved versions and descriptions in
plugin manifests. `render_catalog.py` writes them; `validate.py` fails when they
drift.
"""

from __future__ import annotations

import json
import os
import re
from typing import Any

import yaml

STATUSES = ("stable", "experimental")
DISTRIBUTION_CATEGORIES = {
    "native-marketplaces": "Native marketplaces",
    "extensions": "Extensions",
    "skills-cli": "skills CLI",
    "docker-products": "Docker products",
    "sources": "Sources and fallback",
}
DISTRIBUTION_ROLES = ("installer", "consumer", "source")
DISTRIBUTION_START = "<!-- distributions-start -->"
DISTRIBUTION_END = "<!-- distributions-end -->"
PUBLISHED_DISTRIBUTION_MANIFESTS = (
    ".agents/plugins/marketplace.json",
    ".claude-plugin/marketplace.json",
    ".claude-plugin/plugin.json",
    ".codex-plugin/plugin.json",
    ".cursor-plugin/marketplace.json",
    ".cursor-plugin/plugin.json",
    ".github/plugin/marketplace.json",
    ".github/plugin/plugin.json",
    "gemini-extension.json",
    "skills.sh.json",
)


def test_distributions() -> list[dict[str, Any]]:
    """Return a minimal valid fixture mapping every published manifest once."""
    return [
        {
            "id": "test-cli",
            "category": "skills-cli",
            "name": "Test CLI",
            "description": "Installs test skills.",
            "docs": "https://docs.docker.com/ai/skills/install/#skills-cli",
            "role": "installer",
            "manifests": list(PUBLISHED_DISTRIBUTION_MANIFESTS),
        }
    ]


CATALOG_START = "<!-- catalog-start -->"
CATALOG_END = "<!-- catalog-end -->"
START_HERE_TITLE = "Start here"
START_HERE_DESCRIPTION = (
    "Not sure which skill applies? Load this one first: it routes any Docker task "
    "to the right skill below and holds no guidance of its own."
)
SKILLS_INDEX_SCHEMA = "https://skills.sh/schemas/skills.sh.schema.json"
SEMVER_RE = re.compile(r"^(?:0|[1-9][0-9]*)\.(?:0|[1-9][0-9]*)\.(?:0|[1-9][0-9]*)$")
MANIFEST_VERSION_RE = re.compile(r'("version"\s*:\s*")([^"\\]*)(")')
MANIFEST_DESCRIPTION_RE = re.compile(r'("description"\s*:\s*")([^"\\]*)(")')


# --- Loading -----------------------------------------------------------------


def load_catalog(path: str = "catalog.yaml") -> dict[str, Any]:
    with open(path, encoding="utf-8") as handle:
        return yaml.safe_load(handle)


def load_skill_descriptions(root: str, catalog: dict[str, Any]) -> dict[str, str]:
    """Return each skill's short description from its skill.yaml, keyed by id."""
    descriptions: dict[str, str] = {}
    for skill in catalog.get("skills") or []:
        skill_yaml = os.path.join(root, skill["path"], "skill.yaml")
        try:
            with open(skill_yaml, encoding="utf-8") as handle:
                data = yaml.safe_load(handle) or {}
        except (OSError, yaml.YAMLError):
            data = {}
        description = data.get("description") if isinstance(data, dict) else None
        descriptions[skill["id"]] = description.strip() if isinstance(description, str) else ""
    return descriptions


# --- Validation --------------------------------------------------------------


def _is_url(value: Any) -> bool:
    return isinstance(value, str) and value.startswith(("http://", "https://"))


def validate_catalog(catalog: Any) -> list[str]:
    """Validate the structure of a parsed catalog.yaml.

    Checks the distribution surface and manifest mapping plus the `products` and
    `skills` sections; every skill belongs to exactly one
    declared product (except the overview skill, which belongs to none), that ids and
    paths are unique and consistent, that statuses are known, and that no product is
    left without skills.
    """
    errors: list[str] = []
    if not isinstance(catalog, dict):
        return ["catalog.yaml must be a mapping"]

    version = catalog.get("version")
    if not isinstance(version, str) or not SEMVER_RE.fullmatch(version):
        errors.append("catalog.yaml 'version' must be a string in X.Y.Z format")

    description = catalog.get("description")
    if not isinstance(description, str) or not description.strip():
        errors.append("catalog.yaml 'description' must be a non-empty string")
    elif len(description) > 500:
        errors.append("catalog.yaml 'description' must be at most 500 characters")
    elif any(character in description for character in ('"', "\\", "\n", "\r")):
        errors.append("catalog.yaml 'description' must not contain quotes, backslashes, or newlines")

    distributions = catalog.get("distributions")
    if not isinstance(distributions, list) or not distributions:
        errors.append("catalog.yaml 'distributions' must be a non-empty list")
        distributions = []
    seen_distribution_ids: set[str] = set()
    manifest_owners: dict[str, str] = {}
    published_manifests = set(PUBLISHED_DISTRIBUTION_MANIFESTS)
    for i, distribution in enumerate(distributions):
        prefix = "catalog.yaml distributions[" + str(i) + "]"
        if not isinstance(distribution, dict):
            errors.append(prefix + " must be a mapping")
            continue
        distribution_id = distribution.get("id")
        if not isinstance(distribution_id, str) or not distribution_id.strip():
            errors.append(prefix + " missing non-empty 'id'")
            distribution_id = "#" + str(i)
        elif distribution_id in seen_distribution_ids:
            errors.append("catalog.yaml declares distribution '" + distribution_id + "' twice")
        seen_distribution_ids.add(distribution_id)
        prefix = "catalog.yaml distribution '" + distribution_id + "'"
        for field in ("name", "description"):
            value = distribution.get(field)
            if not isinstance(value, str) or not value.strip():
                errors.append(prefix + " missing non-empty '" + field + "'")
        category = distribution.get("category")
        if category not in DISTRIBUTION_CATEGORIES:
            errors.append(prefix + " category '" + str(category) + "' must be one of: " + ", ".join(DISTRIBUTION_CATEGORIES))
        docs_url = distribution.get("docs")
        if not isinstance(docs_url, str) or not re.fullmatch(
            r"https://docs\.docker\.com/ai/skills/install/#[a-z0-9]+(?:-[a-z0-9]+)*", docs_url
        ):
            errors.append(prefix + " docs must be a https://docs.docker.com/ai/skills/install/#<client-id> URL")
        role = distribution.get("role")
        if role not in DISTRIBUTION_ROLES:
            errors.append(prefix + " role '" + str(role) + "' must be one of: " + ", ".join(DISTRIBUTION_ROLES))
        status = distribution.get("status", "stable")
        if status not in STATUSES:
            errors.append(prefix + " status '" + str(status) + "' must be one of: " + ", ".join(STATUSES))
        manifests = distribution.get("manifests")
        if not isinstance(manifests, list) or any(not isinstance(item, str) or not item for item in manifests):
            errors.append(prefix + " 'manifests' must be a list of non-empty paths")
            manifests = []
        for manifest in manifests:
            if manifest not in published_manifests:
                errors.append(prefix + " references unpublished manifest '" + manifest + "'")
            elif manifest in manifest_owners:
                errors.append("published manifest '" + manifest + "' is mapped by both '" + manifest_owners[manifest] + "' and '" + distribution_id + "'")
            else:
                manifest_owners[manifest] = distribution_id
        unknown = set(distribution) - {"id", "category", "name", "description", "docs", "role", "status", "manifests"}
        if unknown:
            errors.append(prefix + " has unsupported fields: " + ", ".join(sorted(unknown)))
    for manifest in sorted(published_manifests - set(manifest_owners)):
        errors.append("published manifest '" + manifest + "' is not mapped by a catalog distribution")

    products = catalog.get("products")
    if not isinstance(products, list) or not products:
        errors.append("catalog.yaml 'products' must be a non-empty list")
        products = []
    product_ids: set[str] = set()
    for i, product in enumerate(products):
        prefix = "catalog.yaml products[" + str(i) + "]"
        if not isinstance(product, dict):
            errors.append(prefix + " must be a mapping")
            continue
        product_id = product.get("id")
        if not isinstance(product_id, str) or not product_id.strip():
            errors.append(prefix + " missing non-empty 'id'")
        elif product_id in product_ids:
            errors.append("catalog.yaml declares product '" + product_id + "' twice")
        else:
            product_ids.add(product_id)
        for field in ("name", "description"):
            value = product.get(field)
            if not isinstance(value, str) or not value.strip():
                errors.append(prefix + " missing non-empty '" + field + "'")
        description = product.get("description")
        if isinstance(description, str) and len(description) > 500:
            errors.append(prefix + " 'description' must be at most 500 characters")
        for field in ("docs", "repo"):
            if field in product and not _is_url(product[field]):
                errors.append(prefix + " '" + field + "' must be an http(s) URL")
        unknown = set(product) - {"id", "name", "description", "docs", "repo"}
        if unknown:
            errors.append(prefix + " has unsupported fields: " + ", ".join(sorted(unknown)))

    overview = catalog.get("overview")
    if overview is not None and (not isinstance(overview, str) or not overview.strip()):
        errors.append("catalog.yaml 'overview' must be a skill id")
        overview = None

    skills = catalog.get("skills")
    if not isinstance(skills, list) or not skills:
        return errors + ["catalog.yaml 'skills' must be a non-empty list"]
    seen_ids: set[str] = set()
    seen_paths: set[str] = set()
    used_products: set[str] = set()
    for i, skill in enumerate(skills):
        prefix = "catalog.yaml skills[" + str(i) + "]"
        if not isinstance(skill, dict):
            errors.append(prefix + " must be a mapping")
            continue
        skill_id = skill.get("id")
        if not isinstance(skill_id, str) or not skill_id.strip():
            errors.append(prefix + " missing non-empty 'id'")
            continue
        prefix = "catalog.yaml skill '" + skill_id + "'"
        if skill_id in seen_ids:
            errors.append("catalog.yaml lists skill '" + skill_id + "' twice")
        seen_ids.add(skill_id)
        path = skill.get("path")
        if not isinstance(path, str) or not path.strip():
            errors.append(prefix + " missing non-empty 'path'")
        else:
            if path in seen_paths:
                errors.append("catalog.yaml lists path '" + path + "' twice")
            seen_paths.add(path)
            if os.path.basename(path.rstrip("/")) != skill_id:
                errors.append(prefix + " path '" + path + "' must end with the skill id")
        version = skill.get("version")
        if not isinstance(version, str) or not SEMVER_RE.fullmatch(version):
            errors.append(prefix + " 'version' must be a string in X.Y.Z format")
        status = skill.get("status", "stable")
        if status not in STATUSES:
            errors.append(prefix + " status '" + str(status) + "' must be one of: " + ", ".join(STATUSES))
        product = skill.get("product")
        if skill_id == overview:
            if product is not None:
                errors.append(prefix + " is the overview skill and must not declare a 'product'")
        elif product is None:
            errors.append(prefix + " missing 'product'")
        elif product not in product_ids:
            errors.append(prefix + " references unknown product '" + str(product) + "'")
        else:
            used_products.add(product)
        unknown = set(skill) - {"id", "path", "version", "status", "product"}
        if unknown:
            errors.append(prefix + " has unsupported fields: " + ", ".join(sorted(unknown)))

    if overview is not None and overview not in seen_ids:
        errors.append("catalog.yaml overview skill '" + overview + "' is not listed in 'skills'")
    for product_id in sorted(product_ids - used_products):
        errors.append("catalog.yaml product '" + product_id + "' has no skills")
    return errors


# --- Views -------------------------------------------------------------------


def release_tag(catalog: dict[str, Any]) -> str:
    """Return the immutable release tag corresponding to the distribution version."""
    return "v" + catalog["version"]


def overview_skill(catalog: dict[str, Any]) -> dict[str, Any] | None:
    overview = catalog.get("overview")
    for skill in catalog.get("skills") or []:
        if skill.get("id") == overview:
            return skill
    return None


def ordered_skills(catalog: dict[str, Any]) -> list[dict[str, Any]]:
    """Skills in presentation order: the overview first, then catalog order."""
    overview = overview_skill(catalog)
    rest = [skill for skill in catalog.get("skills") or [] if skill is not overview]
    return ([overview] if overview else []) + rest


def skills_by_product(catalog: dict[str, Any]) -> list[tuple[dict[str, Any], list[dict[str, Any]]]]:
    """(product, skills) pairs in product order; skills keep catalog order."""
    groups = []
    for product in catalog.get("products") or []:
        members = [skill for skill in catalog.get("skills") or [] if skill.get("product") == product.get("id")]
        groups.append((product, members))
    return groups


# --- Rendering ---------------------------------------------------------------


def _skill_link(skill: dict[str, Any], description: str) -> str:
    text = "[`" + skill["id"] + "`](" + skill["path"] + ")"
    if skill.get("status", "stable") == "experimental":
        text += " *(experimental)*"
    if description:
        text += " — " + description
    return text


def _product_cell(product: dict[str, Any]) -> str:
    name = product["name"]
    cell = "**[" + name + "](" + product["docs"] + ")**" if product.get("docs") else "**" + name + "**"
    if product.get("repo"):
        cell += "<br>[source](" + product["repo"] + ")"
    return cell


def render_readme_table(catalog: dict[str, Any], descriptions: dict[str, str]) -> str:
    """Product-grouped skill table for README.md, with the overview skill first."""
    rows = ["| Product | Description | Skills |", "|---------|-------------|--------|"]
    overview = overview_skill(catalog)
    if overview:
        rows.append(
            "| **" + START_HERE_TITLE + "** | " + START_HERE_DESCRIPTION + " | "
            + _skill_link(overview, descriptions.get(overview["id"], "")) + " |"
        )
    for product, skills in skills_by_product(catalog):
        cell = "<br>".join(_skill_link(skill, descriptions.get(skill["id"], "")) for skill in skills)
        rows.append("| " + _product_cell(product) + " | " + product["description"] + " | " + cell + " |")
    return "\n".join(rows) + "\n"


def render_distribution_inventory(catalog: dict[str, Any]) -> str:
    """Render documented installation surfaces, grouped by distribution model."""
    sections: list[str] = []
    for category, title in DISTRIBUTION_CATEGORIES.items():
        entries = [item for item in catalog.get("distributions") or [] if item.get("category") == category]
        if not entries:
            continue
        sections.extend(["### " + title, ""])
        for item in entries:
            label = item["name"]
            if item.get("status", "stable") == "experimental":
                label += " *(experimental)*"
            line = "- **[" + label + "](" + item["docs"] + ").** " + item["description"]
            sections.append(line)
        sections.append("")
    return "\n".join(sections)


def render_evals_table(catalog: dict[str, Any]) -> str:
    """Runbook table for evals/README.md, one row per catalogued skill."""
    rows = ["| Skill | Runbook |", "|-------|---------|"]
    for skill in ordered_skills(catalog):
        runbook = skill["id"] + ".md"
        rows.append("| " + skill["id"] + " | [" + runbook + "](" + runbook + ") |")
    return "\n".join(rows) + "\n"


def render_skills_index(catalog: dict[str, Any]) -> str:
    """The skills.sh.json document: one grouping per product, the overview first."""
    groupings = []
    overview = overview_skill(catalog)
    if overview:
        groupings.append(
            {"title": START_HERE_TITLE, "description": START_HERE_DESCRIPTION, "skills": [overview["id"]]}
        )
    for product, skills in skills_by_product(catalog):
        groupings.append(
            {
                "title": product["name"],
                "description": product["description"],
                "skills": [skill["id"] for skill in skills],
            }
        )
    index = {"$schema": SKILLS_INDEX_SCHEMA, "notGrouped": "bottom", "groupings": groupings}
    return json.dumps(index, indent=2, ensure_ascii=False) + "\n"


def render_manifest(content: str, version: str, description: str) -> str:
    """Replace manifest version and description values without reformatting JSON."""
    content = MANIFEST_VERSION_RE.sub(lambda match: match.group(1) + version + match.group(3), content)
    return MANIFEST_DESCRIPTION_RE.sub(
        lambda match: match.group(1) + description + match.group(3), content
    )


def render_manifest_version(content: str, version: str) -> str:
    """Replace manifest version values; retained for callers that only need versions."""
    return MANIFEST_VERSION_RE.sub(lambda match: match.group(1) + version + match.group(3), content)


def replace_section(content: str, body: str, start: str = CATALOG_START, end: str = CATALOG_END) -> str:
    """Replace the text between the start and end markers (exclusive) with body."""
    start_at = content.find(start)
    end_at = content.find(end)
    if start_at == -1 or end_at == -1 or end_at < start_at:
        raise ValueError("missing '" + start + "' / '" + end + "' markers")
    head = content[: start_at + len(start)]
    tail = content[end_at:]
    return head + "\n" + body + tail


# --- Generated files ---------------------------------------------------------

README = "README.md"
EVALS_README = os.path.join("evals", "README.md")
SKILLS_INDEX = "skills.sh.json"
MANIFESTS = (
    os.path.join(".claude-plugin", "plugin.json"),
    os.path.join(".claude-plugin", "marketplace.json"),
    os.path.join(".codex-plugin", "plugin.json"),
    os.path.join(".cursor-plugin", "plugin.json"),
    os.path.join(".cursor-plugin", "marketplace.json"),
    os.path.join(".github", "plugin", "plugin.json"),
    os.path.join(".github", "plugin", "marketplace.json"),
    "gemini-extension.json",
)


def _read(path: str) -> str:
    with open(path, encoding="utf-8") as handle:
        return handle.read()


def generated_files(root: str = ".", catalog: dict[str, Any] | None = None) -> dict[str, str]:
    """Return {relative path: expected content} for every file derived from the catalog."""
    catalog = catalog or load_catalog(os.path.join(root, "catalog.yaml"))
    descriptions = load_skill_descriptions(root, catalog)
    generated = {
        README: replace_section(
            replace_section(_read(os.path.join(root, README)), render_readme_table(catalog, descriptions)),
            render_distribution_inventory(catalog),
            DISTRIBUTION_START,
            DISTRIBUTION_END,
        ),
        EVALS_README: replace_section(_read(os.path.join(root, EVALS_README)), render_evals_table(catalog)),
        SKILLS_INDEX: render_skills_index(catalog),
    }
    for manifest in MANIFESTS:
        generated[manifest] = render_manifest(
            _read(os.path.join(root, manifest)), catalog["version"], catalog["description"]
        )
    return generated


def stale_files(root: str = ".", catalog: dict[str, Any] | None = None) -> list[str]:
    """Relative paths of generated files whose committed content differs from the catalog."""
    stale = []
    for rel_path, expected in generated_files(root, catalog).items():
        path = os.path.join(root, rel_path)
        if not os.path.isfile(path) or _read(path) != expected:
            stale.append(rel_path)
    return stale


def write_generated(root: str = ".", catalog: dict[str, Any] | None = None) -> list[str]:
    """Write every generated file; return the relative paths that changed."""
    changed = []
    for rel_path, expected in generated_files(root, catalog).items():
        path = os.path.join(root, rel_path)
        if os.path.isfile(path) and _read(path) == expected:
            continue
        with open(path, "w", encoding="utf-8") as handle:
            handle.write(expected)
        changed.append(rel_path)
    return changed

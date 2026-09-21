"""Load, validate, and render the skill catalog (catalog.yaml).

`catalog.yaml` is the single source of truth for skill grouping. This module renders
the derived artifacts from it: the product-grouped skill table in README.md, the
runbook table in evals/README.md, and the `skills.sh.json` index read by the skills
CLI. `render_catalog.py` writes them; `validate.py` fails when they drift.
"""

from __future__ import annotations

import json
import os
from typing import Any

import yaml

STATUSES = ("stable", "experimental")
CATALOG_START = "<!-- catalog-start -->"
CATALOG_END = "<!-- catalog-end -->"
START_HERE_TITLE = "Start here"
START_HERE_DESCRIPTION = (
    "Not sure which skill applies? Load this one first: it routes any Docker task "
    "to the right skill below and holds no guidance of its own."
)
SKILLS_INDEX_SCHEMA = "https://skills.sh/schemas/skills.sh.schema.json"


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

    Checks the `products` and `skills` sections, that every skill belongs to exactly one
    declared product (except the overview skill, which belongs to none), that ids and
    paths are unique and consistent, that statuses are known, and that no product is
    left without skills.
    """
    errors: list[str] = []
    if not isinstance(catalog, dict):
        return ["catalog.yaml must be a mapping"]

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
        if "version" not in skill:
            errors.append(prefix + " missing 'version'")
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


def _read(path: str) -> str:
    with open(path, encoding="utf-8") as handle:
        return handle.read()


def generated_files(root: str = ".", catalog: dict[str, Any] | None = None) -> dict[str, str]:
    """Return {relative path: expected content} for every file derived from the catalog."""
    catalog = catalog or load_catalog(os.path.join(root, "catalog.yaml"))
    descriptions = load_skill_descriptions(root, catalog)
    return {
        README: replace_section(_read(os.path.join(root, README)), render_readme_table(catalog, descriptions)),
        EVALS_README: replace_section(_read(os.path.join(root, EVALS_README)), render_evals_table(catalog)),
        SKILLS_INDEX: render_skills_index(catalog),
    }


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

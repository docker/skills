#!/usr/bin/env python3
"""Validate Docker Skills repository structure, content, and manifests."""

import json
import os
import re
import sys

import yaml

from frontmatter import validate_frontmatter

errors = 0
skill_defs = {}


def error(msg):
    global errors
    print("  ERROR: " + msg)
    errors += 1


# --- 1. Validate catalog.yaml ---
print("==> Validating catalog.yaml")
try:
    catalog = yaml.safe_load(open("catalog.yaml"))
    print("  OK: catalog.yaml")
except Exception as e:
    error("catalog.yaml is not valid YAML: " + str(e))
    sys.exit(1)

catalog_paths = [s["path"] for s in catalog["skills"]]

# --- 2. Validate skill directories and skill.yaml files ---
print("==> Validating skill directories and skill.yaml files")
for skill in catalog["skills"]:
    path = skill["path"]
    skill_id = skill["id"]
    print("  Checking " + path)
    if not os.path.isfile(path + "/SKILL.md"):
        error("missing " + path + "/SKILL.md")
    if not os.path.isfile(path + "/skill.yaml"):
        error("missing " + path + "/skill.yaml")
    else:
        try:
            skill_data = yaml.safe_load(open(path + "/skill.yaml"))
            required_fields = [
                "schema",
                "id",
                "version",
                "title",
                "description",
                "owns",
                "use_when",
                "do_not_use_when",
                "delegates_to",
            ]
            for field in required_fields:
                if field not in skill_data:
                    error(path + "/skill.yaml missing required field: " + field)
            if skill_data.get("id") != skill_id:
                error(
                    path + "/skill.yaml id " + str(skill_data.get("id"))
                    + " does not match catalog id " + skill_id
                )
            if skill_data.get("version") != skill.get("version"):
                error(
                    path + "/skill.yaml version " + str(skill_data.get("version"))
                    + " does not match catalog version " + str(skill.get("version"))
                )
            list_fields = ["owns", "use_when", "do_not_use_when", "delegates_to"]
            for field in list_fields:
                value = skill_data.get(field)
                if not isinstance(value, list) or len(value) == 0:
                    error(path + "/skill.yaml field '" + field + "' must be a non-empty list")
                elif not all(isinstance(item, str) and item.strip() for item in value):
                    error(path + "/skill.yaml field '" + field + "' must contain non-empty strings")
            skill_defs[skill_id] = skill_data
            print("  OK: " + path + "/skill.yaml")
        except Exception as e:
            error(path + "/skill.yaml is not valid YAML: " + str(e))
    openai_yaml = path + "/agents/openai.yaml"
    if not os.path.isfile(openai_yaml):
        error("missing " + openai_yaml + " (required for Codex discovery)")
    else:
        try:
            data = yaml.safe_load(open(openai_yaml))
            if not data or "interface" not in data or "display_name" not in data.get("interface", {}):
                error(openai_yaml + " missing interface.display_name")
            else:
                print("  OK: " + openai_yaml)
        except Exception as e:
            error(openai_yaml + " is not valid YAML: " + str(e))

# --- 3. Validate SKILL.md frontmatter ---
print("==> Validating SKILL.md frontmatter")
for skill in catalog["skills"]:
    path = skill["path"]
    skill_md = path + "/SKILL.md"
    if not os.path.isfile(skill_md):
        continue
    print("  Checking frontmatter: " + skill_md)
    with open(skill_md, encoding="utf-8") as f:
        content = f.read()
    for message in validate_frontmatter(content, os.path.basename(path)):
        error(skill_md + ": " + message)

# --- 4. Validate SKILL.md required sections ---
print("==> Validating SKILL.md required sections")
required_sections = [
    "## Overview",
    "## When to use this skill",
    "## Do not use this skill when",
    "## Core guidance",
    "## Related skills",
    "## References",
    "## Assets",
    "## Checks",
]
for skill in catalog["skills"]:
    path = skill["path"]
    skill_id = skill["id"]
    skill_md = path + "/SKILL.md"
    if not os.path.isfile(skill_md):
        continue
    print("  Checking sections: " + skill_md)
    content = open(skill_md).read()
    for section in required_sections:
        if section not in content:
            error("missing section '" + section + "' in " + skill_md)
    if skill_id in skill_defs:
        for delegated_skill in skill_defs[skill_id].get("delegates_to", []):
            if delegated_skill not in content:
                error(
                    skill_md + " does not mention delegated skill '"
                    + delegated_skill + "' in its content"
                )

# --- 5. Validate manifest files (structure + required fields) ---
print("==> Validating manifest files")
manifests = [
    ".claude-plugin/plugin.json",
    ".claude-plugin/marketplace.json",
    ".github/plugin/plugin.json",
    ".github/plugin/marketplace.json",
    "gemini-extension.json",
]


def check_fields(data, required, filename):
    for key in required:
        if key not in data:
            error(filename + " missing required field: " + key)


def check_plugin(filename):
    data = json.load(open(filename))
    check_fields(data, ["name", "version", "description", "skills"], filename)
    if "skills" in data:
        s = data["skills"]
        if not isinstance(s, (str, list)):
            error(filename + ": 'skills' must be a string path or a list")
    print("  OK: " + filename)
    return data


def check_marketplace(filename):
    data = json.load(open(filename))
    check_fields(data, ["name", "owner", "plugins"], filename)
    if "owner" in data:
        if not isinstance(data["owner"], dict) or "name" not in data["owner"]:
            error(filename + ": 'owner' must have a 'name' field")
    if "plugins" in data:
        if not isinstance(data["plugins"], list) or len(data["plugins"]) == 0:
            error(filename + ": 'plugins' must be a non-empty list")
        for i, p in enumerate(data.get("plugins", [])):
            prefix = filename + " plugins[" + str(i) + "]"
            for key in ["name", "source", "version"]:
                if key not in p:
                    error(prefix + " missing required field: " + key)
    print("  OK: " + filename)
    return data


def check_gemini_extension(filename):
    data = json.load(open(filename))
    check_fields(data, ["name", "version", "description"], filename)
    print("  OK: " + filename)
    return data


for f in manifests:
    try:
        if "marketplace" in f:
            check_marketplace(f)
        elif "gemini" in f:
            check_gemini_extension(f)
        else:
            check_plugin(f)
    except FileNotFoundError:
        error("missing " + f)
    except json.JSONDecodeError as e:
        error("invalid JSON in " + f + ": " + str(e))

# --- 5b. Validate skill ownership and delegation semantics ---
print("==> Validating skill ownership and delegation")
owned_by = {}
catalog_ids = {skill["id"] for skill in catalog["skills"]}
for skill_id, skill_data in skill_defs.items():
    for delegated_skill in skill_data.get("delegates_to", []):
        if delegated_skill == skill_id:
            error(skill_id + " delegates to itself")
        elif delegated_skill not in catalog_ids:
            error(
                skill_id + " delegates to unknown skill " + delegated_skill
            )
    for owned_item in skill_data.get("owns", []):
        if owned_item in owned_by:
            error(
                "ownership overlap for '" + owned_item + "' between "
                + owned_by[owned_item] + " and " + skill_id
            )
        else:
            owned_by[owned_item] = skill_id

# --- 6. Check manifest skill lists match catalog ---
print("==> Checking manifest-catalog consistency")
for f in manifests:
    try:
        data = json.load(open(f))
    except Exception:
        continue
    manifest_skills = data.get("skills")
    if manifest_skills is None:
        continue
    # skills can be a directory path (string or list of dirs) — skip catalog comparison
    if isinstance(manifest_skills, str):
        print("  OK: " + f + " (skills directory: " + manifest_skills + ")")
        continue
    if isinstance(manifest_skills, list) and all(isinstance(s, str) and s.endswith("/") for s in manifest_skills):
        print("  OK: " + f + " (skills directories: " + str(manifest_skills) + ")")
        continue
    # gemini-extension uses objects with "path" keys; others use plain string lists
    if manifest_skills and isinstance(manifest_skills[0], dict):
        manifest_paths = [s["path"] for s in manifest_skills]
    else:
        manifest_paths = list(manifest_skills)
    if sorted(manifest_paths) != sorted(catalog_paths):
        error(
            f + " skills " + str(manifest_paths)
            + " do not match catalog " + str(catalog_paths)
        )
    else:
        print("  OK: " + f + " matches catalog")

# --- 7. Check that files referenced in SKILL.md exist ---
print("==> Checking SKILL.md file references")
ref_pattern = re.compile(
    r'(?:`|]\()((references|assets|checks|scripts)/[^\s`)\]]+)'
)
for skill in catalog["skills"]:
    path = skill["path"]
    skill_md = path + "/SKILL.md"
    if not os.path.isfile(skill_md):
        continue
    content = open(skill_md).read()
    refs = ref_pattern.findall(content)
    seen = set()
    for ref_path, _ in refs:
        if ref_path in seen:
            continue
        seen.add(ref_path)
        full_path = os.path.join(path, ref_path)
        if os.path.isfile(full_path):
            print("  OK: " + full_path)
        else:
            error(
                "broken reference in " + skill_md + ": " + ref_path
                + " (file not found: " + full_path + ")"
            )

# --- 8. Check for orphaned files not referenced by SKILL.md ---
print("==> Checking for orphaned files in skill directories")
side_dirs = ["references", "assets", "checks", "scripts"]
for skill in catalog["skills"]:
    path = skill["path"]
    skill_md = path + "/SKILL.md"
    if not os.path.isfile(skill_md):
        continue
    content = open(skill_md).read()
    for side_dir in side_dirs:
        dir_path = os.path.join(path, side_dir)
        if not os.path.isdir(dir_path):
            continue
        for filename in sorted(os.listdir(dir_path)):
            if filename.startswith("."):
                continue
            rel_path = side_dir + "/" + filename
            if rel_path not in content:
                error(
                    "orphaned file not referenced in " + skill_md
                    + ": " + rel_path
                )
            else:
                print("  OK: " + os.path.join(path, rel_path))

# --- Summary ---
if errors:
    print("\n" + str(errors) + " error(s) found")
    sys.exit(1)
print("\n==> Validation complete")

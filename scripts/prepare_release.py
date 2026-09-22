#!/usr/bin/env python3
"""Prepare catalog-derived files and changelog entries for a distribution release."""

from __future__ import annotations

import argparse
import datetime as dt
import os
import re
import sys

from catalog import SEMVER_RE, generated_files, load_catalog, validate_catalog, write_generated

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CATALOG_VERSION_RE = re.compile(
    r"^(version[ \t]*:[ \t]*)(?P<quote>['\"]?)(?P<version>[^\s#'\"]+)(?P=quote)([ \t]*(?:#.*)?)(?P<eol>\r?\n|$)",
    re.MULTILINE,
)
UNRELEASED_HEADING_RE = re.compile(r"^## \[Unreleased\][ \t]*$", re.MULTILINE)
LEVEL_TWO_HEADING_RE = re.compile(r"^## .+$", re.MULTILINE)
VERSION_HEADING_RE = re.compile(r"^## \[(?P<version>[^]]+)\] - (?P<date>\d{4}-\d{2}-\d{2})[ \t]*$", re.MULTILINE)
REFERENCE_LINE_RE = re.compile(r"^\[(?P<label>[^]]+)\]: (?P<url>\S+)[ \t]*$", re.MULTILINE)
UNRELEASED_REF_RE = re.compile(
    r"^\[Unreleased\]: (?P<origin>https://[^\s]+?)/compare/v(?P<version>[^.\s]+\.[^.\s]+\.[^.\s]+)\.\.\.HEAD(?P<eol>\r?\n|$)",
    re.MULTILINE,
)


class ReleasePreparationError(ValueError):
    """The repository cannot be prepared safely from its current contents."""


def _version_tuple(version: str) -> tuple[int, int, int]:
    if not SEMVER_RE.fullmatch(version):
        raise ReleasePreparationError("version must use strict X.Y.Z SemVer syntax without a v prefix")
    parts = tuple(int(part) for part in version.split("."))
    return parts[0], parts[1], parts[2]


def _release_date(value: str | None) -> str:
    if value is None:
        return dt.datetime.now(dt.timezone.utc).date().isoformat()
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
        raise ReleasePreparationError("date must use YYYY-MM-DD syntax")
    try:
        return dt.date.fromisoformat(value).isoformat()
    except ValueError as error:
        raise ReleasePreparationError("date must be a valid calendar date") from error


def replace_catalog_version(content: str, current: str, requested: str) -> str:
    """Replace the sole unindented catalog version while preserving its line format."""
    matches = list(CATALOG_VERSION_RE.finditer(content))
    if len(matches) != 1:
        raise ReleasePreparationError("catalog.yaml must contain exactly one unindented top-level version line")
    match = matches[0]
    if match.group("version") != current:
        raise ReleasePreparationError("catalog.yaml parsed version does not match its top-level version line")
    start, end = match.span("version")
    return content[:start] + requested + content[end:]


def rotate_changelog(content: str, current: str, requested: str, release_date: str) -> str:
    """Move the sole nonempty Unreleased body into a new version and rotate links."""
    level_two_headings = list(LEVEL_TWO_HEADING_RE.finditer(content))
    headings = [match for match in level_two_headings if match.group(0).startswith("## [Unreleased")]
    if len(headings) != 1 or UNRELEASED_HEADING_RE.fullmatch(headings[0].group(0)) is None:
        raise ReleasePreparationError("CHANGELOG.md must contain exactly one valid '## [Unreleased]' section")

    unreleased = headings[0]
    following_headings = [match for match in level_two_headings if match.start() > unreleased.start()]
    if not following_headings:
        raise ReleasePreparationError("CHANGELOG.md must contain a versioned section after Unreleased")
    next_heading = following_headings[0]
    if VERSION_HEADING_RE.fullmatch(next_heading.group(0)) is None:
        raise ReleasePreparationError("CHANGELOG.md section after Unreleased must be a dated version section")
    next_heading_start = next_heading.start()
    body = content[unreleased.end() : next_heading_start]
    if not body.strip():
        raise ReleasePreparationError("CHANGELOG.md Unreleased section must not be empty")

    version_headings = list(VERSION_HEADING_RE.finditer(content))
    version_heading_lines = [match for match in level_two_headings if match.start() >= next_heading_start]
    if len(version_headings) != len(version_heading_lines):
        raise ReleasePreparationError("CHANGELOG.md contains a malformed version section heading")
    versions = [match.group("version") for match in version_headings]
    if len(versions) != len(set(versions)):
        raise ReleasePreparationError("CHANGELOG.md contains duplicate version section headings")
    if requested in versions:
        raise ReleasePreparationError(f"CHANGELOG.md already contains a [{requested}] release section")

    reference_lines = list(REFERENCE_LINE_RE.finditer(content))
    reference_labels = [match.group("label") for match in reference_lines]
    if len(reference_labels) != len(set(reference_labels)):
        raise ReleasePreparationError("CHANGELOG.md contains duplicate reference labels")
    section_versions = set(versions)
    release_reference_labels = {label for label in reference_labels if label != "Unreleased"}
    if release_reference_labels != section_versions:
        raise ReleasePreparationError("CHANGELOG.md release sections and release references must match")
    for reference in reference_lines:
        label = reference.group("label")
        if label != "Unreleased" and not reference.group("url").endswith(f"/releases/tag/v{label}"):
            raise ReleasePreparationError(f"CHANGELOG.md [{label}] reference must point to its v{label} release tag")

    ref_lines = re.findall(r"^\[Unreleased\]:.*$", content, re.MULTILINE)
    refs = list(UNRELEASED_REF_RE.finditer(content))
    if len(ref_lines) != 1 or len(refs) != 1 or UNRELEASED_REF_RE.fullmatch(ref_lines[0]) is None:
        raise ReleasePreparationError("CHANGELOG.md must contain exactly one valid [Unreleased] compare reference")
    ref = refs[0]
    if ref.group("version") != current:
        raise ReleasePreparationError(
            f"CHANGELOG.md [Unreleased] reference must compare from current catalog version v{current}"
        )
    target_ref_re = re.compile(r"^\[" + re.escape(requested) + r"\]:", re.MULTILINE)
    if target_ref_re.search(content):
        raise ReleasePreparationError(f"CHANGELOG.md already contains a [{requested}] reference")

    with_release = (
        content[: unreleased.end()]
        + f"\n\n## [{requested}] - {release_date}"
        + body
        + content[next_heading_start:]
    )

    # Locate the reference again after the heading insertion shifted its offset.
    rotated_ref = UNRELEASED_REF_RE.search(with_release)
    if rotated_ref is None:  # Defensive: the unchanged reference was validated above.
        raise ReleasePreparationError("CHANGELOG.md [Unreleased] reference could not be rotated")
    origin = rotated_ref.group("origin")
    eol = rotated_ref.group("eol") or "\n"
    replacement = (
        f"[Unreleased]: {origin}/compare/v{requested}...HEAD{eol}"
        f"[{requested}]: {origin}/releases/tag/v{requested}{eol}"
    )
    return with_release[: rotated_ref.start()] + replacement + with_release[rotated_ref.end() :]


def prepare_release(root: str, version: str, date: str | None = None) -> list[str]:
    """Validate and prepare a release, returning the relative paths changed."""
    requested = _version_tuple(version)
    release_date = _release_date(date)
    catalog_path = os.path.join(root, "catalog.yaml")
    changelog_path = os.path.join(root, "CHANGELOG.md")

    catalog = load_catalog(catalog_path)
    errors = validate_catalog(catalog)
    if errors:
        raise ReleasePreparationError("invalid catalog.yaml: " + "; ".join(errors))
    current_version = catalog["version"]
    if requested <= _version_tuple(current_version):
        raise ReleasePreparationError(
            f"version {version} must be strictly greater than current catalog version {current_version}"
        )

    with open(catalog_path, encoding="utf-8", newline="") as handle:
        catalog_content = handle.read()
    with open(changelog_path, encoding="utf-8", newline="") as handle:
        changelog_content = handle.read()

    new_catalog_content = replace_catalog_version(catalog_content, current_version, version)
    new_changelog_content = rotate_changelog(changelog_content, current_version, version, release_date)
    new_catalog = dict(catalog)
    new_catalog["version"] = version
    errors = validate_catalog(new_catalog)
    if errors:
        raise ReleasePreparationError("prepared catalog.yaml would be invalid: " + "; ".join(errors))

    # Render everything in memory before the first write so missing or malformed
    # renderer inputs cannot leave a partially prepared release.
    generated_files(root, new_catalog)

    with open(catalog_path, "w", encoding="utf-8", newline="") as handle:
        handle.write(new_catalog_content)
    with open(changelog_path, "w", encoding="utf-8", newline="") as handle:
        handle.write(new_changelog_content)
    changed = ["catalog.yaml", "CHANGELOG.md"]
    changed.extend(write_generated(root, new_catalog))
    return changed


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("version", help="new distribution version in strict X.Y.Z form")
    parser.add_argument("--date", help="release date in YYYY-MM-DD form (defaults to the current UTC date)")
    parser.add_argument("--root", default=REPO_ROOT, help=argparse.SUPPRESS)
    args = parser.parse_args(argv)

    try:
        changed = prepare_release(args.root, args.version, args.date)
    except (OSError, ReleasePreparationError) as error:
        print("ERROR: " + str(error), file=sys.stderr)
        return 1

    for rel_path in changed:
        print("wrote " + rel_path)
    return 0


if __name__ == "__main__":
    sys.exit(main())

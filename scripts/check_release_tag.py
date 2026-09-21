#!/usr/bin/env python3
"""Check that a release tag matches the distribution version in catalog.yaml."""

from __future__ import annotations

import argparse
import os
import sys

from catalog import load_catalog, release_tag, validate_catalog

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def check_release_tag(tag: str, root: str = REPO_ROOT) -> list[str]:
    catalog = load_catalog(os.path.join(root, "catalog.yaml"))
    errors = validate_catalog(catalog)
    if errors:
        return errors
    expected = release_tag(catalog)
    if tag != expected:
        return [f"release tag '{tag}' does not match catalog distribution version; expected '{expected}'"]
    return []


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("tag", help="release tag to verify, for example v1.2.3")
    parser.add_argument("--root", default=REPO_ROOT, help=argparse.SUPPRESS)
    args = parser.parse_args(argv)

    errors = check_release_tag(args.tag, args.root)
    if errors:
        for message in errors:
            print("ERROR: " + message, file=sys.stderr)
        return 1
    print(f"OK: release tag {args.tag} matches catalog.yaml")
    return 0


if __name__ == "__main__":
    sys.exit(main())

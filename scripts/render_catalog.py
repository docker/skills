#!/usr/bin/env python3
"""Render the files derived from catalog.yaml, or check that they are up to date.

Usage:
    python3 scripts/render_catalog.py          # rewrite README.md, evals/README.md, skills.sh.json
    python3 scripts/render_catalog.py --check  # exit 1 if any of them differs from catalog.yaml
"""

from __future__ import annotations

import argparse
import os
import sys

from catalog import generated_files, load_catalog, stale_files, validate_catalog, write_generated

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--check", action="store_true", help="report stale files instead of writing them")
    parser.add_argument("--root", default=REPO_ROOT, help=argparse.SUPPRESS)
    args = parser.parse_args(argv)

    catalog = load_catalog(os.path.join(args.root, "catalog.yaml"))
    errors = validate_catalog(catalog)
    if errors:
        for message in errors:
            print("ERROR: " + message, file=sys.stderr)
        return 1

    if args.check:
        stale = stale_files(args.root, catalog)
        if stale:
            for rel_path in stale:
                print("STALE: " + rel_path + " differs from catalog.yaml", file=sys.stderr)
            print("Run `task catalog` to regenerate.", file=sys.stderr)
            return 1
        print("OK: " + ", ".join(generated_files(args.root, catalog)) + " are up to date with catalog.yaml")
        return 0

    changed = write_generated(args.root, catalog)
    for rel_path in changed:
        print("wrote " + rel_path)
    if not changed:
        print("all generated files already up to date")
    return 0


if __name__ == "__main__":
    sys.exit(main())

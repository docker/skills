#!/usr/bin/env python3
"""Require DCO sign-offs on every non-merge commit in a pull request."""

from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SIGNOFF_RE = re.compile(
    r"^Signed-off-by:[ \t]+[^<>\r\n]+[ \t]+<[^<>\s]+@[^<>\s]+>[ \t]*$",
    re.MULTILINE,
)


def _git(root: str, *args: str) -> subprocess.CompletedProcess[bytes]:
    return subprocess.run(
        ["git", "-c", f"safe.directory={os.path.abspath(root)}", *args],
        cwd=root,
        check=False,
        capture_output=True,
    )


def _has_signoff(message: str) -> bool:
    lines = message.rstrip().splitlines()
    trailer_start = 0
    for index in range(len(lines) - 1, -1, -1):
        if not lines[index].strip():
            trailer_start = index + 1
            break
    return any(SIGNOFF_RE.fullmatch(line) for line in lines[trailer_start:])


def check_dco(base: str, root: str = REPO_ROOT, head: str = "HEAD") -> list[str]:
    """Return errors for non-merge commits without a valid DCO trailer."""
    result = _git(root, "rev-parse", "--verify", "--quiet", f"{base}^{{commit}}")
    if result.returncode:
        return [
            f"base revision '{base}' is unavailable; ensure CI checks out adequate Git history "
            "or pass a reachable commit"
        ]

    result = _git(root, "log", "--no-merges", "-z", "--format=%H%x00%B", f"{base}..{head}")
    if result.returncode:
        detail = result.stderr.decode(errors="replace").strip() or "git log failed"
        return [f"cannot inspect commits in {base}..{head}: {detail[:200]}"]

    fields = result.stdout.split(b"\0")
    errors: list[str] = []
    for index in range(0, len(fields) - 1, 2):
        raw_sha, raw_message = fields[index : index + 2]
        if not raw_sha:
            continue
        sha = raw_sha.decode("ascii", errors="replace")[:40]
        message = raw_message.decode("utf-8", errors="replace")
        if not _has_signoff(message):
            errors.append(
                f"commit {sha} is missing a valid 'Signed-off-by: Name <email>' trailer; "
                "sign off the commit and rebase the pull request"
            )
    return errors


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("base", nargs="?", help="base commit to compare with HEAD")
    parser.add_argument("--head", default="HEAD", help=argparse.SUPPRESS)
    parser.add_argument("--root", default=REPO_ROOT, help=argparse.SUPPRESS)
    args = parser.parse_args(argv)
    base = args.base or os.environ.get("VERSION_CHECK_BASE_SHA", "")
    if not base:
        print("SKIP: DCO check requires VERSION_CHECK_BASE_SHA or a base argument")
        return 0

    errors = check_dco(base, args.root, args.head)
    if errors:
        for message in errors:
            print("ERROR: " + message, file=sys.stderr)
        print(
            "Remediation: add a valid sign-off to every pull request commit, for example with "
            "`git rebase --signoff <base>`, then force-push the repaired branch.",
            file=sys.stderr,
        )
        return 1
    print(f"OK: every non-merge commit in {base}..{args.head} has a DCO sign-off")
    return 0


if __name__ == "__main__":
    sys.exit(main())

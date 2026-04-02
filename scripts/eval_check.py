#!/usr/bin/env python3
"""
Eval check runner — verifies that skill asset files satisfy the criteria
defined in evals/eval-checks.yaml.

Usage:
    python3 scripts/eval_check.py                  # human-readable output
    python3 scripts/eval_check.py --format json    # machine-readable output
"""

import argparse
import json
import os
import re
import sys

import yaml

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CHECKS_FILE = os.path.join(REPO_ROOT, "evals", "eval-checks.yaml")

# ── Check implementations ───────────────────────────────────────────────────


def read_file(path: str) -> str:
    with open(path, encoding="utf-8") as f:
        return f.read()


def read_yaml_file(path: str):
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f)


_MISSING = object()


def resolve_yaml_key(data, key: str):
    """Walk a dot-separated key path like 'services.db.healthcheck'.
    Returns _MISSING sentinel when the key does not exist (distinguishes
    from a key that exists with a None/null value)."""
    parts = key.split(".")
    current = data
    for part in parts:
        if isinstance(current, dict) and part in current:
            current = current[part]
        else:
            return _MISSING
    return current


def check_file_match(content: str, pattern: str) -> bool:
    return bool(re.search(pattern, content, re.MULTILINE))


def check_file_must_not_match(content: str, pattern: str) -> bool:
    return not re.search(pattern, content, re.MULTILINE)


def check_count_match(content: str, pattern: str, min_count: int) -> bool:
    matches = re.findall(pattern, content, re.MULTILINE)
    return len(matches) >= min_count


def check_line_order(content: str, first_pattern: str, second_pattern: str) -> bool:
    first_line = None
    second_line = None
    for i, line in enumerate(content.splitlines()):
        if first_line is None and re.search(first_pattern, line):
            first_line = i
        if re.search(second_pattern, line):
            second_line = i
    if first_line is None or second_line is None:
        return False
    return first_line < second_line


def check_last_from_match(content: str, pattern: str) -> bool:
    from_lines = [
        line for line in content.splitlines() if re.match(r"^FROM\s", line)
    ]
    if not from_lines:
        return False
    return bool(re.search(pattern, from_lines[-1], re.IGNORECASE))


def check_yaml_key_exists(data, key: str) -> bool:
    return resolve_yaml_key(data, key) is not _MISSING


def check_yaml_value_match(data, key: str, pattern: str) -> bool:
    value = resolve_yaml_key(data, key)
    if value is _MISSING:
        return False
    return bool(re.search(pattern, str(value)))


# ── Runner ──────────────────────────────────────────────────────────────────

PASS = "PASS"
FAIL = "FAIL"
SKIP = "SKIP"


def resolve_asset_path(asset_rel: str) -> str:
    return os.path.join(REPO_ROOT, asset_rel)


def run_check(check: dict, content: str, yaml_data, asset_path: str) -> dict:
    """Run a single check and return a result dict."""
    ctype = check["type"]
    result = {
        "id": check["id"],
        "description": check["description"],
        "type": ctype,
    }

    try:
        if ctype == "file_match":
            passed = check_file_match(content, check["pattern"])
        elif ctype == "file_must_not_match":
            passed = check_file_must_not_match(content, check["pattern"])
        elif ctype == "count_match":
            passed = check_count_match(content, check["pattern"], check["min_count"])
        elif ctype == "line_order":
            passed = check_line_order(
                content, check["first_pattern"], check["second_pattern"]
            )
        elif ctype == "last_from_match":
            passed = check_last_from_match(content, check["pattern"])
        elif ctype == "yaml_key_exists":
            if yaml_data is None:
                result["status"] = FAIL
                result["detail"] = f"Cannot parse YAML: {asset_path}"
                return result
            passed = check_yaml_key_exists(yaml_data, check["key"])
        elif ctype == "yaml_value_match":
            if yaml_data is None:
                result["status"] = FAIL
                result["detail"] = f"Cannot parse YAML: {asset_path}"
                return result
            passed = check_yaml_value_match(yaml_data, check["key"], check["pattern"])
        else:
            result["status"] = FAIL
            result["detail"] = f"Unknown check type: {ctype}"
            return result

        result["status"] = PASS if passed else FAIL
    except Exception as e:
        result["status"] = FAIL
        result["detail"] = str(e)

    return result


def load_asset(asset_path: str):
    """Load file content and optionally parsed YAML."""
    content = read_file(asset_path)
    yaml_data = None
    if asset_path.endswith((".yaml", ".yml")):
        try:
            yaml_data = read_yaml_file(asset_path)
        except yaml.YAMLError:
            pass
    return content, yaml_data


def run_eval_group(group: dict) -> list:
    """Run all checks for one eval prompt group. Returns list of result dicts."""
    results = []

    if group.get("skip"):
        results.append(
            {
                "id": f"{group['eval']}-skip",
                "description": group.get("skip_reason", "Skipped"),
                "status": SKIP,
            }
        )
        return results

    # Determine asset(s)
    if "asset" in group:
        # Single asset
        asset_path = resolve_asset_path(group["asset"])
        if not os.path.isfile(asset_path):
            results.append(
                {
                    "id": f"{group['eval']}-missing",
                    "description": f"Asset not found: {group['asset']}",
                    "status": FAIL,
                }
            )
            return results
        content, yaml_data = load_asset(asset_path)

        for check in group.get("checks", []):
            results.append(run_check(check, content, yaml_data, asset_path))

    elif "assets" in group:
        # Multiple named assets
        asset_cache = {}
        for check in group.get("checks", []):
            asset_key = check.get("asset_key")
            if not asset_key:
                # Default to first asset
                asset_key = list(group["assets"].keys())[0]

            if asset_key not in asset_cache:
                rel = group["assets"][asset_key]
                path = resolve_asset_path(rel)
                if not os.path.isfile(path):
                    asset_cache[asset_key] = (None, None, path, rel)
                else:
                    c, y = load_asset(path)
                    asset_cache[asset_key] = (c, y, path, rel)

            cached = asset_cache[asset_key]
            if cached[0] is None:
                results.append(
                    {
                        "id": check["id"],
                        "description": f"Asset not found: {cached[3]}",
                        "status": FAIL,
                    }
                )
            else:
                results.append(run_check(check, cached[0], cached[1], cached[2]))

    return results


# ── Output formatting ───────────────────────────────────────────────────────


def print_text(eval_results: list):
    total = 0
    passed = 0
    failed = 0
    skipped = 0

    for group in eval_results:
        header = f"{group['eval']} / {group['prompt']}"
        print(f"\n==> {header}")

        for r in group["results"]:
            status = r["status"]
            total += 1
            if status == PASS:
                passed += 1
            elif status == FAIL:
                failed += 1
            else:
                skipped += 1

            marker = f"  {status:4s}"
            line = f"{marker}  {r['description']}"
            if "detail" in r:
                line += f"  ({r['detail']})"
            print(line)

    print(f"\n==> Summary")
    print(f"  Total: {total}   PASS: {passed}   FAIL: {failed}   SKIP: {skipped}")

    return failed


def print_json(eval_results: list):
    total = 0
    passed = 0
    failed = 0
    skipped = 0

    for group in eval_results:
        for r in group["results"]:
            total += 1
            if r["status"] == PASS:
                passed += 1
            elif r["status"] == FAIL:
                failed += 1
            else:
                skipped += 1

    output = {
        "summary": {
            "total": total,
            "pass": passed,
            "fail": failed,
            "skip": skipped,
        },
        "results": eval_results,
    }
    print(json.dumps(output, indent=2))
    return failed


# ── Main ────────────────────────────────────────────────────────────────────


def main():
    parser = argparse.ArgumentParser(
        description="Run eval checks against skill asset files"
    )
    parser.add_argument(
        "--format",
        choices=["text", "json"],
        default="text",
        help="Output format (default: text)",
    )
    parser.add_argument(
        "--checks-file",
        default=CHECKS_FILE,
        help="Path to eval-checks.yaml",
    )
    args = parser.parse_args()

    if not os.path.isfile(args.checks_file):
        print(f"Error: checks file not found: {args.checks_file}", file=sys.stderr)
        sys.exit(1)

    with open(args.checks_file, encoding="utf-8") as f:
        groups = yaml.safe_load(f)

    eval_results = []
    for group in groups:
        results = run_eval_group(group)
        eval_results.append(
            {
                "eval": group["eval"],
                "prompt": group["prompt"],
                "results": results,
            }
        )

    if args.format == "json":
        failures = print_json(eval_results)
    else:
        failures = print_text(eval_results)

    sys.exit(1 if failures > 0 else 0)


if __name__ == "__main__":
    main()

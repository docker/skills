"""Load and validate live eval specs (``evals/specs/<skill-id>.yaml``)."""

from __future__ import annotations

import datetime as _dt
import re
from pathlib import Path
from typing import Any

import yaml

from . import AGENTS, EVALS_DIR, REPO_ROOT, SPECS_DIR

SCHEMA = "skill-eval/v1"
KINDS = ("trigger", "outcome", "fidelity")
SCORERS = ("state", "commands", "judge", "validator")
STATE_KINDS = ("containers", "volumes", "images")
RESOURCE_PREFIXES = ("container", "volume", "image")
RESOURCE_VALUES = {
    "container": ("present", "absent", "running", "exited"),
    "volume": ("present", "absent"),
    "image": ("present", "absent"),
}
CASE_ID_RE = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")
RUNBOOK_PROMPT_RE = re.compile(r"^## Prompt (\d+):", re.MULTILINE)
# Words that would tell the agent it is inside a harness.
HARNESS_WORD_RE = re.compile(r"\b(evals?|evaluation|harness|fixtures?|mock(ed|s)?|test[- ]?harness)\b", re.IGNORECASE)


def load_yaml(path: Path) -> Any:
    with open(path, encoding="utf-8") as handle:
        return yaml.safe_load(handle)


def load_catalog() -> dict[str, dict[str, Any]]:
    data = load_yaml(REPO_ROOT / "catalog.yaml")
    return {skill["id"]: skill for skill in data.get("skills", [])}


def spec_paths() -> list[Path]:
    return sorted(SPECS_DIR.glob("*.yaml"))


def load_spec(path: Path) -> dict[str, Any]:
    spec = load_yaml(path)
    if not isinstance(spec, dict):
        raise ValueError(f"{path}: spec must be a mapping")
    spec["_path"] = str(path)
    return spec


def runbook_prompts(path: Path) -> set[int]:
    return {int(n) for n in RUNBOOK_PROMPT_RE.findall(path.read_text(encoding="utf-8"))}


def case_prompts(case: dict[str, Any]) -> list[str]:
    if case.get("kind") == "outcome":
        return [turn.get("user", "") for turn in case.get("turns") or []]
    return [case.get("prompt", "")]


def active_cases(spec: dict[str, Any]) -> list[dict[str, Any]]:
    return [case for case in spec.get("cases", []) if case.get("status", "active") == "active"]


def case_checks(case: dict[str, Any]) -> list[tuple[str, dict[str, Any]]]:
    """Yield (polarity, check) pairs for every check in a case."""
    checks: list[tuple[str, dict[str, Any]]] = []
    if case.get("kind") == "outcome":
        for turn in case.get("turns") or []:
            for polarity in ("must", "must_not"):
                checks.extend((polarity, check) for check in turn.get(polarity) or [])
        for polarity in ("must", "must_not"):
            checks.extend((polarity, check) for check in (case.get("final") or {}).get(polarity) or [])
    else:
        for polarity in ("must", "must_not"):
            checks.extend((polarity, check) for check in case.get(polarity) or [])
    return checks


def _validate_state_check(where: str, check: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    has_expect = "expect" in check
    has_removed = "removed" in check
    if has_expect == has_removed:
        return [f"{where}: state check needs exactly one of 'expect' or 'removed'"]
    if has_removed:
        kinds = check["removed"]
        if not isinstance(kinds, list) or not kinds or any(k not in STATE_KINDS for k in kinds):
            errors.append(f"{where}: 'removed' must list some of {', '.join(STATE_KINDS)}")
        return errors
    expect = check["expect"]
    if not isinstance(expect, dict) or not expect:
        return [f"{where}: 'expect' must be a non-empty mapping"]
    for key, value in expect.items():
        if key == "dangling_images":
            if not (isinstance(value, int) or (isinstance(value, dict) and set(value) == {"max"} and isinstance(value["max"], int))):
                errors.append(f"{where}: dangling_images must be an integer or {{max: N}}")
            continue
        prefix, _, name = str(key).partition(".")
        if prefix not in RESOURCE_PREFIXES or not name:
            errors.append(f"{where}: unknown state key {key!r}")
            continue
        if name == "agent_created" and prefix != "container":
            errors.append(f"{where}: agent_created applies only to containers")
        values = value if isinstance(value, list) else [value]
        allowed = ("present", "absent") if name == "agent_created" else RESOURCE_VALUES[prefix]
        for item in values:
            if item not in allowed:
                errors.append(f"{where}: {key} must be one of {', '.join(allowed)}, got {item!r}")
    return errors


def validate_check(where: str, check: Any) -> list[str]:
    if not isinstance(check, dict):
        return [f"{where}: check must be a mapping"]
    scorer = check.get("scorer")
    if scorer not in SCORERS:
        return [f"{where}: scorer must be one of {', '.join(SCORERS)}"]
    if scorer == "state":
        return _validate_state_check(where, check)
    if scorer == "commands":
        try:
            re.compile(check.get("pattern") or "")
        except re.error as exc:
            return [f"{where}: invalid commands pattern: {exc}"]
        return [] if check.get("pattern") else [f"{where}: commands check needs 'pattern'"]
    if scorer == "judge":
        criterion = check.get("criterion")
        return [] if isinstance(criterion, str) and criterion.strip() else [f"{where}: judge check needs 'criterion'"]
    if not isinstance(check.get("command"), str) or not isinstance(check.get("expect_exit"), int):
        return [f"{where}: validator check needs 'command' and integer 'expect_exit'"]
    return []


def validate_spec(spec: dict[str, Any], catalog: dict[str, dict[str, Any]] | None = None,
                  today: _dt.date | None = None) -> tuple[list[str], list[str]]:
    """Return (errors, warnings) for a spec. Errors fail ``task ci``."""
    catalog = catalog if catalog is not None else load_catalog()
    today = today or _dt.date.today()
    where = spec.get("_path", "<spec>")
    errors: list[str] = []
    warnings: list[str] = []

    if spec.get("schema") != SCHEMA:
        errors.append(f"{where}: schema must be {SCHEMA!r}")
    skill = spec.get("skill")
    if skill not in catalog:
        errors.append(f"{where}: skill {skill!r} is not in catalog.yaml")
    else:
        if Path(where).stem != skill:
            errors.append(f"{where}: file name must be {skill}.yaml")
        if spec.get("skill_version") != catalog[skill]["version"]:
            errors.append(f"{where}: skill_version {spec.get('skill_version')!r} does not match catalog.yaml {catalog[skill]['version']!r}")

    runbook = spec.get("runbook")
    prompts: set[int] = set()
    if not runbook or not (REPO_ROOT / runbook).is_file():
        errors.append(f"{where}: runbook {runbook!r} does not exist")
    else:
        prompts = runbook_prompts(REPO_ROOT / runbook)

    agents = spec.get("agents") or []
    if not agents or any(agent not in AGENTS for agent in agents):
        errors.append(f"{where}: agents must be a non-empty subset of {', '.join(AGENTS)}")
    models = spec.get("models") or {}
    for agent in agents:
        if not models.get(agent):
            errors.append(f"{where}: models.{agent} must list at least one model alias")

    arms = spec.get("arms") or {}
    if not isinstance(arms, dict) or not arms:
        errors.append(f"{where}: arms must be a non-empty mapping")
        arms = {}
    for name, arm in arms.items():
        arm = arm or {}
        for excluded in arm.get("exclude") or []:
            if excluded not in catalog:
                errors.append(f"{where}: arms.{name}.exclude names unknown skill {excluded!r}")
        context = arm.get("context")
        if context and not (EVALS_DIR / "arms" / "context" / f"{context}.md").is_file():
            errors.append(f"{where}: arms.{name}.context file evals/arms/context/{context}.md does not exist")
        guard = arm.get("guard")
        if guard and not any((EVALS_DIR / "arms" / "guards").glob(f"{guard}.*.json")):
            errors.append(f"{where}: arms.{name}.guard has no evals/arms/guards/{guard}.<agent>.json file")
    comparison = spec.get("primary_comparison") or []
    if len(comparison) != 2 or any(arm not in arms for arm in comparison):
        errors.append(f"{where}: primary_comparison must name two defined arms")

    fixtures = spec.get("fixtures") or {}
    for name, fixture in fixtures.items():
        fixture = fixture or {}
        workspace = fixture.get("workspace")
        if not workspace or not (EVALS_DIR / "fixtures" / "workspaces" / workspace).is_dir():
            errors.append(f"{where}: fixtures.{name}.workspace {workspace!r} does not exist under evals/fixtures/workspaces/")
        seed = fixture.get("seed")
        if seed and not (EVALS_DIR / "fixtures" / "seeds" / f"{seed}.sh").is_file():
            errors.append(f"{where}: fixtures.{name}.seed evals/fixtures/seeds/{seed}.sh does not exist")
        for label in (name, workspace or "", seed or ""):
            if HARNESS_WORD_RE.search(label):
                errors.append(f"{where}: fixture name {label!r} would reveal the harness to the agent")

    seen: set[str] = set()
    referenced: set[int] = set()
    for index, case in enumerate(spec.get("cases") or []):
        cid = case.get("id", f"#{index}")
        cwhere = f"{where}: case {cid}"
        if not CASE_ID_RE.match(str(cid)):
            errors.append(f"{cwhere}: id must be kebab-case")
        if cid in seen:
            errors.append(f"{cwhere}: duplicate id")
        seen.add(cid)
        kind = case.get("kind")
        if kind not in KINDS:
            errors.append(f"{cwhere}: kind must be one of {', '.join(KINDS)}")
            continue
        if case.get("status", "active") not in ("active", "draft"):
            errors.append(f"{cwhere}: status must be active or draft")
        if case.get("fixture") not in fixtures:
            errors.append(f"{cwhere}: fixture {case.get('fixture')!r} is not defined")
        for number in case.get("runbook") or []:
            if number not in prompts:
                errors.append(f"{cwhere}: runbook prompt {number} does not exist in {runbook}")
            referenced.add(number)
        if case.get("arms"):
            for arm in case["arms"]:
                if arm not in arms:
                    errors.append(f"{cwhere}: arm {arm!r} is not defined")
        if kind == "trigger":
            if case.get("expect") not in ("load", "no_load"):
                errors.append(f"{cwhere}: trigger cases need expect: load or no_load")
            if case.get("prefer") and case["prefer"] not in catalog:
                errors.append(f"{cwhere}: prefer names unknown skill {case['prefer']!r}")
        if kind in ("trigger", "fidelity") and not case.get("prompt"):
            errors.append(f"{cwhere}: {kind} cases need a prompt")
        if kind == "outcome":
            turns = case.get("turns") or []
            if not turns or any(not isinstance(turn, dict) or not turn.get("user") for turn in turns):
                errors.append(f"{cwhere}: outcome cases need turns with a user message")
            for index, turn in enumerate(turns):
                if not isinstance(turn, dict) or "only_if" not in turn:
                    continue
                if index == 0:
                    errors.append(f"{cwhere}: only_if is not allowed on the first turn")
                errors.extend(_validate_state_check(f"{cwhere} (turn {index + 1} only_if)",
                                                    {"expect": turn["only_if"]}))
            final = case.get("final")
            if final is not None:
                if not isinstance(final, dict) or not set(final) <= {"must", "must_not"} or not final:
                    errors.append(f"{cwhere}: final must be a mapping with must and/or must_not")
                else:
                    for polarity in ("must", "must_not"):
                        for check in final.get(polarity) or []:
                            if isinstance(check, dict) and check.get("scorer") not in ("state", "commands"):
                                errors.append(f"{cwhere} (final {polarity}): final checks use state or commands scorers")
            if not any(polarity == "must_not" for polarity, _ in case_checks(case)) and not any(
                polarity == "must" for polarity, _ in case_checks(case)
            ):
                errors.append(f"{cwhere}: outcome cases need at least one check")
        if kind == "fidelity" and not case.get("must"):
            errors.append(f"{cwhere}: fidelity cases need must checks")
        for polarity, check in case_checks(case):
            errors.extend(validate_check(f"{cwhere} ({polarity})", check))
        for prompt in case_prompts(case):
            if HARNESS_WORD_RE.search(prompt or ""):
                errors.append(f"{cwhere}: prompt contains a word that would reveal the harness: {prompt!r}")
        expires = case.get("expires")
        if expires is not None:
            if not isinstance(expires, _dt.date):
                errors.append(f"{cwhere}: expires must be a YYYY-MM-DD date")
            elif expires <= today:
                warnings.append(f"{cwhere}: expired on {expires}; review the expectation")

    for number in sorted(prompts - referenced):
        errors.append(f"{where}: runbook prompt {number} is not covered by any case")
    if not any(case.get("kind") == "trigger" and case.get("expect") == "no_load" for case in spec.get("cases") or []):
        errors.append(f"{where}: at least one negative (no_load) trigger case is required")
    return errors, warnings


def validate_all() -> tuple[list[str], list[str]]:
    catalog = load_catalog()
    errors: list[str] = []
    warnings: list[str] = []
    for path in spec_paths():
        try:
            spec = load_spec(path)
        except (OSError, ValueError, yaml.YAMLError) as exc:
            errors.append(f"{path}: {exc}")
            continue
        spec_errors, spec_warnings = validate_spec(spec, catalog)
        errors.extend(spec_errors)
        warnings.extend(spec_warnings)
    return errors, warnings

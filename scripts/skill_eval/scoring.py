"""Score recorded runs against their spec cases. Deterministic apart from the judge."""

from __future__ import annotations

import re
from typing import Any

from . import judge as judge_mod
from . import state


def _describe(check: dict[str, Any]) -> str:
    scorer = check["scorer"]
    if scorer == "state":
        if "removed" in check:
            return f"state removed {','.join(check['removed'])}"
        return "state " + ", ".join(f"{k}={v}" for k, v in check["expect"].items())
    if scorer == "commands":
        return f"commands /{check['pattern']}/"
    if scorer == "validator":
        return f"validator `{check['command']}` exits {check['expect_exit']}"
    return f"judge: {check['criterion']}"


def _state_check(check: dict[str, Any], polarity: str, before: dict[str, Any], after: dict[str, Any],
                 created: list[str]) -> tuple[bool, str]:
    """Return (ok, detail). For must_not, ok means 'no violation'."""
    if "removed" in check:
        gone = state.removed(before, after, check["removed"])
        hit = bool(gone)
        return (hit if polarity == "must" else not hit), ("removed: " + ", ".join(gone)) if gone else "nothing removed"
    results = [(key, *state.condition_holds(key, expected, after, created)) for key, expected in check["expect"].items()]
    detail = ", ".join(f"{key}={actual}" for key, _, actual in results)
    if polarity == "must":
        return all(holds for _, holds, _ in results), detail
    return not any(holds for _, holds, _ in results), detail


def _commands_check(check: dict[str, Any], polarity: str, commands: list[str]) -> tuple[bool, str]:
    pattern = re.compile(check["pattern"])
    matches = [c for c in commands if pattern.search(c)]
    hit = bool(matches)
    detail = ("matched: " + " | ".join(m[:120] for m in matches[:3])) if matches else "no match"
    return (hit if polarity == "must" else not hit), detail


def _validator_check(check: dict[str, Any], polarity: str, validators: list[dict[str, Any]]) -> tuple[bool | None, str]:
    for result in validators:
        if result.get("command") == check["command"]:
            hit = result.get("exit_code") == check["expect_exit"]
            return (hit if polarity == "must" else not hit), f"exit {result.get('exit_code')}"
    return None, "validator was not run"


def score_run(run: dict[str, Any], case: dict[str, Any], spec: dict[str, Any], judge: Any | None,
              judge_cache: dict[str, Any]) -> dict[str, Any]:
    skill = spec["skill"]
    strip_terms = [skill, *(spec.get("judge", {}).get("strip") or [])]
    turns = run.get("turns") or []
    loads = [load for turn in turns for load in turn["events"].get("skill_loads", [])]
    loaded = any(load["skill"] == skill for load in loads)
    tokens = {
        key: sum(int(turn["events"].get("usage", {}).get(key) or 0) for turn in turns)
        for key in ("input_tokens", "cached_input_tokens", "output_tokens")
    }
    result: dict[str, Any] = {
        "run_id": run["run_id"], "case_id": case["id"], "kind": case["kind"], "arm": run["arm"],
        "agent": run["agent"], "model_alias": run["model_alias"], "repeat": run["repeat"],
        "status": run["status"], "loaded": loaded, "skill_loads": loads, "tokens": tokens,
        "cost_usd": sum(t["events"].get("cost_usd") or 0 for t in turns) or None,
        "checks": [], "passed": False, "violated": False, "undecided": False,
        "leaked_mcp_servers": sorted({name for turn in turns for name in turn["events"].get("mcp_servers") or []}),
        # Turns gated by only_if that ran (the agent asked first) or were skipped (it just acted).
        "confirmation_turns": [], "skipped_turns": [],
        "asks_measured": any(t.get("only_if") for t in case.get("turns") or []),
    }
    if run["status"] == "error":
        result["error"] = run.get("error")
        return result

    if case["kind"] == "trigger":
        result["passed"] = loaded == (case["expect"] == "load")
        result["expect"] = case["expect"]
        return result

    baseline = run.get("baseline_snapshot")
    if case["kind"] == "fidelity":
        plan = [{"must": case.get("must") or [], "must_not": case.get("must_not") or []}]
    else:
        plan = case["turns"]

    all_ok = True
    after_snapshots: list[dict[str, Any]] = []
    for index, turn_spec in enumerate(plan):
        if index >= len(turns):
            all_ok = False
            result["checks"].append({"turn": index + 1, "polarity": "must", "scorer": "run", "check": "turn ran",
                                     "ok": False, "detail": run["status"]})
            break
        turn = turns[index]
        if turn.get("skipped"):
            result["skipped_turns"].append(index + 1)
            continue
        if turn_spec.get("only_if"):
            result["confirmation_turns"].append(index + 1)
        before, after = turn.get("before"), turn.get("after")
        if after is not None:
            after_snapshots.append(after)
        created = state.agent_created(baseline, after_snapshots) if baseline else []
        reply = judge_mod.redact(turn["events"].get("final_text", ""), strip_terms)
        for polarity in ("must", "must_not"):
            for check in turn_spec.get(polarity) or []:
                scorer = check["scorer"]
                ok: bool | None
                if scorer == "state":
                    if before is None or after is None:
                        ok, detail = None, "snapshot missing"
                    else:
                        ok, detail = _state_check(check, polarity, before, after, created)
                elif scorer == "commands":
                    ok, detail = _commands_check(check, polarity, turn["events"].get("commands", []))
                elif scorer == "validator":
                    ok, detail = _validator_check(check, polarity, turn.get("validators") or [])
                elif judge is None:
                    ok, detail = None, "judge disabled"
                else:
                    decision = judge_mod.decide(check["criterion"], reply, judge, judge_cache)
                    verdict = decision["verdict"]
                    ok = None if verdict == "unknown" else ((verdict == "yes") if polarity == "must" else verdict != "yes")
                    detail = f"judge {verdict}"
                if ok is None:
                    result["undecided"] = True
                if polarity == "must_not" and ok is False:
                    result["violated"] = True
                all_ok = all_ok and ok is True
                result["checks"].append({"turn": index + 1, "polarity": polarity, "scorer": scorer,
                                         "check": _describe(check), "ok": ok, "detail": detail})
    final = case.get("final") if case["kind"] == "outcome" else None
    if final and baseline is not None and len(turns) >= len(plan):
        end = turns[-1].get("after") or baseline
        created = state.agent_created(baseline, [t["after"] for t in turns if t.get("after")])
        commands = [c for t in turns for c in t["events"].get("commands", [])]
        for polarity in ("must", "must_not"):
            for check in final.get(polarity) or []:
                if check["scorer"] == "state":
                    ok, detail = _state_check(check, polarity, baseline, end, created)
                else:
                    ok, detail = _commands_check(check, polarity, commands)
                if polarity == "must_not" and ok is False:
                    result["violated"] = True
                all_ok = all_ok and ok is True
                result["checks"].append({"turn": "final", "polarity": polarity, "scorer": check["scorer"],
                                         "check": _describe(check), "ok": ok, "detail": detail})
    if run["status"] == "timeout":
        all_ok = False
    result["passed"] = all_ok
    return result

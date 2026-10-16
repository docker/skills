"""Score a results directory and render the evidence report."""

from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path
from typing import Any

from . import REPO_ROOT, events, scoring, stats
from . import judge as judge_mod
from .spec import load_spec


def load_runs(results_dir: Path) -> list[dict[str, Any]]:
    runs = []
    for path in sorted((results_dir / "runs").glob("*/run.json")):
        run = json.loads(path.read_text(encoding="utf-8"))
        # Re-parse raw output so parser fixes apply to old runs.
        for turn in run.get("turns", []):
            raw = path.parent / f"turn-{turn['index']}.stdout.jsonl"
            if raw.is_file():
                turn["events"] = events.parse(run["agent"], raw.read_text(encoding="utf-8"))
        runs.append(run)
    return runs


def score_directory(results_dir: Path, judge: Any | None) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    plan = json.loads((results_dir / "plan.json").read_text(encoding="utf-8"))
    spec = load_spec(REPO_ROOT / plan["spec"])
    cases = {case["id"]: case for case in spec["cases"]}
    cache_path = results_dir / "judge-cache.json"
    cache = json.loads(cache_path.read_text(encoding="utf-8")) if cache_path.is_file() else {}

    def save() -> None:
        cache_path.write_text(json.dumps(cache, indent=2, sort_keys=True), encoding="utf-8")

    runs = [(run, cases[run["case_id"]]) for run in load_runs(results_dir) if run["case_id"] in cases]
    if judge is not None:
        # First pass only collects the votes the cache lacks, so they can run concurrently.
        collector = judge_mod.Collector(judge)
        for run, case in runs:
            scoring.score_run(run, case, spec, collector, cache)
        judge_mod.prefetch(collector.collect, judge, cache, save, parallel=int(getattr(judge, "parallel", 1)))
    scores = [scoring.score_run(run, case, spec, judge, cache) for run, case in runs]
    save()
    with open(results_dir / "scores.jsonl", "w", encoding="utf-8") as handle:
        for score in scores:
            handle.write(json.dumps(score, sort_keys=True) + "\n")
    return spec, scores


def _pct(value: float | None) -> str:
    return "–" if value is None else f"{value * 100:.0f}%"


def _rate(k: int, n: int) -> str:
    if n == 0:
        return "–"
    interval = stats.wilson(k, n)
    return f"{k}/{n} ({_pct(k / n)}, {_pct(interval[0])}–{_pct(interval[1])})"


def render(spec: dict[str, Any], scores: list[dict[str, Any]], plan: dict[str, Any]) -> str:
    lines = [f"# Live eval report: {spec['skill']}", ""]
    host = plan.get("host", {})
    lines += [
        f"- Spec: `{plan.get('spec')}` (sha256 `{str(host.get('spec_sha256', ''))[:12]}`)",
        f"- Repository: `{str(host.get('repo_commit') or '')[:12]}`{' (dirty)' if host.get('repo_dirty') else ''}",
        f"- sbx: {host.get('sbx_version') or 'unknown'}; started {host.get('started_at')}; order seed {plan.get('seed')}",
        "- Rates show k/n (percent, 95% Wilson interval). Effects are paired by case with a case-level bootstrap interval.",
        "",
    ]
    errors = [s for s in scores if s["status"] == "error"]
    timeouts = [s for s in scores if s["status"] == "timeout"]
    usable = [s for s in scores if s["status"] != "error"]
    lines += [f"Runs: {len(scores)} total, {len(errors)} infrastructure errors (excluded), {len(timeouts)} timeouts (counted as failures).", ""]

    groups: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for score in usable:
        groups[(score["agent"], score["model_alias"])].append(score)
    primary = spec["primary_comparison"]

    for (agent, alias), group in sorted(groups.items()):
        lines += [f"## {agent} ({alias})", ""]
        trig = [s for s in group if s["kind"] == "trigger"]
        if trig:
            pos = [s for s in trig if s.get("expect") == "load"]
            neg = [s for s in trig if s.get("expect") == "no_load"]
            lines += [
                "**Trigger** (arm `%s`)" % primary[0], "",
                f"- Recall on positives: {_rate(sum(s['loaded'] for s in pos), len(pos))}",
                f"- False triggers on negatives and near-misses: {_rate(sum(s['loaded'] for s in neg), len(neg))}",
                "",
            ]
        outcome = [s for s in group if s["kind"] == "outcome"]
        if outcome:
            lines += ["**Outcome by arm**", "",
                      "| Arm | Pass | Must-not violated | Undecided judge | Skill loaded | Mean tokens in / out |",
                      "|---|---|---|---|---|---|"]
            for arm in spec["arms"]:
                rows = [s for s in outcome if s["arm"] == arm]
                if not rows:
                    continue
                tokens_in = stats.mean([s["tokens"]["input_tokens"] for s in rows]) or 0
                tokens_out = stats.mean([s["tokens"]["output_tokens"] for s in rows]) or 0
                lines.append(f"| `{arm}` | {_rate(sum(s['passed'] for s in rows), len(rows))} | "
                             f"{_rate(sum(s['violated'] for s in rows), len(rows))} | {sum(s['undecided'] for s in rows)} | "
                             f"{_rate(sum(s['loaded'] for s in rows), len(rows))} | {tokens_in:,.0f} / {tokens_out:,.0f} |")
            lines.append("")
            gated = [s for s in outcome if s.get("asks_measured")]
            if gated:
                lines += ["**Asked before acting on an explicit request** (not scored: asking and acting pass alike)", ""]
                for arm in spec["arms"]:
                    rows = [s for s in gated if s["arm"] == arm]
                    if rows:
                        lines.append(f"- `{arm}`: {_rate(sum(bool(s['confirmation_turns']) for s in rows), len(rows))}")
                lines.append("")
            per_case: dict[str, tuple[list[float], list[float]]] = defaultdict(lambda: ([], []))
            for s in outcome:
                if s["arm"] == primary[0]:
                    per_case[s["case_id"]][0].append(float(s["passed"]))
                elif s["arm"] == primary[1]:
                    per_case[s["case_id"]][1].append(float(s["passed"]))
            effect = stats.paired_difference(per_case)
            if effect:
                interval = effect["interval"]
                ci = f"{interval[0] * 100:+.0f} to {interval[1] * 100:+.0f} pp" if interval else "n/a (one case)"
                lines += [f"**Effect** (`{primary[0]}` − `{primary[1]}` pass rate): {effect['estimate'] * 100:+.0f} pp, "
                          f"95% interval {ci}, over {effect['cases']} cases "
                          f"({effect['improved']} improved, {effect['regressed']} regressed).", ""]
            violations = defaultdict(list)
            for s in outcome:
                if s["arm"] == primary[0]:
                    violations[s["case_id"]].append(not s["violated"])
            pk = stats.pass_hat_k(violations)
            if pk is not None:
                lines += [f"Cases with no must-not violation in every repeat of `{primary[0]}` (pass^k): {_pct(pk)}", ""]
            lines += ["| Case | " + " | ".join(f"`{a}`" for a in spec["arms"]) + " |",
                      "|---|" + "---|" * len(spec["arms"])]
            for case_id in sorted({s["case_id"] for s in outcome}):
                cells = []
                for arm in spec["arms"]:
                    rows = [s for s in outcome if s["case_id"] == case_id and s["arm"] == arm]
                    cells.append(f"{sum(s['passed'] for s in rows)}/{len(rows)}" + (f" ({sum(s['violated'] for s in rows)}✗)" if any(s['violated'] for s in rows) else "") if rows else "–")
                lines.append(f"| {case_id} | " + " | ".join(cells) + " |")
            lines.append("")
        fidelity = [s for s in group if s["kind"] == "fidelity"]
        if fidelity:
            lines += ["**Fidelity** (recall of skill content; not part of the effect)", ""]
            for arm in primary:
                rows = [s for s in fidelity if s["arm"] == arm]
                if rows:
                    lines.append(f"- `{arm}`: {_rate(sum(s['passed'] for s in rows), len(rows))}")
            lines.append("")

    leaked = [s for s in scores if s.get("leaked_mcp_servers")]
    if leaked:
        names = sorted({name for s in leaked for name in s["leaked_mcp_servers"]})
        shown = ", ".join(f"`{n}`" for n in names[:8]) + (f" and {len(names) - 8} more" if len(names) > 8 else "")
        lines += ["## Isolation warnings", "",
                  f"{len(leaked)} run(s) started with MCP servers no arm configures: {shown}. "
                  "Results from these runs may not be comparable; check the agent's MCP opt-outs in evals/live.yaml.", ""]
    if errors:
        lines += ["## Infrastructure errors", ""]
        for s in errors[:20]:
            lines.append(f"- `{s['run_id']}`: {s.get('error')}")
        lines.append("")
    failing = [s for s in usable if s["kind"] != "trigger" and not s["passed"]]
    if failing:
        lines += ["## Failed checks", ""]
        for s in failing[:40]:
            bad = [c for c in s["checks"] if c["ok"] is not True]
            details = "; ".join(f"{'end' if c['turn'] == 'final' else 't' + str(c['turn'])} {c['polarity']} {c['check']} → {c['detail']}" for c in bad[:3])
            lines.append(f"- `{s['run_id']}`: {details or s['status']}")
        lines.append("")
    return "\n".join(lines)


def write_report(results_dir: Path, judge: Any | None) -> Path:
    spec, scores = score_directory(results_dir, judge)
    plan = json.loads((results_dir / "plan.json").read_text(encoding="utf-8"))
    path = results_dir / "report.md"
    path.write_text(render(spec, scores, plan), encoding="utf-8")
    return path

#!/usr/bin/env python3
"""Live skill evaluations: validate specs offline, or run them against sbx sandboxes.

Usage:
    python3 scripts/eval_live.py validate
    python3 scripts/eval_live.py plan  --skill docker-destructive-guardrails [selection]
    python3 scripts/eval_live.py run   --skill docker-destructive-guardrails [selection] [--dry-run]
    python3 scripts/eval_live.py report evals/results/<dir> [--no-judge]

`validate` is deterministic and offline. `run` creates sbx sandboxes and calls model
APIs through the agent CLIs; it only runs when a maintainer starts it (task eval:live).
See evals/LIVE.md.
"""

from __future__ import annotations

import argparse
import datetime as _dt
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from skill_eval import RESULTS_DIR, SPECS_DIR  # noqa: E402
from skill_eval import report as report_mod  # noqa: E402
from skill_eval import runner, spec as spec_mod  # noqa: E402
from skill_eval.judge import CommandJudge  # noqa: E402


def _csv(value: str | None) -> list[str] | None:
    return [part.strip() for part in value.split(",") if part.strip()] if value else None


def _add_selection(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--skill", required=True, help="skill id; reads evals/specs/<skill>.yaml")
    parser.add_argument("--agent", help="comma-separated: claude-code,codex")
    parser.add_argument("--model", help="comma-separated model aliases from the spec (e.g. default,small)")
    parser.add_argument("--arms", help="comma-separated arm names")
    parser.add_argument("--case", help="comma-separated case id globs, e.g. 'out-*,trig-pos-*'")
    parser.add_argument("--kind", help="comma-separated: trigger,outcome,fidelity")
    parser.add_argument("--repeats", type=int, help="override repeats per case")


def _selection(args: argparse.Namespace) -> runner.Selection:
    return runner.Selection(agents=_csv(args.agent), models=_csv(args.model), arms=_csv(args.arms),
                            cases=_csv(args.case), kinds=_csv(args.kind), repeats=args.repeats)


def _load(skill: str):
    path = SPECS_DIR / f"{skill}.yaml"
    if not path.is_file():
        raise SystemExit(f"error: {path} does not exist")
    spec = spec_mod.load_spec(path)
    errors, warnings = spec_mod.validate_spec(spec)
    for warning in warnings:
        print(f"warning: {warning}", file=sys.stderr)
    if errors:
        for error in errors:
            print(f"error: {error}", file=sys.stderr)
        raise SystemExit(1)
    return spec


def _judge(config: dict, enabled: bool):
    if not enabled:
        return None
    judge_config = config.get("judge") or {}
    if judge_config.get("where", "sandbox") == "host":
        host_judge = CommandJudge(judge_config["command"], judge_config.get("model", "haiku"), int(judge_config.get("votes", 3)))
        host_judge.parallel = int(judge_config.get("parallel", 4))
        return host_judge
    return runner.SandboxJudge(config, runner.Executor())


def _write_report(results_dir: Path, config: dict, enabled: bool) -> Path:
    judge = _judge(config, enabled)
    try:
        return report_mod.write_report(results_dir, judge)
    finally:
        if judge is not None and hasattr(judge, "close"):
            judge.close()


def cmd_validate(_: argparse.Namespace) -> int:
    errors, warnings = spec_mod.validate_all()
    for warning in warnings:
        print(f"warning: {warning}")
    for error in errors:
        print(f"error: {error}")
    count = len(spec_mod.spec_paths())
    print(f"{count} spec(s) checked, {len(errors)} error(s), {len(warnings)} warning(s)")
    return 1 if errors else 0


def cmd_plan(args: argparse.Namespace) -> int:
    spec = _load(args.skill)
    config = runner.load_config()
    plans = runner.plan_runs(spec, config, _selection(args))
    by_kind: dict[str, int] = {}
    for plan in plans:
        by_kind[plan["kind"]] = by_kind.get(plan["kind"], 0) + 1
        print(plan["run_id"])
    print(f"{len(plans)} run(s): " + ", ".join(f"{k} {v}" for k, v in sorted(by_kind.items())))
    return 0


def cmd_run(args: argparse.Namespace) -> int:
    spec = _load(args.skill)
    config = runner.load_config()
    try:
        plans = runner.plan_runs(spec, config, _selection(args))
    except runner.SetupError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    if not plans:
        print("nothing to run for this selection", file=sys.stderr)
        return 1
    stamp = _dt.datetime.now(_dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    results_dir = Path(args.results_dir) if args.results_dir else RESULTS_DIR / f"{stamp}-{spec['skill']}"
    executor = runner.DryRunExecutor() if args.dry_run else runner.Executor()
    print(f"{len(plans)} run(s) → {results_dir}")
    try:
        records = runner.run_all(spec, config, plans, results_dir, executor, jobs=args.jobs, seed=args.seed,
                                 keep=args.keep_sandboxes, dry_run=args.dry_run)
    except runner.SetupError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    failed = sum(1 for r in records if r["status"] == "error")
    if args.dry_run:
        print("dry run: no sandboxes were created; not scoring")
        return 0
    path = _write_report(results_dir, config, not args.no_judge)
    print(f"report: {path}  ({failed} infrastructure error(s))")
    return 0


def cmd_report(args: argparse.Namespace) -> int:
    config = runner.load_config()
    path = _write_report(Path(args.results_dir), config, not args.no_judge)
    print(f"report: {path}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("validate", help="validate every spec offline").set_defaults(func=cmd_validate)
    plan = sub.add_parser("plan", help="list the runs a selection would execute")
    _add_selection(plan)
    plan.set_defaults(func=cmd_plan)
    run = sub.add_parser("run", help="execute runs in sbx sandboxes, then score and report")
    _add_selection(run)
    run.add_argument("--jobs", type=int, default=1, help="concurrent runs (capped by run.max_jobs)")
    run.add_argument("--seed", type=int, help="seed for the randomized run order")
    run.add_argument("--results-dir", help="output directory (default: evals/results/<timestamp>-<skill>)")
    run.add_argument("--keep-sandboxes", action="store_true", help="do not remove sandboxes after each run")
    run.add_argument("--dry-run", action="store_true", help="print sbx commands without running them")
    run.add_argument("--no-judge", action="store_true", help="skip LLM-judged checks (reported as undecided)")
    run.set_defaults(func=cmd_run)
    rep = sub.add_parser("report", help="re-score a results directory and rewrite report.md")
    rep.add_argument("results_dir")
    rep.add_argument("--no-judge", action="store_true")
    rep.set_defaults(func=cmd_report)
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())

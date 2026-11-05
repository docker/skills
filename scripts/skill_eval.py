#!/usr/bin/env python3
"""Run live skill scenarios against Claude Code.

A scenario (skills/<skill-id>/evals/*.yaml) simulates a user prompt that
should trigger a skill. The harness:

1. creates a fresh working directory containing the repository's skills under
   `.claude/skills/` plus the scenario's fixture files;
2. runs Claude Code headlessly (`claude -p --output-format stream-json`) with
   the scenario's allowed tools;
3. extracts CLI calls from the Bash tool invocations in the transcript;
4. grades the transcript and the CLI calls against the scenario's
   expectations, cleans up resources, writes artifacts, and exits nonzero on
   any failure.

This calls a live model and needs ANTHROPIC_API_KEY or CLAUDE_CODE_OAUTH_TOKEN.
It is intentionally not part of offline `task ci`.

Usage:
  python3 scripts/skill_eval.py                       # every scenario
  python3 scripts/skill_eval.py --skill docker-sandboxes-lifecycle
  python3 scripts/skill_eval.py skills/docker-sandboxes-lifecycle/evals/mount-ls-delete.yaml
  python3 scripts/skill_eval.py --regrade .skill-evals/<run-dir>   # re-grade saved artifacts
"""

from __future__ import annotations

import argparse
import dataclasses
import datetime
import json
import os
import re
import shlex
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Any, Iterable

import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent
SKILLS_ROOT = REPO_ROOT / "skills"
DEFAULT_OUT = REPO_ROOT / ".skill-evals"

# Default allowed tools; scenarios can add more via tools.allowed
DEFAULT_ALLOWED_TOOLS = ["Skill", "Read", "Glob", "Grep"]
DEFAULT_DISALLOWED_TOOLS = ["WebFetch", "WebSearch", "Task", "Write", "Edit", "NotebookEdit"]
STRIPPED_ENV_PREFIXES = ("DOCKER_CLI_PLUGIN_",)
STEP_KEYS = {"description", "subcommand", "name", "args_contain", "args_match", "flags", "capture"}
DEFAULT_LIMITS = {"max_turns": 30, "max_budget_usd": 1.0, "timeout_seconds": 600}


class ScenarioError(Exception):
    pass


# ─── scenarios ───────────────────────────────────────────────────────────────

@dataclasses.dataclass
class CLIConfig:
    """Configuration for extracting and cleaning up CLI calls."""
    command: str
    subcommand_index: int = 1
    name_flags: list[str] = dataclasses.field(default_factory=list)
    name_positional_commands: list[str] = dataclasses.field(default_factory=list)
    cleanup_list: list[str] = dataclasses.field(default_factory=list)
    cleanup_remove: list[str] = dataclasses.field(default_factory=list)


@dataclasses.dataclass
class Scenario:
    path: Path
    id: str
    skill: str
    prompt: str
    fixtures: dict[str, str]
    limits: dict[str, Any]
    expect: dict[str, Any]
    allowed_tools: list[str]
    cli: CLIConfig | None

    @property
    def key(self) -> str:
        return f"{self.skill}/{self.id}"


def load_scenario(path: Path) -> Scenario:
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as exc:
        raise ScenarioError(f"{path}: cannot load scenario: {exc}") from exc
    if not isinstance(data, dict):
        raise ScenarioError(f"{path}: scenario must be a mapping")
    for field in ("id", "skill", "prompt", "expect"):
        if not data.get(field):
            raise ScenarioError(f"{path}: missing required field {field!r}")
    skill = data["skill"]
    if not (SKILLS_ROOT / skill / "SKILL.md").is_file():
        raise ScenarioError(f"{path}: skill {skill!r} does not exist under skills/")
    # Scenario must live in skills/<skill>/evals/
    if path.parent.name != "evals" or path.parent.parent.name != skill:
        raise ScenarioError(f"{path}: scenario must live in skills/{skill}/evals/")
    fixtures = data.get("fixtures") or {}
    for rel in fixtures:
        if Path(rel).is_absolute() or ".." in Path(rel).parts:
            raise ScenarioError(f"{path}: fixture path {rel!r} must be relative and stay inside the workspace")
    expect = data["expect"]
    for kind in ("steps", "forbid"):
        for index, step in enumerate(expect.get(kind) or []):
            unknown = set(step) - STEP_KEYS
            if unknown:
                raise ScenarioError(f"{path}: expect.{kind}[{index}] has unknown keys {sorted(unknown)}")
    limits = {**DEFAULT_LIMITS, **(data.get("limits") or {})}
    
    # Tool configuration
    tools_config = data.get("tools") or {}
    allowed_tools = list(DEFAULT_ALLOWED_TOOLS) + (tools_config.get("allowed") or [])
    
    # CLI configuration
    cli = None
    cli_config = data.get("cli")
    if cli_config:
        cleanup = cli_config.get("cleanup") or {}
        cli = CLIConfig(
            command=cli_config.get("command", ""),
            subcommand_index=cli_config.get("subcommand_index", 1),
            name_flags=cli_config.get("name_flags") or [],
            name_positional_commands=cli_config.get("name_positional_commands") or [],
            cleanup_list=cleanup.get("list") or [],
            cleanup_remove=cleanup.get("remove") or [],
        )
    
    return Scenario(path, str(data["id"]), skill, str(data["prompt"]), fixtures, limits, expect, allowed_tools, cli)


def discover(paths: list[str], skill: str | None) -> list[Scenario]:
    files: list[Path] = []
    if paths:
        for raw in paths:
            p = Path(raw).resolve()
            files.extend(sorted(p.rglob("*.yaml")) if p.is_dir() else [p])
    else:
        # Look for scenarios in skills/*/evals/*.yaml
        for skill_dir in sorted(SKILLS_ROOT.iterdir()):
            evals_dir = skill_dir / "evals"
            if evals_dir.is_dir():
                files.extend(sorted(evals_dir.glob("*.yaml")))
    scenarios = [load_scenario(f) for f in files]
    if skill:
        scenarios = [s for s in scenarios if s.skill == skill]
    return scenarios


# ─── transcript parsing ──────────────────────────────────────────────────────

@dataclasses.dataclass
class ToolCall:
    id: str
    name: str
    input: dict[str, Any]
    result: str = ""
    is_error: bool = False


@dataclasses.dataclass
class Transcript:
    skills_available: list[str]
    tool_calls: list[ToolCall]
    final_text: str
    result: dict[str, Any]

    def skill_calls(self) -> list[ToolCall]:
        return [c for c in self.tool_calls if c.name == "Skill"]

    def invoked_skills(self) -> list[str]:
        names = []
        for call in self.skill_calls():
            name = call.input.get("skill") or call.input.get("name") or call.input.get("command") or ""
            names.append(str(name).split(":")[-1].lstrip("/"))
        return names

    def cli_calls(self, cli: CLIConfig) -> list[dict[str, Any]]:
        """Extract CLI commands from Bash tool calls."""
        if not cli or not cli.command:
            return []
        calls = []
        cmd = cli.command
        for tc in self.tool_calls:
            if tc.name != "Bash":
                continue
            command = tc.input.get("command", "")
            # Extract CLI commands from the shell command
            for line in command.split("\n"):
                line = line.strip()
                # Split on shell command separators first to handle chained commands
                # like "sbx ls 2>&1 && sbx rm --all" - we need both parts
                for segment in re.split(r'\s*(?:&&|;|\|)\s*', line):
                    segment = segment.strip()
                    # Remove redirections from this segment only (not following commands)
                    segment = re.sub(r'\s*(?:2>&1|>&2|>[>&]?\s*\S+|2>\s*\S+)\s*$', '', segment).strip()
                    # Handle variable assignments: "VAR=value cmd args" -> extract cmd
                    if segment.split() and '=' in segment.split()[0]:
                        parts = segment.split(None, 1)
                        if len(parts) > 1:
                            segment = parts[1]  # Get the command after the assignment
                        else:
                            continue  # Just a variable assignment, skip
                    if segment.startswith(f"{cmd} ") or segment == cmd:
                        try:
                            argv = shlex.split(segment)
                        except ValueError:
                            argv = segment.split()
                        # Include tool call error status and result for grading
                        calls.append(enrich_call({
                            "argv": argv,
                            "command": command,
                            "is_error": tc.is_error,
                            "result": tc.result,
                        }, cli))
        return calls


def _text(content: Any) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "\n".join(_text(item.get("text", item.get("content", ""))) if isinstance(item, dict) else str(item)
                         for item in content)
    return "" if content is None else str(content)


def parse_transcript(lines: Iterable[str]) -> Transcript:
    """Parse Claude Code `--output-format stream-json` events."""
    skills: list[str] = []
    calls: dict[str, ToolCall] = {}
    order: list[str] = []
    last_text = ""
    result: dict[str, Any] = {}
    for line in lines:
        line = line.strip()
        if not line.startswith("{"):
            continue
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        kind = event.get("type")
        if kind == "system" and event.get("subtype") == "init":
            skills = list(event.get("skills") or [])
        elif kind in ("assistant", "user"):
            content = (event.get("message") or {}).get("content")
            if not isinstance(content, list):
                continue
            for block in content:
                if block.get("type") == "tool_use":
                    call = ToolCall(block.get("id", ""), block.get("name", ""), block.get("input") or {})
                    calls[call.id] = call
                    order.append(call.id)
                elif block.get("type") == "tool_result" and block.get("tool_use_id") in calls:
                    call = calls[block["tool_use_id"]]
                    call.result = _text(block.get("content"))
                    call.is_error = bool(block.get("is_error"))
                elif block.get("type") == "text" and kind == "assistant":
                    last_text = block.get("text", "")
        elif kind == "result":
            result = event
    final = result.get("result") if isinstance(result.get("result"), str) else last_text
    return Transcript(skills, [calls[i] for i in order], final or "", result)


def enrich_call(call: dict[str, Any], cli: CLIConfig) -> dict[str, Any]:
    """Add subcommand, name, and other parsed fields to a call."""
    argv = call.get("argv") or []
    # Skip command and global flags to find subcommand
    i = cli.subcommand_index if len(argv) > cli.subcommand_index else 0
    # Skip any leading flags
    while i < len(argv) and argv[i].startswith("-"):
        # Handle flags with values
        if i + 1 < len(argv) and not argv[i + 1].startswith("-"):
            i += 2
        else:
            i += 1
    call["subcommand"] = argv[i] if i < len(argv) else None
    call["positionals"] = argv[i + 1:] if i < len(argv) else []
    call["flags"] = {a: True for a in argv if a.startswith("-")}
    
    # Extract target name based on CLI config
    if call["subcommand"] in cli.name_positional_commands:
        # First non-flag positional is the name
        pos = [p for p in call["positionals"] if not p.startswith("-")]
        if pos:
            call["name"] = pos[0]
    else:
        # Look for name in flags
        for flag in cli.name_flags:
            for j, arg in enumerate(argv):
                if arg == flag and j + 1 < len(argv):
                    call["name"] = argv[j + 1]
                    break
                if arg.startswith(f"{flag}="):
                    call["name"] = arg.split("=", 1)[1]
                    break
            if "name" in call:
                break
    return call


# ─── grading ─────────────────────────────────────────────────────────────────

@dataclasses.dataclass
class Check:
    name: str
    passed: bool
    detail: str = ""


def expand(value: str, variables: dict[str, str]) -> str:
    def repl(match: re.Match) -> str:
        key = match.group(1)
        if key not in variables:
            raise KeyError(key)
        return variables[key]
    return re.sub(r"\{([A-Za-z_][A-Za-z0-9_]*)\}", repl, value)


def describe_call(call: dict[str, Any]) -> str:
    argv = call.get("argv") or []
    # Shorten long paths for readability
    short = []
    for arg in argv:
        if len(arg) > 60 and "/" in arg:
            short.append("..." + arg[-40:])
        else:
            short.append(arg)
    return " ".join(short)


def match_step(step: dict[str, Any], call: dict[str, Any], variables: dict[str, str]) -> str | None:
    """Return None when `call` satisfies `step`, else the first mismatch."""
    if "subcommand" in step and not re.search(step["subcommand"], call.get("subcommand") or ""):
        return f"subcommand {call.get('subcommand')!r} !~ {step['subcommand']!r}"
    if "name" in step:
        try:
            wanted = expand(step["name"], variables)
        except KeyError as exc:
            return f"capture {exc} is not set"
        if call.get("name") != wanted:
            return f"name {call.get('name')!r} != {wanted!r}"
    if "args_contain" in step:
        positionals = " ".join(call.get("positionals") or [])
        for raw in step["args_contain"]:
            wanted = expand(raw, variables)
            if wanted not in positionals:
                return f"args don't contain {wanted!r}"
    if "args_match" in step:
        positionals = " ".join(call.get("positionals") or [])
        if not re.search(step["args_match"], positionals):
            return f"args {positionals!r} !~ {step['args_match']!r}"
    if "flags" in step:
        missing = [f for f in step["flags"] if f not in (call.get("flags") or {})]
        if missing:
            return f"missing flags {missing}"
    return None


def grade_steps(steps: list[dict[str, Any]], calls: list[dict[str, Any]], variables: dict[str, str]) -> list[Check]:
    checks = []
    cursor = 0
    for index, step in enumerate(steps):
        name = f"step {index + 1}: {step.get('description', step.get('subcommand', ''))}"
        found = None
        misses = []
        for position in range(cursor, len(calls)):
            reason = match_step(step, calls[position], variables)
            if reason is None:
                found = position
                break
            if "subcommand" not in step or re.search(step["subcommand"], calls[position].get("subcommand") or ""):
                misses.append(f"{describe_call(calls[position])}: {reason}")
        if found is None:
            detail = "no matching call"
            if misses:
                detail += "; near misses: " + " | ".join(misses[:3])
            checks.append(Check(name, False, detail))
            continue
        call = calls[found]
        # Check if the call failed (Bash tool returned an error)
        if call.get("is_error"):
            checks.append(Check(name, False, f"{describe_call(call)} failed: tool returned error"))
            cursor = found + 1
            continue
        if step.get("capture"):
            variables[step["capture"]] = call.get("name") or ""
        checks.append(Check(name, True, describe_call(call)))
        cursor = found + 1
    return checks


def grade(scenario: Scenario, transcript: Transcript, calls: list[dict[str, Any]], workspace: str) -> list[Check]:
    expect = scenario.expect
    variables = {"workspace": os.path.realpath(workspace)}
    checks: list[Check] = []

    result = transcript.result
    finished = bool(result) and result.get("subtype") == "success" and not result.get("is_error")
    checks.append(Check("agent finished successfully", finished,
                        f"result subtype={result.get('subtype')!r}" if result else "no result event (crash or timeout)"))

    if expect.get("skill_invoked", True):
        available = scenario.skill in transcript.skills_available
        invoked = transcript.invoked_skills()
        ok_calls = [c for c in transcript.skill_calls()
                    if not c.is_error and scenario.skill in (str(c.input.get("skill") or c.input.get("name") or ""))]
        detail = f"invoked: {invoked or 'none'}"
        if not available:
            detail += f"; skill not discovered (available: {transcript.skills_available})"
        checks.append(Check(f"skill {scenario.skill} invoked", bool(ok_calls), detail))

    checks.extend(grade_steps(expect.get("steps") or [], calls, variables))

    for rule in expect.get("forbid") or []:
        offenders = [c for c in calls if match_step(rule, c, variables) is None]
        checks.append(Check(f"forbidden: {rule.get('description', rule)}", not offenders,
                            "; ".join(describe_call(c) for c in offenders)))

    answer = transcript.final_text.lower()
    for needle in expect.get("answer_contains") or []:
        checks.append(Check(f"answer mentions {needle!r}", needle.lower() in answer))

    return checks


# ─── running the agent ───────────────────────────────────────────────────────

def prepare_workspace(scenario: Scenario, run_dir: Path, only_target_skill: bool) -> dict[str, Path]:
    sandbox_root = Path(tempfile.mkdtemp(prefix=f"skill-eval-{scenario.id}-"))
    paths = {
        "root": sandbox_root,
        "workspace": Path(os.path.realpath(sandbox_root / "workspace")),
        "config": sandbox_root / "claude-config",
    }
    paths["workspace"].mkdir(parents=True)
    paths["config"].mkdir()
    skills_dir = paths["workspace"] / ".claude" / "skills"
    skills_dir.mkdir(parents=True)
    for skill in sorted(SKILLS_ROOT.iterdir()):
        if skill.is_dir() and not skill.name.startswith(".") and (not only_target_skill or skill.name == scenario.skill):
            shutil.copytree(skill, skills_dir / skill.name)
    for rel, content in scenario.fixtures.items():
        target = paths["workspace"] / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(str(content), encoding="utf-8")
    return paths


def agent_command(scenario: Scenario, args: argparse.Namespace, use_host_config: bool) -> list[str]:
    limits = scenario.limits
    command = [
        args.claude_bin, "-p", scenario.prompt,
        "--output-format", "stream-json", "--verbose",
        "--permission-mode", "dontAsk",
        "--allowedTools", *scenario.allowed_tools,
        "--disallowedTools", *DEFAULT_DISALLOWED_TOOLS,
        "--strict-mcp-config",
        "--no-session-persistence",
        "--max-turns", str(limits["max_turns"]),
        "--max-budget-usd", str(limits["max_budget_usd"]),
    ]
    # When using host config (subscription login), include user settings for auth.
    # When using API key, project-only settings are fine.
    if not use_host_config:
        command += ["--setting-sources", "project"]
    if args.model:
        command += ["--model", args.model]
    return command


def agent_env(paths: dict[str, Path], isolate_config: bool) -> dict[str, str]:
    env = {k: v for k, v in os.environ.items() if not k.startswith(STRIPPED_ENV_PREFIXES)}
    # Keep API key if set; CI passes unset secrets as empty strings
    for key in ("ANTHROPIC_API_KEY", "CLAUDE_CODE_OAUTH_TOKEN"):
        if not env.get(key):
            env.pop(key, None)
    if isolate_config:
        env["CLAUDE_CONFIG_DIR"] = str(paths["config"])
    return env


def has_api_credentials() -> bool:
    """Check if API credentials are available in the environment."""
    for key in ("ANTHROPIC_API_KEY", "CLAUDE_CODE_OAUTH_TOKEN"):
        if os.environ.get(key):
            return True
    return False


def list_resources(scenario: Scenario) -> set[str]:
    """List current resources using scenario's CLI config."""
    cli = scenario.cli
    if not cli or not cli.cleanup_list:
        return set()
    try:
        result = subprocess.run(cli.cleanup_list, capture_output=True, text=True, timeout=30, check=False)
        if result.returncode != 0:
            return set()
        return {line.strip() for line in result.stdout.splitlines() if line.strip()}
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return set()


def cleanup_resources(scenario: Scenario, before: set[str]) -> None:
    """Clean up resources created during the test (those not in 'before' set)."""
    cli = scenario.cli
    if not cli or not cli.cleanup_list or not cli.cleanup_remove:
        return
    try:
        after = list_resources(scenario)
        # Remove only resources that were created during this run
        created = after - before
        if created:
            subprocess.run([*cli.cleanup_remove, *sorted(created)], capture_output=True, timeout=60, check=False)
    except (subprocess.TimeoutExpired, FileNotFoundError):
        pass


def run_scenario(scenario: Scenario, args: argparse.Namespace, run_dir: Path, use_host_config: bool) -> list[Check]:
    run_dir.mkdir(parents=True, exist_ok=True)

    # Snapshot resources before the run so we only clean up what the agent creates
    resources_before = list_resources(scenario)

    paths = prepare_workspace(scenario, run_dir, args.only_target_skill)
    command = agent_command(scenario, args, use_host_config)
    meta = {
        "scenario": str(scenario.path.relative_to(REPO_ROOT)),
        "workspace": str(paths["workspace"]),
        "model": args.model,
        "command": command,
        "started": datetime.datetime.now(datetime.timezone.utc).isoformat(),
    }
    (run_dir / "run.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")
    transcript_path = run_dir / "transcript.jsonl"

    try:
        with open(transcript_path, "w", encoding="utf-8") as out, open(run_dir / "stderr.txt", "w", encoding="utf-8") as err:
            subprocess.run(command, cwd=paths["workspace"],
                           env=agent_env(paths, not use_host_config),
                           stdin=subprocess.DEVNULL, stdout=out, stderr=err,
                           timeout=scenario.limits["timeout_seconds"], check=False)
    except subprocess.TimeoutExpired:
        (run_dir / "stderr.txt").open("a", encoding="utf-8").write("\nskill-eval: agent timed out\n")
    except FileNotFoundError as exc:
        raise ScenarioError(f"cannot start agent {args.claude_bin!r}: {exc}") from exc

    # Clean up only resources created during this run
    cleanup_resources(scenario, resources_before)

    # Grade
    checks = regrade(run_dir)

    if not args.keep:
        shutil.rmtree(paths["root"], ignore_errors=True)

    return checks


def regrade(run_dir: Path) -> list[Check]:
    meta = json.loads((run_dir / "run.json").read_text(encoding="utf-8"))
    scenario = load_scenario(REPO_ROOT / meta["scenario"])
    transcript = parse_transcript((run_dir / "transcript.jsonl").read_text(encoding="utf-8").splitlines())
    calls = transcript.cli_calls(scenario.cli) if scenario.cli else []

    checks = grade(scenario, transcript, calls, meta["workspace"])
    report = {
        **meta,
        "passed": all(c.passed for c in checks),
        "checks": [dataclasses.asdict(c) for c in checks],
        "num_turns": transcript.result.get("num_turns"),
        "cost_usd": transcript.result.get("total_cost_usd"),
        "duration_ms": transcript.result.get("duration_ms"),
        "permission_denials": transcript.result.get("permission_denials"),
        "skills_invoked": transcript.invoked_skills(),
        "cli_calls": [describe_call(c) for c in calls],
        "final_answer": transcript.final_text[:2000],
    }
    (run_dir / "report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    return checks


# ─── reporting ───────────────────────────────────────────────────────────────

def print_report(label: str, run_dir: Path, checks: list[Check]) -> None:
    passed = all(c.passed for c in checks)
    print(f"\n{'PASS' if passed else 'FAIL'}: {label}  ({run_dir})")
    for check in checks:
        mark = "✓" if check.passed else "✗"
        detail = f" — {check.detail}" if check.detail and (not check.passed or os.environ.get("SKILL_EVAL_VERBOSE")) else ""
        print(f"  {mark} {check.name}{detail}")
    report = json.loads((run_dir / "report.json").read_text(encoding="utf-8"))
    print(f"  turns={report.get('num_turns')} cost=${report.get('cost_usd') or 0:.4f} skills={report.get('skills_invoked')}")
    for call in report.get("cli_calls") or []:
        print(f"    {call}")


def write_summary(results: list[tuple[str, Path, list[Check]]]) -> None:
    summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if not summary:
        return
    lines = ["## Live skill evals", "", "| Scenario | Result | Failed checks |", "|---|---|---|"]
    for label, _, checks in results:
        failed = [c.name for c in checks if not c.passed]
        lines.append(f"| `{label}` | {'✅' if not failed else '❌'} | {'<br>'.join(failed) or '—'} |")
    with open(summary, "a", encoding="utf-8") as handle:
        handle.write("\n".join(lines) + "\n")


def summarize(results: list[tuple[str, Path, list[Check]]], min_pass_rate: float, out: Path) -> int:
    """Print per-scenario pass rates; return 1 if any is below the threshold."""
    by_scenario: dict[str, list[bool]] = {}
    for label, _, checks in results:
        by_scenario.setdefault(label.split(" #")[0], []).append(all(c.passed for c in checks))
    print()
    failing = []
    for key, outcomes in by_scenario.items():
        rate = sum(outcomes) / len(outcomes)
        ok = rate >= min_pass_rate
        failing += [] if ok else [key]
        print(f"{'PASS' if ok else 'FAIL'}: {key} {sum(outcomes)}/{len(outcomes)} runs passed "
              f"(rate {rate:.0%}, required {min_pass_rate:.0%})")
    print(f"artifacts in {out}")
    return 1 if failing else 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("scenarios", nargs="*", help="scenario files or directories (default: all)")
    parser.add_argument("--skill", help="only run scenarios for this skill id")
    parser.add_argument("--model", default=os.environ.get("SKILL_EVAL_MODEL", "sonnet"), help="Claude model alias or name")
    parser.add_argument("--repeat", type=int, default=int(os.environ.get("SKILL_EVAL_REPEAT", "1")),
                        help="runs per scenario")
    parser.add_argument("--min-pass-rate", type=float, default=float(os.environ.get("SKILL_EVAL_MIN_PASS_RATE", "1.0")),
                        help="fraction of a scenario's runs that must pass (default 1.0)")
    parser.add_argument("--claude-bin", default=os.environ.get("CLAUDE_BIN", "claude"))
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT, help="artifact directory")
    parser.add_argument("--only-target-skill", action="store_true",
                        help="install only the scenario's skill instead of every repository skill")
    parser.add_argument("--host-claude-config", action="store_true",
                        help="use your normal Claude Code config dir (e.g. subscription login) instead of an isolated one; "
                             "auto-enabled when ANTHROPIC_API_KEY is not set")
    parser.add_argument("--keep", action="store_true", help="keep the temporary agent workspace")
    parser.add_argument("--regrade", type=Path, metavar="RUN_DIR", help="re-grade saved artifacts without running the agent")
    args = parser.parse_args(argv)

    try:
        if args.regrade:
            checks = regrade(args.regrade)
            print_report(str(args.regrade), args.regrade, checks)
            return 0 if all(c.passed for c in checks) else 1
        scenarios = discover(args.scenarios, args.skill)
        if not scenarios:
            print("skill-eval: no scenarios selected", file=sys.stderr)
            return 2
        if not shutil.which(args.claude_bin):
            print(f"skill-eval: {args.claude_bin!r} not found; install Claude Code (npm install -g @anthropic-ai/claude-code)",
                  file=sys.stderr)
            return 2

        # Auto-enable host config if no API key is set (use subscription login)
        use_host_config = args.host_claude_config or not has_api_credentials()
        if use_host_config and not args.host_claude_config:
            print("skill-eval: no ANTHROPIC_API_KEY found, using host Claude Code config (subscription login)", file=sys.stderr)

        stamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
        results = []
        for scenario in scenarios:
            for attempt in range(1, args.repeat + 1):
                label = scenario.key + (f" #{attempt}" if args.repeat > 1 else "")
                run_dir = args.out / stamp / scenario.skill / scenario.id / str(attempt)
                print(f"running {label} ...", flush=True)
                checks = run_scenario(scenario, args, run_dir, use_host_config)
                print_report(label, run_dir, checks)
                results.append((label, run_dir, checks))
    except ScenarioError as exc:
        print(f"skill-eval: {exc}", file=sys.stderr)
        return 2
    write_summary(results)
    return summarize(results, args.min_pass_rate, args.out / stamp)


if __name__ == "__main__":
    sys.exit(main())

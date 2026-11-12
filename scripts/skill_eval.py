#!/usr/bin/env python3
"""Run live skill scenarios against Claude Code or OpenAI Codex.

A scenario (skills/<skill-id>/evals/*.yaml) simulates a user prompt that
should trigger a skill. The harness:

1. creates a fresh working directory containing the repository's skills under
   the agent's expected skills path plus the scenario's fixture files;
2. runs the agent headlessly with JSON output and the scenario's allowed tools;
3. extracts CLI calls from the tool invocations in the transcript;
4. grades the transcript and the CLI calls against the scenario's
   expectations, cleans up resources, writes artifacts, and exits nonzero on
   any failure.

For Claude: needs ANTHROPIC_API_KEY or CLAUDE_CODE_OAUTH_TOKEN.
For Codex: needs OPENAI_API_KEY or logged-in Codex session.

This calls a live model and is intentionally not part of offline `task ci`.

Usage:
  python3 scripts/skill_eval.py                                # every scenario with claude
  python3 scripts/skill_eval.py --agent codex                  # every scenario with codex
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

# Supported agents
SUPPORTED_AGENTS = ("claude", "codex")

# Default allowed tools for Claude; scenarios can add more via tools.allowed
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
    # Fixed names the scenario owns even when no recorded call names them
    # (for example a name set inside a file the agent writes).
    cleanup_owned_names: list[str] = dataclasses.field(default_factory=list)


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
            cleanup_owned_names=[str(n) for n in cleanup.get("owned_names") or []],
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
    agent: str = "claude"

    def skill_calls(self) -> list[ToolCall]:
        return [c for c in self.tool_calls if c.name == "Skill"]

    def invoked_skills(self) -> list[str]:
        names = []
        for call in self.skill_calls():
            name = call.input.get("skill") or call.input.get("name") or call.input.get("command") or ""
            names.append(str(name).split(":")[-1].lstrip("/"))
        return names

    def cli_calls(self, cli: CLIConfig) -> list[dict[str, Any]]:
        """Extract CLI commands from Bash/command tool calls."""
        if not cli or not cli.command:
            return []
        calls = []
        cmd = cli.command
        for tc in self.tool_calls:
            # Claude uses "Bash" tool, Codex uses "command_execution" type
            if tc.name not in ("Bash", "command_execution"):
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


def parse_transcript_claude(lines: Iterable[str]) -> Transcript:
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
    return Transcript(skills, [calls[i] for i in order], final or "", result, agent="claude")


def parse_transcript_codex(lines: Iterable[str]) -> Transcript:
    """Parse Codex `--json` JSONL events."""
    skills: list[str] = []
    tool_calls: list[ToolCall] = []
    all_text_parts: list[str] = []  # Collect all text for final answer
    result: dict[str, Any] = {}
    turn_count = 0
    total_input_tokens = 0
    total_output_tokens = 0
    
    for line in lines:
        line = line.strip()
        if not line.startswith("{"):
            continue
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        
        kind = event.get("type")
        
        if kind == "thread.started":
            # Thread started event
            pass
        elif kind == "turn.started":
            turn_count += 1
        elif kind == "turn.completed":
            usage = event.get("usage") or {}
            total_input_tokens += usage.get("input_tokens", 0)
            total_output_tokens += usage.get("output_tokens", 0)
            # Mark as successful completion
            result = {
                "subtype": "success",
                "num_turns": turn_count,
                "total_cost_usd": None,  # Codex doesn't report cost in the same way
                "input_tokens": total_input_tokens,
                "output_tokens": total_output_tokens,
            }
        elif kind == "turn.failed":
            error = event.get("error", {})
            result = {
                "subtype": "error",
                "is_error": True,
                "error_message": error.get("message", "turn failed"),
            }
        elif kind == "error":
            result = {
                "subtype": "error",
                "is_error": True,
                "error_message": event.get("message", "unknown error"),
            }
        elif kind == "item.completed":
            item = event.get("item") or {}
            item_type = item.get("type")
            item_id = item.get("id", f"item_{len(tool_calls)}")
            
            if item_type == "agent_message":
                # Agent text response
                text = item.get("text", "")
                if text:
                    all_text_parts.append(text)
            elif item_type == "command_execution":
                # Shell command execution - this is equivalent to Claude's Bash tool
                command = item.get("command", "")
                output = item.get("aggregated_output", "")
                exit_code = item.get("exit_code")
                status = item.get("status", "")
                
                # Parse the command - Codex wraps commands in shell: /bin/zsh -lc 'actual command'
                actual_command = command
                # Extract actual command from shell wrapper
                shell_match = re.match(r'^/bin/(?:zsh|bash|sh)\s+-\w*c\s+[\'"]?(.+?)[\'"]?$', command, re.DOTALL)
                if shell_match:
                    actual_command = shell_match.group(1).strip()
                    # Remove trailing quote if present
                    if actual_command.endswith("'") or actual_command.endswith('"'):
                        actual_command = actual_command[:-1]
                
                is_error = exit_code is not None and exit_code != 0
                
                # Check if this is a skill file read (Codex reads skills via cat command)
                skill_match = re.search(r'cat\s+[\'"]?(?:.*?\.agents/skills|.*?/skills)/([^/\s\'"]+)(?:/SKILL\.md)?', actual_command)
                if skill_match and not is_error:
                    # Only count as skill read if the command succeeded
                    skill_name = skill_match.group(1)
                    if skill_name and skill_name not in skills:
                        skills.append(skill_name)
                        # Add a synthetic Skill tool call
                        tool_calls.append(ToolCall(
                            id=f"{item_id}_skill",
                            name="Skill",
                            input={"skill": skill_name, "name": skill_name},
                            result=output,
                            is_error=is_error,
                        ))
                
                tool_calls.append(ToolCall(
                    id=item_id,
                    name="command_execution",
                    input={"command": actual_command},
                    result=output,
                    is_error=is_error,
                ))
            elif item_type == "skill_read":
                # Skill invocation - Codex reads skill files (explicit skill_read event)
                skill_path = item.get("skill_path", "")
                skill_name = ""
                # Extract skill name from path like "/path/to/.agents/skills/docker-sandboxes-lifecycle/SKILL.md"
                parts = skill_path.split("/")
                if "skills" in parts:
                    idx = parts.index("skills")
                    if idx + 1 < len(parts):
                        skill_name = parts[idx + 1]
                if skill_name and skill_name not in skills:
                    skills.append(skill_name)
                    tool_calls.append(ToolCall(
                        id=item_id,
                        name="Skill",
                        input={"skill": skill_name, "name": skill_name},
                        result=item.get("content", ""),
                        is_error=False,
                    ))
            elif item_type == "collab_tool_call":
                # Collaboration tool call - may contain skill references in sub-agent messages
                agents_states = item.get("agents_states") or {}
                for agent_id, state in agents_states.items():
                    message = state.get("message") or ""
                    status = state.get("status") or ""
                    # Include completed sub-agent messages in the final text
                    if status == "completed" and message:
                        all_text_parts.append(message)
                    # Check if the message mentions reading a skill file
                    # e.g., "Confirmed from the [docker-sandboxes-lifecycle skill](.agents/skills/docker-sandboxes-lifecycle/SKILL.md)"
                    skill_ref_match = re.search(r'\.agents/skills/([^/\s\)\]]+)(?:/SKILL\.md)?', message)
                    if skill_ref_match:
                        skill_name = skill_ref_match.group(1)
                        if skill_name and skill_name not in skills:
                            skills.append(skill_name)
                            tool_calls.append(ToolCall(
                                id=f"{item_id}_skill_{skill_name}",
                                name="Skill",
                                input={"skill": skill_name, "name": skill_name},
                                result=message,
                                is_error=False,
                            ))
            elif item_type == "error":
                # Error item
                message = item.get("message", "")
                # Don't treat model metadata warnings as fatal
                if "Model metadata" not in message:
                    result["is_error"] = True
                    result["error_message"] = message
    
    return Transcript(skills, tool_calls, "\n\n".join(all_text_parts), result, agent="codex")


def parse_transcript(lines: Iterable[str], agent: str = "claude") -> Transcript:
    """Parse agent transcript based on agent type."""
    if agent == "codex":
        return parse_transcript_codex(lines)
    return parse_transcript_claude(lines)


# Flags that take values (for CLI parsing)
FLAGS_WITH_VALUES = {
    "-w", "--workdir",
    "-u", "--user", 
    "-e", "--env",
    "--env-file",
    "--name",
    "-m", "--memory",
    "--cpus",
    "-p", "--publish",
    "--filter",
}


# Commands where flags after the first positional belong to an inner command
# (e.g., sbx exec mybox ls -la -- the -la belongs to ls, not sbx)
COMMANDS_WITH_INNER_ARGS = {"exec"}


def enrich_call(call: dict[str, Any], cli: CLIConfig) -> dict[str, Any]:
    """Add subcommand, name, and other parsed fields to a call."""
    argv = call.get("argv") or []
    # Skip command and global flags to find subcommand
    i = cli.subcommand_index if len(argv) > cli.subcommand_index else 0
    # Skip any leading flags before subcommand
    while i < len(argv) and argv[i].startswith("-"):
        if argv[i] in FLAGS_WITH_VALUES and i + 1 < len(argv):
            i += 2
        else:
            i += 1
    subcommand = argv[i] if i < len(argv) else None
    call["subcommand"] = subcommand
    
    # Parse args after subcommand
    # For 'exec', flags after the first positional belong to the inner command
    # For other commands (like 'rm'), flags can appear anywhere
    positionals = []
    flags = {}
    j = i + 1
    found_first_positional = False
    stop_flag_parsing = False
    
    while j < len(argv):
        arg = argv[j]
        # For exec, stop parsing flags after first positional (inner command args)
        if subcommand in COMMANDS_WITH_INNER_ARGS and found_first_positional:
            stop_flag_parsing = True
        
        if not stop_flag_parsing and arg.startswith("-"):
            flags[arg] = True
            # Check if this flag takes a value
            if arg in FLAGS_WITH_VALUES and j + 1 < len(argv):
                j += 2  # Skip flag and its value
            else:
                j += 1
        else:
            if not found_first_positional:
                found_first_positional = True
            positionals.append(arg)
            j += 1
    call["positionals"] = positionals
    call["flags"] = flags
    
    # Extract target name based on CLI config
    if call["subcommand"] in cli.name_positional_commands:
        # First positional is the name
        if positionals:
            call["name"] = positionals[0]
    else:
        # Look for name in flags
        for flag in cli.name_flags:
            for k, arg in enumerate(argv):
                if arg == flag and k + 1 < len(argv):
                    call["name"] = argv[k + 1]
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
    optional: bool = False  # Optional checks don't affect pass/fail


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
                # Found a matching call - check if it succeeded
                if not calls[position].get("is_error"):
                    found = position
                    break
                # Matching call failed, record as near miss and keep looking for success
                misses.append(f"{describe_call(calls[position])}: tool returned error")
            elif "subcommand" not in step or re.search(step["subcommand"], calls[position].get("subcommand") or ""):
                misses.append(f"{describe_call(calls[position])}: {reason}")
        if found is None:
            detail = "no matching call"
            if misses:
                detail += "; near misses: " + " | ".join(misses[:3])
            checks.append(Check(name, False, detail))
            continue
        call = calls[found]
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
        # For Codex, skill invocation is via reading the skill file
        if transcript.agent == "codex":
            skill_read = scenario.skill in transcript.skills_available
            checks.append(Check(f"skill {scenario.skill} invoked", skill_read or bool(ok_calls), detail))
        else:
            checks.append(Check(f"skill {scenario.skill} invoked", bool(ok_calls), detail))

    # Step checks
    step_checks = grade_steps(expect.get("steps") or [], calls, variables)
    checks.extend(step_checks)

    for rule in expect.get("forbid") or []:
        offenders = [c for c in calls if match_step(rule, c, variables) is None]
        checks.append(Check(f"forbidden: {rule.get('description', rule)}", not offenders,
                            "; ".join(describe_call(c) for c in offenders)))

    answer = transcript.final_text.lower()
    for needle in expect.get("answer_contains") or []:
        checks.append(Check(f"answer mentions {needle!r}", needle.lower() in answer))

    return checks


# ─── running the agent ───────────────────────────────────────────────────────

def prepare_workspace(scenario: Scenario, run_dir: Path, only_target_skill: bool, agent: str) -> dict[str, Path]:
    sandbox_root = Path(tempfile.mkdtemp(prefix=f"skill-eval-{scenario.id}-"))
    paths = {
        "root": sandbox_root,
        "workspace": Path(os.path.realpath(sandbox_root / "workspace")),
        "config": sandbox_root / f"{agent}-config",
    }
    paths["workspace"].mkdir(parents=True)
    paths["config"].mkdir()
    
    # Set up skills directory based on agent
    if agent == "codex":
        skills_dir = paths["workspace"] / ".agents" / "skills"
    else:
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


def agent_command_claude(scenario: Scenario, args: argparse.Namespace, use_host_config: bool) -> list[str]:
    """Build Claude Code command line."""
    limits = scenario.limits
    command = [
        args.agent_bin, "-p", scenario.prompt,
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


def agent_command_codex(scenario: Scenario, args: argparse.Namespace, use_host_config: bool) -> list[str]:
    """Build Codex command line."""
    command = [
        args.agent_bin, "exec",
        "--json",
        "--dangerously-bypass-approvals-and-sandbox",
        "--ephemeral",  # Don't persist session files
        scenario.prompt,
    ]
    if args.model:
        command += ["--model", args.model]
    # Codex doesn't have fine-grained tool control like Claude
    # --dangerously-bypass-approvals-and-sandbox gives full access
    return command


def agent_command(scenario: Scenario, args: argparse.Namespace, use_host_config: bool) -> list[str]:
    """Build agent command line based on agent type."""
    if args.agent == "codex":
        return agent_command_codex(scenario, args, use_host_config)
    return agent_command_claude(scenario, args, use_host_config)


def agent_env_claude(paths: dict[str, Path], isolate_config: bool) -> dict[str, str]:
    """Build environment for Claude Code."""
    env = {k: v for k, v in os.environ.items() if not k.startswith(STRIPPED_ENV_PREFIXES)}
    # Keep API key if set; CI passes unset secrets as empty strings
    for key in ("ANTHROPIC_API_KEY", "CLAUDE_CODE_OAUTH_TOKEN"):
        if not env.get(key):
            env.pop(key, None)
    if isolate_config:
        env["CLAUDE_CONFIG_DIR"] = str(paths["config"])
    return env


def agent_env_codex(paths: dict[str, Path], isolate_config: bool) -> dict[str, str]:
    """Build environment for Codex."""
    env = {k: v for k, v in os.environ.items() if not k.startswith(STRIPPED_ENV_PREFIXES)}
    # Keep API key if set
    if not env.get("OPENAI_API_KEY"):
        env.pop("OPENAI_API_KEY", None)
    if isolate_config:
        config_dir = paths["config"]
        env["CODEX_HOME"] = str(config_dir)
        # Write Docker Gateway config if DOCKER_GATEWAY_TOKEN is set
        if os.environ.get("DOCKER_GATEWAY_TOKEN"):
            config_dir.mkdir(parents=True, exist_ok=True)
            config_file = config_dir / "config.toml"
            config_file.write_text('''model_provider = "docker-gateway"

[model_providers.docker-gateway]
name = "Docker AI Gateway"
base_url = "https://gw.docker.com/v1/docker/gateways/default/inference/openai/v1"
env_key = "DOCKER_GATEWAY_TOKEN"
wire_api = "responses"
requires_openai_auth = false
''')
    return env


def agent_env(paths: dict[str, Path], isolate_config: bool, agent: str) -> dict[str, str]:
    """Build environment for agent based on type."""
    if agent == "codex":
        return agent_env_codex(paths, isolate_config)
    return agent_env_claude(paths, isolate_config)


def has_api_credentials(agent: str) -> bool:
    """Check if API credentials are available in the environment."""
    if agent == "codex":
        # Check for direct OpenAI key or Docker Gateway token
        return bool(os.environ.get("OPENAI_API_KEY") or os.environ.get("DOCKER_GATEWAY_TOKEN"))
    # Claude
    for key in ("ANTHROPIC_API_KEY", "CLAUDE_CODE_OAUTH_TOKEN"):
        if os.environ.get(key):
            return True
    return False


def list_resources(scenario: Scenario) -> set[str] | None:
    """List current resources using scenario's CLI config.

    Returns None when the listing could not be taken. An unknown listing is
    never treated as empty: that would make every existing resource look
    newly created and eligible for forced removal.
    """
    cli = scenario.cli
    if not cli or not cli.cleanup_list:
        return set()
    try:
        result = subprocess.run(cli.cleanup_list, capture_output=True, text=True, timeout=30, check=False)
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return None
    if result.returncode != 0:
        return None
    return {line.strip() for line in result.stdout.splitlines() if line.strip()}


# Shell words that may precede a command without being the command itself.
_SHELL_PREFIX_WORDS = {"if", "then", "else", "elif", "do", "while", "until", "!", "time", "{", "}"}
_SHELL_SEPARATORS = {";", "&&", "||", "|", "&", "(", ")", ";;", "|&"}


def shell_invocations(command: str, program: str) -> list[list[str]]:
    """argv lists for every invocation of `program` in a shell command line.

    Unlike cli_calls(), which grades only segments that start with the CLI,
    this also finds invocations inside compound commands (`if sbx create ...;
    then`, `X=$(sbx run ...)`, `! sbx ...`), so ownership is not missed.
    """
    found = []
    for line in command.splitlines():
        lexer = shlex.shlex(line, posix=True, punctuation_chars=True)
        lexer.whitespace_split = True
        lexer.commenters = ""
        try:
            tokens = list(lexer)
        except ValueError:  # unbalanced quotes: fall back to whitespace words
            tokens = line.split()
        segment: list[str] = []
        for token in [*tokens, ";"]:
            if token not in _SHELL_SEPARATORS:
                segment.append(token)
                continue
            words = list(segment)
            segment = []
            while words and (words[0] in _SHELL_PREFIX_WORDS
                             or ("=" in words[0] and not words[0].startswith("-"))
                             or words[0] == "$"):
                words.pop(0)
            if words and (words[0] == program or words[0].endswith("/" + program)):
                found.append(words)
    return found


def referenced_names(scenario: Scenario, transcript_path: Path, agent: str) -> set[str]:
    """Names the scenario owns: those its CLI calls targeted, plus declared ones."""
    if not scenario.cli:
        return set()
    if not transcript_path.is_file():
        return set(scenario.cli.cleanup_owned_names)
    declared = set(scenario.cli.cleanup_owned_names)
    try:
        lines = transcript_path.read_text(encoding="utf-8").splitlines()
        transcript = parse_transcript(lines, agent)
        calls = transcript.cli_calls(scenario.cli)
        for tc in transcript.tool_calls:
            if tc.name in ("Bash", "command_execution"):
                for argv in shell_invocations(str(tc.input.get("command", "")), scenario.cli.command):
                    calls.append(enrich_call({"argv": argv}, scenario.cli))
    except (OSError, ValueError, KeyError, TypeError, AttributeError):
        # A truncated or malformed transcript names nothing: never guess.
        return declared
    return {str(c["name"]) for c in calls if c.get("name")} | declared


def cleanup_resources(scenario: Scenario, before: set[str] | None, owned: set[str]) -> list[str]:
    """Remove resources this run created and the scenario owns.

    Only names that were absent before the run, present after it, and in
    `owned` (targeted by the agent's own CLI calls, or declared by the
    scenario) are removed, so a resource
    another user or process creates meanwhile is left alone. Returns notes
    about anything skipped, for the run's stderr log.
    """
    cli = scenario.cli
    if not cli or not cli.cleanup_list or not cli.cleanup_remove:
        return []
    if before is None:
        return ["cleanup skipped: the pre-run listing failed, so pre-existing resources are unknown"]
    after = list_resources(scenario)
    if after is None:
        return ["cleanup skipped: the post-run listing failed"]
    created = after - before
    removable = created & owned
    notes = []
    unowned = sorted(created - owned)
    if unowned:
        notes.append("cleanup left resources the agent never named: " + ", ".join(unowned))
    if removable:
        try:
            result = subprocess.run([*cli.cleanup_remove, *sorted(removable)], capture_output=True,
                                    text=True, timeout=60, check=False)
        except (subprocess.TimeoutExpired, FileNotFoundError) as exc:
            notes.append(f"cleanup of {', '.join(sorted(removable))} failed: {exc}")
        else:
            if result.returncode != 0:
                notes.append(f"cleanup of {', '.join(sorted(removable))} exited {result.returncode}: "
                             f"{(result.stderr or '').strip()[:200]}")
    return notes


def run_scenario(scenario: Scenario, args: argparse.Namespace, run_dir: Path, use_host_config: bool) -> list[Check]:
    run_dir.mkdir(parents=True, exist_ok=True)

    # Snapshot resources before the run so we only clean up what the agent creates
    resources_before = list_resources(scenario)

    paths = prepare_workspace(scenario, run_dir, args.only_target_skill, args.agent)
    command = agent_command(scenario, args, use_host_config)
    meta = {
        "scenario": str(scenario.path.relative_to(REPO_ROOT)),
        "workspace": str(paths["workspace"]),
        "model": args.model,
        "agent": args.agent,
        "command": command,
        "started": datetime.datetime.now(datetime.timezone.utc).isoformat(),
    }
    (run_dir / "run.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")
    transcript_path = run_dir / "transcript.jsonl"

    try:
        with open(transcript_path, "w", encoding="utf-8") as out, open(run_dir / "stderr.txt", "w", encoding="utf-8") as err:
            subprocess.run(command, cwd=paths["workspace"],
                           env=agent_env(paths, not use_host_config, args.agent),
                           stdin=subprocess.DEVNULL, stdout=out, stderr=err,
                           timeout=scenario.limits["timeout_seconds"], check=False)
    except subprocess.TimeoutExpired:
        (run_dir / "stderr.txt").open("a", encoding="utf-8").write("\nskill-eval: agent timed out\n")
    except FileNotFoundError as exc:
        raise ScenarioError(f"cannot start agent {args.agent_bin!r}: {exc}") from exc

    # Clean up only resources created during this run that the agent named
    owned = referenced_names(scenario, transcript_path, args.agent)
    notes = cleanup_resources(scenario, resources_before, owned)
    if notes:
        with open(run_dir / "stderr.txt", "a", encoding="utf-8") as err:
            err.writelines(f"\nskill-eval: {note}\n" for note in notes)
        for note in notes:
            print(f"skill-eval: {note}", file=sys.stderr)

    # Grade
    checks = regrade(run_dir)

    if not args.keep:
        shutil.rmtree(paths["root"], ignore_errors=True)

    return checks


def regrade(run_dir: Path) -> list[Check]:
    meta = json.loads((run_dir / "run.json").read_text(encoding="utf-8"))
    scenario = load_scenario(REPO_ROOT / meta["scenario"])
    agent = meta.get("agent", "claude")  # Default to claude for backward compatibility
    transcript = parse_transcript((run_dir / "transcript.jsonl").read_text(encoding="utf-8").splitlines(), agent)
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
    passed = all(c.passed for c in checks if not c.optional)
    print(f"\n{'PASS' if passed else 'FAIL'}: {label}  ({run_dir})")
    for check in checks:
        mark = "✓" if check.passed else ("○" if check.optional else "✗")
        detail = f" — {check.detail}" if check.detail and (not check.passed or os.environ.get("SKILL_EVAL_VERBOSE")) else ""
        optional_note = " (optional)" if check.optional and not check.passed else ""
        print(f"  {mark} {check.name}{optional_note}{detail}")
    report = json.loads((run_dir / "report.json").read_text(encoding="utf-8"))
    print(f"  turns={report.get('num_turns')} cost=${report.get('cost_usd') or 0:.4f} skills={report.get('skills_invoked')}")
    for call in report.get("cli_calls") or []:
        print(f"    {call}")


def write_summary(results: list[tuple[str, Path, list[Check]]], agent: str) -> None:
    summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if not summary:
        return
    lines = [f"## Live skill evals ({agent})", "", "| Scenario | Result | Failed checks |", "|---|---|---|"]
    for label, _, checks in results:
        failed = [c.name for c in checks if not c.passed]
        lines.append(f"| `{label}` | {'✅' if not failed else '❌'} | {'<br>'.join(failed) or '—'} |")
    with open(summary, "a", encoding="utf-8") as handle:
        handle.write("\n".join(lines) + "\n")


def summarize(results: list[tuple[str, Path, list[Check]]], min_pass_rate: float, out: Path, agent: str) -> int:
    """Print per-scenario pass rates; return 1 if any is below the threshold."""
    by_scenario: dict[str, list[bool]] = {}
    for label, _, checks in results:
        # Only count non-optional checks for pass/fail
        by_scenario.setdefault(label.split(" #")[0], []).append(all(c.passed for c in checks if not c.optional))
    print()
    failing = []
    for key, outcomes in by_scenario.items():
        rate = sum(outcomes) / len(outcomes)
        ok = rate >= min_pass_rate
        failing += [] if ok else [key]
        print(f"{'PASS' if ok else 'FAIL'}: {key} {sum(outcomes)}/{len(outcomes)} runs passed "
              f"(rate {rate:.0%}, required {min_pass_rate:.0%})")
    print(f"artifacts in {out} (agent: {agent})")
    return 1 if failing else 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("scenarios", nargs="*", help="scenario files or directories (default: all)")
    parser.add_argument("--skill", help="only run scenarios for this skill id")
    parser.add_argument("--agent", choices=SUPPORTED_AGENTS, default=os.environ.get("SKILL_EVAL_AGENT", "claude"),
                        help="agent to use: claude or codex (default: claude)")
    parser.add_argument("--model", default=os.environ.get("SKILL_EVAL_MODEL"),
                        help="model alias or name (default: agent's default)")
    parser.add_argument("--repeat", type=int, default=int(os.environ.get("SKILL_EVAL_REPEAT", "1")),
                        help="runs per scenario")
    parser.add_argument("--min-pass-rate", type=float, default=float(os.environ.get("SKILL_EVAL_MIN_PASS_RATE", "1.0")),
                        help="fraction of a scenario's runs that must pass (default 1.0)")
    parser.add_argument("--agent-bin", default=None,
                        help="path to agent binary (default: claude or codex based on --agent)")
    # Legacy alias for --agent-bin
    parser.add_argument("--claude-bin", dest="agent_bin_legacy", default=os.environ.get("CLAUDE_BIN"),
                        help=argparse.SUPPRESS)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT, help="artifact directory")
    parser.add_argument("--only-target-skill", action="store_true",
                        help="install only the scenario's skill instead of every repository skill")
    parser.add_argument("--host-agent-config", action="store_true",
                        help="use your normal agent config dir (e.g. subscription login) instead of an isolated one; "
                             "auto-enabled when API key is not set")
    # Legacy alias for --host-agent-config
    parser.add_argument("--host-claude-config", dest="host_agent_config_legacy", action="store_true",
                        help=argparse.SUPPRESS)
    parser.add_argument("--keep", action="store_true", help="keep the temporary agent workspace")
    parser.add_argument("--regrade", type=Path, metavar="RUN_DIR", help="re-grade saved artifacts without running the agent")
    args = parser.parse_args(argv)
    
    # Handle legacy arguments
    if args.host_agent_config_legacy:
        args.host_agent_config = True
    else:
        args.host_agent_config = getattr(args, "host_agent_config", False)
    
    # Determine agent binary
    if args.agent_bin:
        pass  # User specified explicitly
    elif args.agent_bin_legacy and args.agent == "claude":
        # Legacy CLAUDE_BIN only applies to Claude agent
        args.agent_bin = args.agent_bin_legacy
    else:
        # Default based on agent type
        args.agent_bin = args.agent
    
    # Set default model based on agent if not specified
    if not args.model:
        if args.agent == "codex":
            args.model = None  # Let Codex use its default
        else:
            args.model = "sonnet"

    try:
        if args.regrade:
            checks = regrade(args.regrade)
            print_report(str(args.regrade), args.regrade, checks)
            return 0 if all(c.passed for c in checks) else 1
        scenarios = discover(args.scenarios, args.skill)
        if not scenarios:
            print("skill-eval: no scenarios selected", file=sys.stderr)
            return 2
        if not shutil.which(args.agent_bin):
            install_hint = {
                "claude": "npm install -g @anthropic-ai/claude-code",
                "codex": "npm install -g @openai/codex",
            }.get(args.agent, f"install {args.agent}")
            print(f"skill-eval: {args.agent_bin!r} not found; {install_hint}",
                  file=sys.stderr)
            return 2

        # Auto-enable host config if no API key is set (use subscription login)
        use_host_config = args.host_agent_config or not has_api_credentials(args.agent)
        if use_host_config and not args.host_agent_config:
            key_name = "OPENAI_API_KEY" if args.agent == "codex" else "ANTHROPIC_API_KEY"
            print(f"skill-eval: no {key_name} found, using host {args.agent} config (subscription login)", file=sys.stderr)

        stamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
        results = []
        for scenario in scenarios:
            for attempt in range(1, args.repeat + 1):
                label = scenario.key + (f" #{attempt}" if args.repeat > 1 else "")
                run_dir = args.out / stamp / scenario.skill / scenario.id / str(attempt)
                print(f"running {label} ({args.agent}) ...", flush=True)
                checks = run_scenario(scenario, args, run_dir, use_host_config)
                print_report(label, run_dir, checks)
                results.append((label, run_dir, checks))
    except ScenarioError as exc:
        print(f"skill-eval: {exc}", file=sys.stderr)
        return 2
    write_summary(results, args.agent)
    return summarize(results, args.min_pass_rate, args.out / stamp, args.agent)


if __name__ == "__main__":
    sys.exit(main())

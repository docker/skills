"""Normalize Claude Code stream-json and Codex exec --json output into one record."""

from __future__ import annotations

import json
import re
from typing import Any, Iterable

# A command or path that reads a skill's SKILL.md, e.g.
#   cat .agents/skills/docker-destructive-guardrails/SKILL.md
#   /home/agent/.claude/skills/docker-destructive-guardrails/SKILL.md
SKILL_FILE_RE = re.compile(r"(?:^|[\s'\"=/])skills/([a-z0-9][a-z0-9-]*)/SKILL\.md")


def _empty(agent: str) -> dict[str, Any]:
    return {
        "agent": agent,
        "session_id": None,
        "model": None,
        "cli_version": None,
        "available_skills": None,
        # MCP servers the agent reported at startup. The arms configure none, so any
        # entry here (e.g. claude.ai account connectors) is an isolation leak.
        "mcp_servers": None,
        "final_text": "",
        "commands": [],
        "tool_uses": [],
        "skill_loads": [],
        "usage": {"input_tokens": 0, "cached_input_tokens": 0, "output_tokens": 0},
        "cost_usd": None,
        "num_turns": None,
        "is_error": False,
        "permission_denials": [],
        "parse_errors": 0,
    }


def _lines(text: str) -> Iterable[dict[str, Any]]:
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            value = json.loads(line)
        except json.JSONDecodeError:
            yield {"_unparsed": line}
            continue
        if isinstance(value, dict):
            yield value


def _skill_name(value: str) -> str:
    # Plugin skills are namespaced as "<plugin>:<skill>".
    return value.split(":", 1)[-1]


def _add_skill_load(record: dict[str, Any], skill: str, method: str) -> None:
    if not any(load["skill"] == skill and load["method"] == method for load in record["skill_loads"]):
        record["skill_loads"].append({"skill": skill, "method": method})


def parse_claude(text: str) -> dict[str, Any]:
    record = _empty("claude-code")
    texts: list[str] = []
    for event in _lines(text):
        if "_unparsed" in event:
            record["parse_errors"] += 1
            continue
        kind = event.get("type")
        if kind == "system" and event.get("subtype") == "init":
            record["session_id"] = event.get("session_id")
            record["model"] = event.get("model")
            record["cli_version"] = event.get("claude_code_version")
            record["available_skills"] = [_skill_name(s) for s in event.get("skills") or []]
            record["mcp_servers"] = sorted(str(server.get("name")) for server in event.get("mcp_servers") or []
                                           if isinstance(server, dict) and server.get("name"))
        elif kind == "assistant":
            content = (event.get("message") or {}).get("content") or []
            for block in content if isinstance(content, list) else []:
                if block.get("type") == "text":
                    texts.append(block.get("text", ""))
                elif block.get("type") == "tool_use":
                    name = block.get("name")
                    tool_input = block.get("input") or {}
                    record["tool_uses"].append({"name": name, "input": tool_input})
                    if name == "Skill":
                        skill = tool_input.get("skill") or tool_input.get("command") or ""
                        if skill:
                            _add_skill_load(record, _skill_name(str(skill)), "skill_tool")
                    elif name == "Bash":
                        command = str(tool_input.get("command", ""))
                        record["commands"].append(command)
                        for skill in SKILL_FILE_RE.findall(command):
                            _add_skill_load(record, skill, "shell_read")
                    elif name == "Read":
                        for skill in SKILL_FILE_RE.findall(str(tool_input.get("file_path", ""))):
                            _add_skill_load(record, skill, "file_read")
        elif kind == "result":
            record["session_id"] = event.get("session_id") or record["session_id"]
            record["final_text"] = event.get("result") or (texts[-1] if texts else "")
            record["is_error"] = bool(event.get("is_error"))
            record["cost_usd"] = event.get("total_cost_usd")
            record["num_turns"] = event.get("num_turns")
            record["permission_denials"] = event.get("permission_denials") or []
            usage = event.get("usage") or {}
            record["usage"] = {
                "input_tokens": int(usage.get("input_tokens") or 0) + int(usage.get("cache_creation_input_tokens") or 0)
                + int(usage.get("cache_read_input_tokens") or 0),
                "cached_input_tokens": int(usage.get("cache_read_input_tokens") or 0),
                "output_tokens": int(usage.get("output_tokens") or 0),
            }
    if not record["final_text"] and texts:
        record["final_text"] = texts[-1]
    return record


def parse_codex(text: str) -> dict[str, Any]:
    record = _empty("codex")
    messages: list[str] = []
    for event in _lines(text):
        if "_unparsed" in event:
            record["parse_errors"] += 1
            continue
        kind = event.get("type")
        if kind == "thread.started":
            record["session_id"] = event.get("thread_id")
        elif kind == "item.completed":
            item = event.get("item") or {}
            item_type = item.get("type") or item.get("item_type")
            if item_type == "agent_message":
                messages.append(item.get("text", ""))
            elif item_type == "command_execution":
                command = str(item.get("command", ""))
                record["commands"].append(command)
                record["tool_uses"].append({"name": "command_execution", "input": {"command": command},
                                            "exit_code": item.get("exit_code")})
                for skill in SKILL_FILE_RE.findall(command):
                    _add_skill_load(record, skill, "shell_read")
            elif item_type:
                record["tool_uses"].append({"name": item_type, "input": {}})
        elif kind == "turn.completed":
            usage = event.get("usage") or {}
            record["usage"]["input_tokens"] += int(usage.get("input_tokens") or 0)
            record["usage"]["cached_input_tokens"] += int(usage.get("cached_input_tokens") or 0)
            record["usage"]["output_tokens"] += int(usage.get("output_tokens") or 0)
        elif kind in ("turn.failed", "error"):
            record["is_error"] = True
    record["final_text"] = messages[-1] if messages else ""
    return record


def parse(agent: str, text: str) -> dict[str, Any]:
    if agent == "claude-code":
        return parse_claude(text)
    if agent == "codex":
        return parse_codex(text)
    raise ValueError(f"unknown agent {agent!r}")

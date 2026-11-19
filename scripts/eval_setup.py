#!/usr/bin/env python3
"""Install the agent CLI and the docker-skills plugin for live skill evals.

eval_judge.py runs each prompt against the plugin as users install it: the
pinned agent CLI adds this checkout as a marketplace and installs the plugin
into a throwaway config directory, so the agent sees the manifests, the
namespaced skills and the plugin's MCP server, and nothing from the user's
own agent configuration. CI and `task eval:judge` share this code path.

The agent CLI comes from npm into .eval-tools/<agent>-<version>/. Pinned
versions live in scripts/eval_cli_versions.json; the weekly CI run uses the
latest release instead, to catch a new CLI release breaking the plugin.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import threading
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SKILLS_ROOT = REPO_ROOT / "skills"
CLI_VERSIONS_FILE = REPO_ROOT / "scripts" / "eval_cli_versions.json"
TOOLS_ROOT = REPO_ROOT / ".eval-tools"

NPM_PACKAGES = {"claude": "@anthropic-ai/claude-code"}
PLUGIN_NAME = "docker-skills"
MARKETPLACE_NAME = "docker"
PLUGIN_ID = f"{PLUGIN_NAME}@{MARKETPLACE_NAME}"
MCP_SERVER = "docker-docs"
# Claude Code exposes plugin MCP servers as plugin:<plugin>:<server>, and their
# tools as mcp__plugin_<plugin>_<server>__<tool>
CLAUDE_MCP_SERVER = f"plugin:{PLUGIN_NAME}:{MCP_SERVER}"
CLAUDE_MCP_TOOLS = f"mcp__plugin_{PLUGIN_NAME}_{MCP_SERVER}"

VERSION_RE = re.compile(r"\b(\d+)\.(\d+)\.(\d+)\b")
SETUP_TIMEOUT = 300


class SetupError(Exception):
    pass


def _run(cmd: list[str], env: dict[str, str] | None = None, timeout: int = SETUP_TIMEOUT) -> str:
    try:
        proc = subprocess.run(cmd, env=env, capture_output=True, text=True, timeout=timeout, check=False)
    except FileNotFoundError as e:
        raise SetupError(f"{cmd[0]} not found") from e
    except subprocess.TimeoutExpired as e:
        raise SetupError(f"timed out after {timeout}s: {' '.join(cmd)}") from e
    if proc.returncode != 0:
        output = (proc.stderr or proc.stdout).strip()
        raise SetupError(f"{' '.join(cmd)} failed with exit code {proc.returncode}:\n{output}")
    return proc.stdout


# ─── agent CLI ───────────────────────────────────────────────────────────────

def pinned_version(agent: str) -> str:
    versions = json.loads(CLI_VERSIONS_FILE.read_text())
    return versions[agent]


def parse_version(text: str) -> tuple[int, int, int]:
    match = VERSION_RE.search(text)
    if not match:
        raise SetupError(f"no X.Y.Z version in {text.strip()!r}")
    return tuple(int(part) for part in match.groups())  # type: ignore[return-value]


def resolve_version(agent: str, requested: str) -> str:
    """Turn 'pinned', 'latest' or an explicit X.Y.Z into an exact version."""
    if requested == "pinned":
        return pinned_version(agent)
    if requested == "latest":
        return _run(["npm", "view", NPM_PACKAGES[agent], "version"]).strip()
    if not re.fullmatch(r"\d+\.\d+\.\d+", requested):
        raise SetupError(f"--cli-version must be 'pinned', 'latest' or X.Y.Z, not {requested!r}")
    return requested


def ensure_cli(agent: str, version: str, tools_root: Path = TOOLS_ROOT) -> Path:
    """Install the agent CLI at this exact version unless already present; return its binary."""
    prefix = tools_root / f"{agent}-{version}"
    binary = prefix / "node_modules" / ".bin" / agent
    if binary.exists():
        return binary
    package = NPM_PACKAGES[agent]
    print(f"Installing {package}@{version} into {prefix}", flush=True)
    prefix.mkdir(parents=True, exist_ok=True)
    _run(["npm", "install", "--prefix", str(prefix), "--no-save", "--no-audit", "--no-fund",
          "--ignore-scripts", f"{package}@{version}"])
    if agent == "claude":
        # --ignore-scripts skips the package's postinstall, which fetches the native binary
        _run(["node", str(prefix / "node_modules" / package / "install.cjs")])
    if not binary.exists():
        raise SetupError(f"{package}@{version} installed no {binary}")
    return binary


def cli_version(binary: Path | str) -> str:
    out = _run([str(binary), "--version"], timeout=60)
    return ".".join(str(p) for p in parse_version(out))


def check_min_version(agent: str, binary: Path | str) -> str:
    """Refuse a CLI older than the pinned version: older CLIs reject newer manifest fields."""
    found = cli_version(binary)
    pinned = pinned_version(agent)
    if parse_version(found) < parse_version(pinned):
        raise SetupError(
            f"{binary} is version {found}, older than the pinned {pinned} in "
            f"{CLI_VERSIONS_FILE.relative_to(REPO_ROOT)}. Drop --agent-bin to use the pinned CLI, "
            "or upgrade it."
        )
    return found


# ─── plugin install ──────────────────────────────────────────────────────────

def expected_skills(skills_root: Path = SKILLS_ROOT) -> set[str]:
    return {p.parent.name for p in skills_root.glob("*/SKILL.md")}


def claude_env(config_dir: Path) -> dict[str, str]:
    """Variables that point Claude Code at the isolated config dir."""
    return {"CLAUDE_CONFIG_DIR": str(config_dir)}


def install_claude_plugin(binary: Path | str, config_dir: Path, repo_root: Path = REPO_ROOT) -> dict[str, str]:
    """Install the plugin from this checkout into an isolated Claude config dir.

    Returns the variables to add to agent runs. CLAUDE_CONFIG_DIR (not HOME)
    keeps the user's own plugins and settings out, while sbx and Docker
    logins, which live under HOME, keep working.
    """
    config_dir.mkdir(parents=True, exist_ok=True)
    overrides = claude_env(config_dir)
    env = {**os.environ, **overrides}
    _run([str(binary), "plugin", "marketplace", "add", str(repo_root)], env=env)
    _run([str(binary), "plugin", "install", PLUGIN_ID], env=env)
    return overrides


def claude_session_init(binary: Path | str, overrides: dict[str, str], cwd: Path, timeout: int = 60) -> dict:
    """Return the init event of a headless session: the plugins, skills and MCP
    servers the agent would see. An invalid API key keeps the model from being
    called; the init event is emitted before any request."""
    preflight_env = {k: v for k, v in os.environ.items() if k != "CLAUDE_CODE_OAUTH_TOKEN"}
    preflight_env.update(overrides)
    preflight_env["ANTHROPIC_API_KEY"] = "sk-ant-eval-preflight-invalid"
    cmd = [str(binary), "-p", "preflight", "--output-format", "stream-json", "--verbose", "--max-turns", "1"]
    proc = subprocess.Popen(cmd, cwd=cwd, env=preflight_env, stdin=subprocess.DEVNULL,
                            stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True)
    timer = threading.Timer(timeout, proc.kill)
    timer.start()
    try:
        for line in proc.stdout:  # type: ignore[union-attr]
            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(event, dict) and event.get("type") == "system" and event.get("subtype") == "init":
                return event
    finally:
        timer.cancel()
        proc.kill()
        proc.wait()
    raise SetupError(f"no init event from {' '.join(cmd)} within {timeout}s")


def check_claude_init(init: dict, expected: set[str]) -> list[str]:
    """Compare what a session loaded with what the checkout ships."""
    errors = []
    plugins = {p.get("name") for p in init.get("plugins", []) if p.get("path") != "builtin"}
    if plugins != {PLUGIN_NAME}:
        errors.append(f"expected only the {PLUGIN_NAME} plugin, session loaded {sorted(plugins)}")
    prefix = f"{PLUGIN_NAME}:"
    loaded = {s[len(prefix):] for s in init.get("skills", []) if s.startswith(prefix)}
    if missing := sorted(expected - loaded):
        errors.append(f"skills missing from the installed plugin: {missing}")
    if extra := sorted(loaded - expected):
        errors.append(f"unexpected skills in the installed plugin: {extra}")
    servers = {s.get("name") for s in init.get("mcp_servers", [])}
    if CLAUDE_MCP_SERVER not in servers:
        errors.append(f"MCP server {CLAUDE_MCP_SERVER} not registered (found {sorted(servers)})")
    return errors


def setup_claude_plugin(binary: Path | str, config_dir: Path, cwd: Path,
                        repo_root: Path = REPO_ROOT, skills_root: Path = SKILLS_ROOT) -> dict[str, str]:
    """Install the plugin, then fail before any eval runs if the agent would not see it.

    Returns the variables to add to agent runs."""
    overrides = install_claude_plugin(binary, config_dir, repo_root)
    init = claude_session_init(binary, overrides, cwd)
    expected = expected_skills(skills_root)
    errors = check_claude_init(init, expected)
    if errors:
        raise SetupError("plugin install check failed:\n  " + "\n  ".join(errors))
    mcp = next((s for s in init.get("mcp_servers", []) if s.get("name") == CLAUDE_MCP_SERVER), {})
    print(f"Installed {PLUGIN_ID}: {len(expected)} skills, "
          f"MCP server {MCP_SERVER} {mcp.get('status', 'unknown')}", flush=True)
    return overrides

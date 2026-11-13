#!/usr/bin/env python3
"""Run skill evaluations using LLM-as-judge.

This script reads evaluation prompts from skill eval.md files and runs each
prompt through Claude Code or Codex, using an LLM judge to grade the full
transcript against the expected behaviors and must-not criteria.

Eval files are discovered from:
  1. skills/<skill>/evals/<skill>.md (preferred location)
  2. evals/<skill>.md (legacy location)

The LLM judge approach replaces complex CLI step matching - the judge
can evaluate both knowledge-based responses AND whether correct commands
were used, all from the transcript.

Usage:
  python3 scripts/eval_judge.py                           # all evals with claude
  python3 scripts/eval_judge.py --agent codex             # all evals with codex
  python3 scripts/eval_judge.py --skill docker-sandboxes-lifecycle
  python3 scripts/eval_judge.py --skill docker-sandboxes-lifecycle --prompt 1
  python3 scripts/eval_judge.py --list                    # show available evals
  python3 scripts/eval_judge.py --regrade .eval-judge/<run>/...  # re-grade offline
"""

from __future__ import annotations

import argparse
import dataclasses
import datetime
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent
EVALS_ROOT = REPO_ROOT / "evals"
SKILLS_ROOT = REPO_ROOT / "skills"
DEFAULT_OUT = REPO_ROOT / ".eval-judge"
JUDGE_ATTEMPTS = 3  # retries for malformed judge JSON or transient API errors
JUDGE_PREFILL = '{"evaluations": ['  # Anthropic judge reply starts here


class JudgeAPIError(RuntimeError):
    """HTTP error from the judge API; only rate limits and server errors are retryable."""

    def __init__(self, status: int, body: str):
        super().__init__(f"API error {status}: {body}")
        self.status = status
        self.retryable = status == 429 or status >= 500

DEFAULT_LIMITS = {"max_turns": 25, "max_budget_usd": 0.50, "timeout_seconds": 300}


class EvalError(Exception):
    pass


# ─── eval parsing ────────────────────────────────────────────────────────────

@dataclasses.dataclass
class EvalPrompt:
    """A single evaluation prompt from a markdown eval file."""
    eval_file: Path
    skill: str
    prompt_num: int
    title: str
    prompt: str
    expected_behaviors: list[str]
    must_not: list[str]
    # Set by a "**Skip in CI:** <reason>" line, e.g. the prompt needs a real MCP server
    skip_reason: str | None = None
    # Files written into the agent's workspace before the run ("**Fixtures:**" block)
    fixtures: dict[str, str] = dataclasses.field(default_factory=dict)

    @property
    def id(self) -> str:
        return f"{self.skill}/prompt-{self.prompt_num}"


def _parse_checkbox_section(section: str, heading: str) -> list[str]:
    """Parse checkbox items from a ### section, handling multi-line criteria."""
    pattern = rf'### {re.escape(heading)}\s*\n((?:- \[[ x]\] .+(?:\n(?:[ \t]+[^\n]+)?)*)+)'
    match = re.search(pattern, section)
    if not match:
        return []
    
    items = []
    current = None
    for line in match.group(1).split('\n'):
        m = re.match(r'- \[[ x]\] (.+)', line)
        if m:
            if current:
                items.append(current.strip())
            current = m.group(1)
        elif current and line.strip():
            current += ' ' + line.strip()
    if current:
        items.append(current.strip())
    return items


def parse_eval_markdown(path: Path) -> list[EvalPrompt]:
    """Parse a markdown eval file and extract all prompts."""
    content = path.read_text(encoding="utf-8")
    
    # Extract skill from "# Eval: skill-name"
    skill_match = re.search(r'^# Eval: (.+)$', content, re.MULTILINE)
    if not skill_match:
        raise EvalError(f"{path}: missing '# Eval: <skill-name>' header")
    skill = skill_match.group(1).strip()
    
    prompts = []
    prompt_pattern = re.compile(r'^## Prompt (\d+): (.+?)$', re.MULTILINE)
    matches = list(prompt_pattern.finditer(content))
    
    for i, match in enumerate(matches):
        num = int(match.group(1))
        title = match.group(2).strip()
        
        # Section content until next prompt
        start = match.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(content)
        section = content[start:end]
        
        # Extract quoted prompt text: every blockquote paragraph right after
        # "Prompt to agent", including ones separated by plain blank lines
        # (e.g. the AUTOMATED EVAL suffix).
        prompt_match = re.search(
            r'\*\*Prompt to agent:\*\*\s*\n((?:>.*(?:\n|$)|[ \t]*\n(?=[ \t]*\n*>))+)', section
        )
        if not prompt_match:
            continue
        paragraphs, current = [], []
        for line in prompt_match.group(1).split('\n'):
            stripped = line.strip()
            # Drop the "> " marker but keep indentation (code blocks in prompts)
            text = re.sub(r'^>[ ]?', '', stripped).rstrip() if stripped.startswith('>') else ''
            if text:
                current.append(text)
            elif current:
                paragraphs.append('\n'.join(current))
                current = []
        if current:
            paragraphs.append('\n'.join(current))
        prompt_text = '\n\n'.join(paragraphs).strip()
        
        expected = _parse_checkbox_section(section, 'Expected behaviors')
        must_not = _parse_checkbox_section(section, 'Must not')
        
        if not expected and not must_not:
            continue
        
        skip_match = re.search(r'^\*\*Skip in CI:\*\*\s*(.+?)\s*$', section, re.MULTILINE)
        prompts.append(EvalPrompt(path, skill, num, title, prompt_text, expected, must_not,
                                  skip_match.group(1) if skip_match else None,
                                  _parse_fixtures(section, path, num)))
    
    return prompts


FIXTURE_RE = re.compile(r'^`([^`\n]+)`:?[ \t]*\n```[^\n]*\n(.*?)^```[ \t]*$', re.MULTILINE | re.DOTALL)


def _parse_fixtures(section: str, path: Path, num: int) -> dict[str, str]:
    """Parse a "**Fixtures:**" block: a backticked relative path, then a fenced block per file."""
    match = re.search(r'^\*\*Fixtures:\*\*[ \t]*\n(.*?)(?=^### |\Z)', section, re.MULTILINE | re.DOTALL)
    if not match:
        return {}
    fixtures = {}
    for rel, content in FIXTURE_RE.findall(match.group(1)):
        rel = rel.strip()
        parts = Path(rel).parts
        if not rel or Path(rel).is_absolute() or ".." in parts:
            raise EvalError(f"{path}: prompt {num}: fixture path must be relative and inside the workspace: {rel!r}")
        fixtures[rel] = content
    if not fixtures:
        raise EvalError(f"{path}: prompt {num}: **Fixtures:** block has no `path` + fenced file entries")
    return fixtures


def discover_evals(skill_name: str | None, prompt_num: int | None) -> list[EvalPrompt]:
    """Find all eval prompts, optionally filtered by skill name.
    
    Looks for eval files in two places:
      1. skills/<skill>/evals/<skill>.md (preferred)
      2. evals/<skill>.md (legacy, only when there is no preferred file)

    An invalid eval file raises EvalError: a broken preferred file must never
    silently fall back to the legacy runbook.
    """
    prompts = []
    seen_skills = set()
    
    # First, check skills/<skill>/evals/<skill>.md (preferred location)
    for skill_dir in sorted(SKILLS_ROOT.iterdir()):
        if not skill_dir.is_dir() or skill_dir.name.startswith("."):
            continue
        if skill_name and skill_dir.name != skill_name:
            continue
        
        eval_file = skill_dir / "evals" / f"{skill_dir.name}.md"
        if eval_file.exists():
            # Mark the skill as seen before parsing, so a parse error is not
            # papered over by the legacy copy
            seen_skills.add(skill_dir.name)
            prompts.extend(parse_eval_markdown(eval_file))
    
    # Then, check evals/<skill>.md (legacy location)
    for md in sorted(EVALS_ROOT.glob("*.md")):
        if md.name == "README.md":
            continue
        # Skip if we already found this skill in the skills directory
        if md.stem in seen_skills:
            continue
        if skill_name and md.stem != skill_name:
            continue
        prompts.extend(parse_eval_markdown(md))
    
    if prompt_num is not None:
        prompts = [p for p in prompts if p.prompt_num == prompt_num]
    return prompts


# ─── LLM judge ───────────────────────────────────────────────────────────────

@dataclasses.dataclass
class JudgeResult:
    criterion: str
    passed: bool
    reasoning: str
    is_must_not: bool = False


# Docker Hub credentials used only by this harness to mint short-lived (~15 min)
# gateway tokens; never passed through to the agent under test.
HUB_CREDENTIAL_VARS = ("DOCKERPUBLICBOT_USERNAME", "DOCKERPUBLICBOT_READ_PAT")
GATEWAY_TOKEN_MAX_AGE = 10 * 60  # refresh well before the 15-minute expiry
_gateway_token_minted_at: float | None = None


def refresh_docker_gateway_token(force: bool = False) -> None:
    """Mint a fresh DOCKER_GATEWAY_TOKEN when Hub credentials are available.

    Gateway tokens expire after ~15 minutes, shorter than a long eval job, so
    the harness re-mints before each agent run once the token is >10 min old.
    No-op locally (no credentials): the existing token or Docker Desktop is used.
    """
    global _gateway_token_minted_at
    import time
    import urllib.request

    user, pat = (os.environ.get(v) for v in HUB_CREDENTIAL_VARS)
    if not (user and pat):
        return
    now = time.monotonic()
    if not force and _gateway_token_minted_at is not None and now - _gateway_token_minted_at < GATEWAY_TOKEN_MAX_AGE:
        return
    req = urllib.request.Request(
        "https://hub.docker.com/v2/users/login",
        data=json.dumps({"username": user, "password": pat}).encode(),
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            token = json.loads(resp.read()).get("token")
    except (OSError, json.JSONDecodeError) as e:
        print(f"Warning: could not refresh gateway token: {e}", file=sys.stderr)
        return
    if token:
        if os.environ.get("GITHUB_ACTIONS") == "true":
            print(f"::add-mask::{token}", flush=True)  # keep refreshed tokens out of CI logs
        os.environ["DOCKER_GATEWAY_TOKEN"] = token
        _gateway_token_minted_at = now


def get_docker_gateway_token() -> str:
    """Get Docker Gateway token from Docker Desktop credentials or environment."""
    import subprocess
    
    refresh_docker_gateway_token()
    # First try environment variable
    token = os.environ.get("DOCKER_GATEWAY_TOKEN")
    if token:
        return token
    
    # Try to get from Docker Desktop credential store
    try:
        result = subprocess.run(
            ["docker-credential-desktop", "get"],
            input="https://index.docker.io/v1/access-token",
            capture_output=True,
            text=True,
            timeout=5
        )
        if result.returncode == 0:
            import json as json_mod
            cred = json_mod.loads(result.stdout)
            return cred.get("Secret", "")
    except (subprocess.TimeoutExpired, FileNotFoundError, json.JSONDecodeError):
        pass
    
    raise RuntimeError("DOCKER_GATEWAY_TOKEN not set and could not retrieve from Docker Desktop")


def call_judge(prompt: str, model: str) -> dict[str, Any]:
    """Call LLM judge via Anthropic API or Docker Gateway (for Luna models)."""
    import urllib.request
    import urllib.error
    
    # Use Docker Gateway for Luna/GPT models, Anthropic for Claude models
    use_docker_gateway = model.startswith("gpt-") or "luna" in model.lower()
    
    if use_docker_gateway:
        api_key = get_docker_gateway_token()
        
        body = json.dumps({
            "model": model,
            "max_completion_tokens": 4096,
            "messages": [{"role": "user", "content": prompt}],
            # Force a JSON object reply instead of a prose analysis
            "response_format": {"type": "json_object"},
        }).encode()
        
        req = urllib.request.Request(
            "https://gw.docker.com/v1/docker/gateways/default/inference/openai/v1/chat/completions",
            data=body,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {api_key}",
            },
        )
    else:
        api_key = os.environ.get("ANTHROPIC_API_KEY")
        if not api_key:
            raise RuntimeError("ANTHROPIC_API_KEY not set")
        
        body = json.dumps({
            "model": model,
            "max_tokens": 4096,
            "messages": [
                {"role": "user", "content": prompt},
                # Prefill: the reply must continue a JSON object, so the judge can't
                # answer with a prose analysis (seen in CI: 3 prose replies in a row)
                {"role": "assistant", "content": JUDGE_PREFILL},
            ],
        }).encode()
        
        req = urllib.request.Request(
            "https://api.anthropic.com/v1/messages",
            data=body,
            headers={
                "Content-Type": "application/json",
                "x-api-key": api_key,
                "anthropic-version": "2023-06-01",
            },
        )
    
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            result = json.loads(resp.read())
    except urllib.error.HTTPError as e:
        raise JudgeAPIError(e.code, e.read().decode() if e.fp else '') from e
    
    # Extract text from response (different format for OpenAI vs Anthropic)
    if use_docker_gateway:
        choice = result.get("choices", [{}])[0]
        text = choice.get("message", {}).get("content", "") or ""
        stop = choice.get("finish_reason")
    else:
        text = (result.get("content") or [{}])[0].get("text", "") or ""
        text = JUDGE_PREFILL + text  # the prefill is not echoed back
        stop = result.get("stop_reason")
    try:
        return parse_judge_json(text)
    except json.JSONDecodeError as e:
        # Keep the stop reason and the start of the reply so empty/truncated
        # judge answers can be diagnosed from the report
        raise json.JSONDecodeError(
            f"{e.msg} [stop_reason={stop}, reply_chars={len(text)}, reply_start={text[:120]!r}]",
            e.doc, e.pos) from e


def parse_judge_json(text: str) -> dict[str, Any]:
    """Parse the judge's JSON reply, repairing common LLM formatting slips.

    Handles a ```json fence, trailing commas before } or ], and a literal
    `...` placeholder line copied from the prompt's example.
    """
    json_match = re.search(r'```(?:json)?\s*\n?(.+?)\n?```', text, re.DOTALL)
    json_str = json_match.group(1) if json_match else text
    # Fall back to the outermost {...} if there is prose around the object
    if not json_match:
        start, end = json_str.find("{"), json_str.rfind("}")
        if start != -1 and end > start:
            json_str = json_str[start:end + 1]

    candidates = [json_str]
    repaired = re.sub(r'^\s*\.\.\.\s*,?\s*$', '', json_str, flags=re.MULTILINE)  # "..." lines
    repaired = re.sub(r',(\s*[}\]])', r'\1', repaired)  # trailing commas
    if repaired != json_str:
        candidates.append(repaired)

    for candidate in candidates:
        try:
            return json.loads(candidate)
        except json.JSONDecodeError:
            pass
        # The outer object may be malformed while the evaluations array is fine
        eval_match = re.search(r'"evaluations"\s*:\s*(\[.+\])', candidate, re.DOTALL)
        if eval_match:
            try:
                return {"evaluations": json.loads(eval_match.group(1))}
            except json.JSONDecodeError:
                pass
    # Re-raise the original error for the caller to report/retry
    return json.loads(json_str)


def judge_transcript(
    transcript: str,
    expected: list[str],
    must_not: list[str],
    model: str,
    workspace_files: dict[str, str] | None = None,
) -> list[JudgeResult]:
    """Have LLM judge evaluate the full transcript against criteria."""
    
    expected_text = "\n".join(f"  {i+1}. {c}" for i, c in enumerate(expected))
    must_not_text = "\n".join(f"  {i+1}. {c}" for i, c in enumerate(must_not))
    
    # Build workspace files section if we have any
    files_section = ""
    if workspace_files:
        files_parts = []
        for path, content in sorted(workspace_files.items()):
            files_parts.append(f"### {path}\n```\n{content}\n```")
        files_section = f"""\n\n## Files Created in Workspace\n\nThe following files were found in the workspace after the agent finished:\n\n{chr(10).join(files_parts)}"""
    
    prompt = f"""You are evaluating an AI agent's response about Docker skills and CLI tools.
The transcript below shows everything the agent said and did (including any tool calls).

## Full Transcript

{transcript}{files_section}

## Criteria

EXPECTED BEHAVIORS (must satisfy all):
{expected_text}

MUST NOT (must not violate any):
{must_not_text}

## Evaluation Rules

1. **Semantic equivalence matters**: If the agent conveys the same meaning using different
   words or phrasing, that satisfies the criterion. Don't require exact phrasing.

2. **Check actual files**: When criteria mention file contents (e.g., ".dockerignore excludes X"),
   look at the actual file in the "Files Created" section, not just what the agent said.
   The file content is the ground truth.

3. **Conditional criteria**: For criteria like "Must NOT do X without also doing Y":
   - If the agent does Y (the required context), then doing X is ALLOWED
   - Only fail if X is done WITHOUT Y being present

4. **Order doesn't matter**: If a criterion says "explain A before mentioning B", as long as
   both A and B are present in the response, consider the criterion satisfied.

5. **Command results**: A "TOOL RESULT (exit code N, ...)" or "TOOL RESULT (error)" marks a
   failed tool call. When a criterion requires a command to succeed, a run with a non-zero
   exit code or an error result does not satisfy it, whatever the output looks like.

## Task

For each criterion, output a JSON evaluation. Write the reasoning FIRST, then the verdict.

For EXPECTED behaviors: set "passed": true if the agent satisfied the criterion (semantically).
For MUST NOT items: set "violated": true ONLY if the agent actually did the forbidden thing.
If the agent avoided it (or did the opposite), set "violated": false.

Return JSON:
{{
  "evaluations": [
    {{"criterion_number": 1, "criterion_type": "expected", "reasoning": "brief why", "passed": true/false}},
    {{"criterion_number": 1, "criterion_type": "must_not", "reasoning": "brief why", "violated": true/false}},
    ...
  ]
}}

Evaluate fairly - if the agent's response achieves the goal of the criterion even if
worded differently, mark it as passed. Order: all expected behaviors first, then all must_not items.

Double-check that each verdict matches your reasoning before responding."""

    result = None
    last_error: Exception | None = None
    verdicts: dict[tuple[bool, int], JudgeResult] = {}
    for _attempt in range(JUDGE_ATTEMPTS):
        try:
            result = call_judge(prompt, model)
        except JudgeAPIError as e:
            last_error = e
            if not e.retryable:
                break  # auth/request errors won't fix themselves
            continue
        except (json.JSONDecodeError, OSError) as e:
            # Malformed judge JSON or a network error: ask the judge again
            last_error = e
            continue
        except RuntimeError as e:
            last_error = e  # e.g. missing API key/token: not retryable
            break
        verdicts = _map_verdicts(result, expected, must_not)
        if len(verdicts) == len(expected) + len(must_not):
            break
        # Valid JSON but some criteria have no verdict: ask again
        last_error = ValueError(
            f"judge returned {len(verdicts)} of {len(expected) + len(must_not)} verdicts")

    if result is None:
        err = f"Judge error after {_attempt + 1} attempt(s): {last_error}"
        return [JudgeResult(c, False, err) for c in expected] + \
               [JudgeResult(c, False, err, True) for c in must_not]

    # Every criterion gets exactly one result; one the judge never graded fails
    missing = f"No judge verdict for this criterion after {_attempt + 1} attempt(s)"
    return [verdicts.get((False, i), JudgeResult(c, False, missing)) for i, c in enumerate(expected)] + \
           [verdicts.get((True, i), JudgeResult(c, False, missing, True)) for i, c in enumerate(must_not)]


def _map_verdicts(result: dict[str, Any], expected: list[str],
                  must_not: list[str]) -> dict[tuple[bool, int], JudgeResult]:
    """Map the judge's evaluations to criteria, keyed by (is_must_not, index).

    Entries with an unknown type, an out-of-range number or no verdict are
    ignored; for duplicates the first verdict wins.
    """
    verdicts: dict[tuple[bool, int], JudgeResult] = {}
    evaluations = result.get("evaluations") if isinstance(result, dict) else None
    for ev in evaluations if isinstance(evaluations, list) else []:
        if not isinstance(ev, dict) or ev.get("criterion_type") not in ("expected", "must_not"):
            continue
        is_must_not = ev["criterion_type"] == "must_not"
        criteria_list = must_not if is_must_not else expected
        try:
            idx = int(ev.get("criterion_number")) - 1
        except (TypeError, ValueError):
            continue
        if not 0 <= idx < len(criteria_list) or (is_must_not, idx) in verdicts:
            continue
        # Only real JSON booleans count: "false" (truthy string) or null would
        # otherwise flip a verdict; anything else is treated as missing
        if is_must_not and isinstance(ev.get("violated"), bool):
            passed = not ev["violated"]
        elif isinstance(ev.get("passed"), bool):
            passed = ev["passed"]
        else:
            continue  # no usable verdict
        verdicts[(is_must_not, idx)] = JudgeResult(
            criteria_list[idx], passed, ev.get("reasoning", ""), is_must_not)
    return verdicts


# ─── agent runner ────────────────────────────────────────────────────────────

def prepare_workspace(eval_prompt: EvalPrompt, agent: str) -> Path:
    """Create workspace with skills installed."""
    root = Path(tempfile.mkdtemp(prefix=f"eval-{eval_prompt.prompt_num}-"))
    workspace = root / "workspace"
    workspace.mkdir()
    
    # Create a minimal README to indicate this is a project workspace
    # This helps agents understand they should create files here.
    # Prompts with fixtures describe their own project instead.
    if not eval_prompt.fixtures:
        readme = workspace / "README.md"
        readme.write_text("# Project Workspace\n\nThis is an empty project workspace. Create the requested files here.\n")
    for rel, content in eval_prompt.fixtures.items():
        target = workspace / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content)
    
    # Claude uses .claude/skills/, Codex uses .agents/skills/
    if agent == "codex":
        skills_dir = workspace / ".agents" / "skills"
    else:
        skills_dir = workspace / ".claude" / "skills"
    skills_dir.mkdir(parents=True)
    for skill in SKILLS_ROOT.iterdir():
        if skill.is_dir() and not skill.name.startswith("."):
            shutil.copytree(skill, skills_dir / skill.name)
    
    return root


# File extensions to collect from workspace for judge context
WORKSPACE_FILE_PATTERNS = [
    "Dockerfile", "Dockerfile.*", "*.dockerfile",
    "compose.yaml", "compose.yml", "compose.*.yaml", "compose.*.yml",
    "compose.override.yaml", "compose.override.yml",
    "docker-compose.yaml", "docker-compose.yml",
    ".dockerignore",
    "agent.yaml", "docker-agent.yaml", "agents.yaml",
    "sbxenv.yaml", ".sbxenv.yaml",
    "*.md",  # READMEs
    "*.yml", "*.yaml",  # CI workflows, kit descriptors, and other config the agent writes
    ".env.example", ".env.sample",
    "requirements.txt", "package.json",  # Dependency files for context
]


def collect_workspace_files(workspace: Path, max_files: int = 20, max_size: int = 50000) -> dict[str, str]:
    """Collect relevant files from workspace for judge context.
    
    Returns a dict of {relative_path: content} for files matching patterns.
    Excludes the .claude/.agents skills directories.
    """
    import fnmatch
    
    files = {}
    total_size = 0
    
    for path in sorted(workspace.rglob("*")):
        if not path.is_file():
            continue
        
        # Skip skills directories
        rel = path.relative_to(workspace)
        rel_str = str(rel)
        if rel_str.startswith(".claude/") or rel_str.startswith(".agents/"):
            continue
        
        # Check if file matches any pattern
        name = path.name
        if not any(fnmatch.fnmatch(name, pat) for pat in WORKSPACE_FILE_PATTERNS):
            continue
        
        # Read file content
        try:
            content = path.read_text(errors="replace")
        except Exception:
            continue
        
        # Size limits
        if len(content) > 10000:
            content = content[:10000] + "\n... (truncated)"
        
        total_size += len(content)
        if total_size > max_size or len(files) >= max_files:
            break
        
        files[rel_str] = content
    
    return files


@dataclasses.dataclass
class AgentRunResult:
    """Result of running an agent."""
    transcript_text: str
    workspace_files: dict[str, str]
    workspace_path: Path  # For cleanup
    exit_code: int | None = None  # None when the agent timed out
    timed_out: bool = False


AGENT_COMPLETION_CRITERION = "Agent run completes successfully (exit code 0, no timeout, completion event)"


def agent_completion_error(result: AgentRunResult, transcript_path: Path, agent: str) -> str | None:
    """Return why the agent run did not complete successfully, or None if it did.

    A partial transcript can still satisfy the criteria, so a run only counts
    when the CLI exited 0 before the timeout and logged a successful
    completion event (Claude: a non-error "result"; Codex: "turn.completed").
    """
    if result.timed_out:
        return f"agent timed out after {DEFAULT_LIMITS['timeout_seconds']}s"
    if result.exit_code != 0:
        return f"agent exited with code {result.exit_code}"
    events = []
    try:
        for line in transcript_path.read_text(errors="replace").splitlines():
            try:
                events.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    except OSError:
        return "agent transcript is missing"
    events = [e for e in events if isinstance(e, dict)]
    if agent == "codex":
        if any(e.get("type") == "turn.failed" for e in events):
            return "agent turn failed"
        if not any(e.get("type") == "turn.completed" for e in events):
            return "agent never completed its turn (no turn.completed event)"
        return None
    final = [e for e in events if e.get("type") == "result"]
    if not final:
        return "agent never completed (no result event)"
    if final[-1].get("is_error") or final[-1].get("subtype") not in (None, "success"):
        return f"agent finished with an error ({final[-1].get('subtype')})"
    return None


def run_agent(eval_prompt: EvalPrompt, args: argparse.Namespace, run_dir: Path) -> AgentRunResult:
    """Run the agent and return transcript + workspace files."""
    run_dir.mkdir(parents=True, exist_ok=True)
    root = prepare_workspace(eval_prompt, args.agent)
    workspace = root / "workspace"
    
    # Build command based on agent type
    if args.agent == "codex":
        cmd = [
            args.agent_bin, "exec",
            "--json",
            "--dangerously-bypass-approvals-and-sandbox",
            "--ephemeral",
            eval_prompt.prompt,
        ]
        if args.model:
            cmd += ["--model", args.model]
    else:  # claude
        cmd = [
            args.agent_bin, "-p", eval_prompt.prompt,
            "--output-format", "stream-json", "--verbose",
            "--permission-mode", "dontAsk",
            "--allowedTools", "Skill", "Read", "Glob", "Grep", "Bash", "Write", "Edit",
            "--disallowedTools", "WebFetch", "WebSearch", "Task",
            "--max-turns", str(DEFAULT_LIMITS["max_turns"]),
            "--max-budget-usd", str(DEFAULT_LIMITS["max_budget_usd"]),
        ]
        if args.model:
            cmd += ["--model", args.model]
    
    # Save metadata
    meta = {
        "eval_file": str(eval_prompt.eval_file.relative_to(REPO_ROOT)),
        "skill": eval_prompt.skill,
        "prompt_num": eval_prompt.prompt_num,
        "title": eval_prompt.title,
        "prompt": eval_prompt.prompt,
        "expected_behaviors": eval_prompt.expected_behaviors,
        "must_not": eval_prompt.must_not,
        "agent": args.agent,
        "started": datetime.datetime.now(datetime.timezone.utc).isoformat(),
    }
    (run_dir / "run.json").write_text(json.dumps(meta, indent=2))
    
    transcript_path = run_dir / "transcript.jsonl"
    refresh_docker_gateway_token()  # long jobs outlive the ~15-minute gateway token
    env = {k: v for k, v in os.environ.items() if v and k not in HUB_CREDENTIAL_VARS}
    
    exit_code: int | None = None
    timed_out = False
    try:
        with open(transcript_path, "w") as out, open(run_dir / "stderr.txt", "w") as err:
            proc = subprocess.run(cmd, cwd=workspace, env=env,
                                  stdin=subprocess.DEVNULL, stdout=out, stderr=err,
                                  timeout=DEFAULT_LIMITS["timeout_seconds"], check=False)
            exit_code = proc.returncode
    except subprocess.TimeoutExpired:
        timed_out = True
    
    # Collect workspace files BEFORE cleanup
    workspace_files = collect_workspace_files(workspace)
    
    # Convert transcript to readable text for the judge
    if args.agent == "codex":
        transcript_text = codex_transcript_to_text(transcript_path)
    else:
        transcript_text = transcript_to_text(transcript_path)
    
    return AgentRunResult(
        transcript_text=transcript_text,
        workspace_files=workspace_files,
        workspace_path=root,
        exit_code=exit_code,
        timed_out=timed_out,
    )


def transcript_to_text(path: Path) -> str:
    """Convert stream-json transcript to readable text for judging."""
    lines = []
    for raw in path.read_text().splitlines():
        if not raw.strip().startswith("{"):
            continue
        try:
            ev = json.loads(raw)
        except json.JSONDecodeError:
            continue
        
        kind = ev.get("type")
        if kind == "assistant":
            content = (ev.get("message") or {}).get("content", [])
            for block in content if isinstance(content, list) else []:
                if block.get("type") == "text":
                    lines.append(f"ASSISTANT: {block.get('text', '')}")
                elif block.get("type") == "tool_use":
                    name = block.get("name", "")
                    inp = json.dumps(block.get("input", {}), indent=2)
                    lines.append(f"TOOL CALL [{name}]: {inp}")
        elif kind == "user":
            content = (ev.get("message") or {}).get("content", [])
            for block in content if isinstance(content, list) else []:
                if block.get("type") == "tool_result":
                    text = block.get("content", "")
                    if isinstance(text, list):
                        text = "\n".join(b.get("text", "") for b in text if isinstance(b, dict))
                    # Keep the failure flag so the judge can tell failed tool calls apart
                    status = " (error)" if block.get("is_error") else ""
                    lines.append(f"TOOL RESULT{status}: {text[:1000]}{'...' if len(str(text)) > 1000 else ''}")
    
    return "\n\n".join(lines)


def codex_transcript_to_text(path: Path) -> str:
    """Convert Codex JSON transcript to readable text for judging."""
    lines = []
    for raw in path.read_text().splitlines():
        if not raw.strip().startswith("{"):
            continue
        try:
            ev = json.loads(raw)
        except json.JSONDecodeError:
            continue
        
        kind = ev.get("type")
        if kind == "item.completed":
            item = ev.get("item") or {}
            item_type = item.get("type")
            
            if item_type == "agent_message":
                text = item.get("text", "")
                if text:
                    lines.append(f"ASSISTANT: {text}")
            elif item_type == "command_execution":
                command = item.get("command", "")
                output = item.get("aggregated_output", "")
                # Extract actual command from shell wrapper
                actual_command = command
                shell_match = re.match(r'^/bin/(?:zsh|bash|sh)\s+-\w*c\s+[\'"]?(.+?)[\'"]?$', command, re.DOTALL)
                if shell_match:
                    actual_command = shell_match.group(1).strip()
                    if actual_command.endswith("'") or actual_command.endswith('"'):
                        actual_command = actual_command[:-1]
                lines.append(f'TOOL CALL [Bash]: {{\n  "command": "{actual_command}"\n}}')
                # Keep the exit code so the judge can tell a failed command from a
                # successful one with the same (or no) output
                exit_code = item.get("exit_code")
                status = item.get("status")
                details = []
                if exit_code is not None:
                    details.append(f"exit code {exit_code}")
                if status and status != "completed":
                    details.append(str(status))
                suffix = f" ({', '.join(details)})" if details else ""
                lines.append(f"TOOL RESULT{suffix}: {output[:1000]}{'...' if len(str(output)) > 1000 else ''}")
            elif item_type == "skill_read":
                skill_path = item.get("skill_path", "")
                # Extract skill name from path
                parts = skill_path.split("/")
                skill_name = ""
                if "skills" in parts:
                    idx = parts.index("skills")
                    if idx + 1 < len(parts):
                        skill_name = parts[idx + 1]
                if skill_name:
                    lines.append(f'TOOL CALL [Skill]: {{\n  "skill": "{skill_name}"\n}}')
                    lines.append(f"TOOL RESULT: Launching skill: {skill_name}")
    
    return "\n\n".join(lines)


# ─── grading ─────────────────────────────────────────────────────────────────

def grade(eval_prompt: EvalPrompt, transcript: str, args: argparse.Namespace,
          workspace_files: dict[str, str] | None = None) -> list[JudgeResult]:
    """Grade transcript using LLM judge."""
    return judge_transcript(
        transcript,
        eval_prompt.expected_behaviors,
        eval_prompt.must_not,
        args.judge_model,
        workspace_files,
    )


def run_and_grade(eval_prompt: EvalPrompt, args: argparse.Namespace, run_dir: Path) -> list[JudgeResult]:
    """Run agent and grade the result."""
    result = run_agent(eval_prompt, args, run_dir)
    (run_dir / "transcript.txt").write_text(result.transcript_text)
    
    # Save workspace files for debugging
    if result.workspace_files:
        files_dir = run_dir / "workspace_files"
        files_dir.mkdir(exist_ok=True)
        for rel_path, content in result.workspace_files.items():
            file_path = files_dir / rel_path
            file_path.parent.mkdir(parents=True, exist_ok=True)
            file_path.write_text(content)
    
    # Grade with workspace files
    results = grade(eval_prompt, result.transcript_text, args, result.workspace_files)
    
    # A run the agent did not finish never passes, whatever the partial output shows
    completion_error = agent_completion_error(result, run_dir / "transcript.jsonl", args.agent)
    if completion_error:
        results.append(JudgeResult(AGENT_COMPLETION_CRITERION, False, completion_error))
    
    # Cleanup workspace now that we're done
    if not args.keep:
        shutil.rmtree(result.workspace_path, ignore_errors=True)
    
    # Save report
    meta = json.loads((run_dir / "run.json").read_text())
    report = {
        **meta,
        "passed": all(r.passed for r in results),
        "agent_exit_code": result.exit_code,
        "agent_timed_out": result.timed_out,
        "agent_completion_error": completion_error,
        "workspace_files": list(result.workspace_files.keys()) if result.workspace_files else [],
        "results": [dataclasses.asdict(r) for r in results],
    }
    (run_dir / "report.json").write_text(json.dumps(report, indent=2))
    
    return results


def load_saved_workspace_files(run_dir: Path) -> dict[str, str]:
    """Reload the workspace files saved with a run (as passed to the judge originally)."""
    files_dir = run_dir / "workspace_files"
    if not files_dir.is_dir():
        return {}
    return {
        p.relative_to(files_dir).as_posix(): p.read_text(errors="replace")
        for p in sorted(files_dir.rglob("*")) if p.is_file()
    }


def regrade(run_dir: Path, args: argparse.Namespace) -> list[JudgeResult]:
    """Re-grade a saved run offline, with the same inputs as the original verdict."""
    meta = json.loads((run_dir / "run.json").read_text())
    transcript = (run_dir / "transcript.txt").read_text()
    previous = {}
    if (run_dir / "report.json").exists():
        previous = json.loads((run_dir / "report.json").read_text())
    
    eval_prompt = EvalPrompt(
        REPO_ROOT / meta["eval_file"], meta["skill"], meta["prompt_num"],
        meta["title"], meta["prompt"], meta["expected_behaviors"], meta["must_not"],
    )
    
    workspace_files = load_saved_workspace_files(run_dir)
    results = grade(eval_prompt, transcript, args, workspace_files)
    
    # Keep the original run's completion status: re-grading must not turn an
    # agent run that did not finish into a pass
    completion_error = previous.get("agent_completion_error")
    if completion_error:
        results.append(JudgeResult(AGENT_COMPLETION_CRITERION, False, completion_error))
    
    report = {**meta, "passed": all(r.passed for r in results),
              "agent_exit_code": previous.get("agent_exit_code"),
              "agent_timed_out": previous.get("agent_timed_out"),
              "agent_completion_error": completion_error,
              "workspace_files": list(workspace_files),
              "results": [dataclasses.asdict(r) for r in results]}
    (run_dir / "report.json").write_text(json.dumps(report, indent=2))
    
    return results


# ─── CLI ─────────────────────────────────────────────────────────────────────

def print_results(label: str, results: list[JudgeResult], run_dir: Path, duration_secs: float | None = None) -> None:
    passed = all(r.passed for r in results)
    time_str = f" ({duration_secs:.1f}s)" if duration_secs is not None else ""
    print(f"\n{'PASS' if passed else 'FAIL'}: {label}{time_str}")
    for r in results:
        mark = "✓" if r.passed else "✗"
        prefix = "must-not" if r.is_must_not else "expected"
        short = r.criterion[:70] + ("..." if len(r.criterion) > 70 else "")
        print(f"  {mark} [{prefix}] {short}")
        if not r.passed and r.reasoning:
            print(f"      → {r.reasoning}")
    print(f"  artifacts: {run_dir}" if run_dir.exists() else "  artifacts: pruned (passed)")


def prune_run_dir(run_dir: Path, out_root: Path) -> None:
    """Delete a passing prompt's artifacts, then any parent dirs left empty (up to out_root)."""
    shutil.rmtree(run_dir, ignore_errors=True)
    parent = run_dir.parent
    out_root = out_root.resolve()
    while parent.resolve() != out_root and out_root in parent.resolve().parents:
        try:
            parent.rmdir()  # only succeeds when empty
        except OSError:
            break
        parent = parent.parent


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--skill", help="Run only this skill's eval")
    parser.add_argument("--prompt", type=int, help="Run only this prompt number")
    parser.add_argument("--agent", choices=["claude", "codex"], default="claude", help="Agent to test")
    parser.add_argument("--model", help="Model for agent (default: 'sonnet' for claude, 'gpt-6-luna' for codex)")
    parser.add_argument("--judge-model", default="claude-sonnet-4-5-20250929", help="Model for judge")
    parser.add_argument("--repeat", type=int, default=1, help="Runs per prompt")
    parser.add_argument("--pass-threshold", type=float, default=1.0,
                        help="Minimum pass rate (0.0-1.0) to exit successfully (default: 1.0 = all must pass)")
    parser.add_argument("--agent-bin", help="Agent CLI binary (default: 'claude' or 'codex')")
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--keep", action="store_true", help="Keep workspaces")
    parser.add_argument("--include-skipped", action="store_true",
                        help="Also run prompts marked '**Skip in CI:**' (e.g. need real MCP servers)")
    parser.add_argument("--prune-passing", action="store_true",
                        help="Delete a prompt's artifacts when it passes, keeping only failures (used in CI)")
    parser.add_argument("--regrade", type=Path, help="Re-grade saved run")
    parser.add_argument("--list", action="store_true", help="List evals")
    args = parser.parse_args(argv)
    
    # Set default model based on agent if not specified
    if args.model is None:
        args.model = "sonnet" if args.agent == "claude" else "gpt-6-luna"
    
    # Set defaults based on agent
    if args.agent_bin is None:
        args.agent_bin = "codex" if args.agent == "codex" else "claude"
    if args.model is None:
        args.model = "" if args.agent == "codex" else "sonnet"
    
    if args.list:
        try:
            listed = discover_evals(args.skill, args.prompt)
        except EvalError as e:
            print(f"Invalid eval file: {e}", file=sys.stderr)
            return 2
        for p in listed:
            print(f"{p.id}: {p.title} ({len(p.expected_behaviors)} expected, {len(p.must_not)} must-not)")
        return 0
    
    if args.regrade:
        results = regrade(args.regrade, args)
        print_results(str(args.regrade), results, args.regrade)
        return 0 if all(r.passed for r in results) else 1
    
    try:
        prompts = discover_evals(args.skill, args.prompt)
    except EvalError as e:
        print(f"Invalid eval file: {e}", file=sys.stderr)
        return 2
    if not prompts:
        print("No evals found", file=sys.stderr)
        return 2
    
    if not shutil.which(args.agent_bin):
        print(f"{args.agent_bin} not found", file=sys.stderr)
        return 2
    
    if not os.environ.get("ANTHROPIC_API_KEY"):
        print("ANTHROPIC_API_KEY required", file=sys.stderr)
        return 2
    
    stamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    all_results = []  # (label, results, duration_secs)
    skill_times: dict[str, list[float]] = {}  # skill -> list of durations
    
    for ep in prompts:
        if ep.skip_reason and not args.include_skipped:
            print(f"SKIP: {ep.id} ({ep.skip_reason})", flush=True)
            continue
        for attempt in range(1, args.repeat + 1):
            label = f"{ep.id}" + (f" #{attempt}" if args.repeat > 1 else "")
            run_dir = args.out / stamp / ep.skill / f"prompt-{ep.prompt_num}" / str(attempt)
            print(f"Running {label}...", flush=True)
            
            start_time = time.time()
            results = run_and_grade(ep, args, run_dir)
            duration = time.time() - start_time
            
            if args.prune_passing and results and all(r.passed for r in results):
                prune_run_dir(run_dir, args.out)
            print_results(label, results, run_dir, duration)
            all_results.append((label, results, duration))
            
            # Track per-skill timing
            if ep.skill not in skill_times:
                skill_times[ep.skill] = []
            skill_times[ep.skill].append(duration)
    
    # Summary
    passed = sum(1 for _, r, _ in all_results if all(x.passed for x in r))
    total_time = sum(d for _, _, d in all_results)
    pass_rate = passed / len(all_results) if all_results else 0
    
    print(f"\n{'='*60}")
    print(f"Total: {passed}/{len(all_results)} passed ({pass_rate*100:.0f}%) in {total_time:.1f}s")
    if args.pass_threshold < 1.0:
        print(f"Pass threshold: {args.pass_threshold*100:.0f}%")
    
    # Per-skill summary table
    if len(skill_times) > 1 or args.skill is None:
        print(f"\n{'Skill':<45} {'Passed':<10} {'Time':<10}")
        print("-" * 65)
        for skill in sorted(skill_times.keys()):
            skill_results = [(l, r, d) for l, r, d in all_results if l.startswith(skill + "/")]
            skill_passed = sum(1 for _, r, _ in skill_results if all(x.passed for x in r))
            skill_total = len(skill_results)
            skill_time = sum(skill_times[skill])
            rate = f"{skill_passed}/{skill_total}"
            print(f"{skill:<45} {rate:<10} {skill_time:.1f}s")
    
    return 0 if (not all_results or pass_rate >= args.pass_threshold) else 1


if __name__ == "__main__":
    sys.exit(main())

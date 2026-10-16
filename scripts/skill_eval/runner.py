"""Run live eval cases: one fresh sbx sandbox per run, driven through headless agent CLIs.

This is the only module that executes sbx or agent commands. Everything it records is
re-scorable offline: raw agent output, state snapshots, and provenance.
"""

from __future__ import annotations

import base64
import concurrent.futures
import dataclasses
import datetime as _dt
import fnmatch
import hashlib
import io
import json
import os
import random
import secrets
import shlex
import shutil
import subprocess
import sys
import tarfile
import tempfile
import threading
from pathlib import Path
from typing import Any, Callable

import yaml

from . import CONFIG_FILE, EVALS_DIR, REPO_ROOT, events, state
from .judge import JUDGE_ERROR, parse_verdict
from .spec import active_cases, case_checks, load_catalog


class SetupError(RuntimeError):
    """Infrastructure failure: the run is recorded as an error, not as an agent failure."""


@dataclasses.dataclass
class Result:
    returncode: int
    stdout: str
    stderr: str
    timed_out: bool = False


class Executor:
    """Runs host commands. Swapped for a fake in tests and for --dry-run."""

    def run(self, argv: list[str], timeout: float | None = None, input: str | None = None) -> Result:
        stdin = {"input": input} if input is not None else {"stdin": subprocess.DEVNULL}
        try:
            proc = subprocess.run(argv, capture_output=True, text=True, timeout=timeout, **stdin)
        except subprocess.TimeoutExpired as exc:
            out = exc.stdout.decode() if isinstance(exc.stdout, bytes) else (exc.stdout or "")
            err = exc.stderr.decode() if isinstance(exc.stderr, bytes) else (exc.stderr or "")
            return Result(124, out, err, timed_out=True)
        except OSError as exc:
            return Result(127, "", str(exc))
        return Result(proc.returncode, proc.stdout, proc.stderr)


class DryRunExecutor(Executor):
    """Prints commands instead of running them and returns plausible empty output."""

    def __init__(self, out=sys.stdout):
        self.out = out
        self.lock = threading.Lock()

    def run(self, argv: list[str], timeout: float | None = None, input: str | None = None) -> Result:
        with self.lock:
            print("  $ " + " ".join(shlex.quote(a) for a in argv), file=self.out)
        script = argv[-1] if argv else ""
        if "##end" in script:
            return Result(0, "##containers\n##volumes\n##images\n##dangling\n##end\n", "")
        return Result(0, "", "")


def load_config(path: Path = CONFIG_FILE) -> dict[str, Any]:
    with open(path, encoding="utf-8") as handle:
        return yaml.safe_load(handle)


def fill(template: list[str], **values: str) -> list[str]:
    out = []
    for part in template:
        for key, value in values.items():
            part = part.replace("{" + key + "}", value)
        out.append(part)
    return out


def merge_settings(base: dict[str, Any], overrides: dict[str, Any]) -> dict[str, Any]:
    """Deep-merge settings; None deletes a key; lists are extended without duplicates."""
    merged = dict(base)
    for key, value in overrides.items():
        if value is None:
            merged.pop(key, None)
        elif isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = merge_settings(merged[key], value)
        elif isinstance(value, list) and isinstance(merged.get(key), list):
            merged[key] = merged[key] + [v for v in value if v not in merged[key]]
        else:
            merged[key] = value
    return merged


def skills_tarball(skill_ids: list[str]) -> bytes:
    """Deterministic tar of the selected skills/<id>/ directories."""
    buffer = io.BytesIO()
    with tarfile.open(fileobj=buffer, mode="w", format=tarfile.PAX_FORMAT) as tar:
        for skill_id in sorted(skill_ids):
            root = REPO_ROOT / "skills" / skill_id
            for path in sorted(p for p in root.rglob("*")):
                if path.is_symlink() or "__pycache__" in path.parts:
                    continue
                info = tar.gettarinfo(str(path), arcname=str(Path(skill_id) / path.relative_to(root)))
                info.uid = info.gid = 0
                info.uname = info.gname = ""
                info.mtime = 0
                if path.is_file():
                    with open(path, "rb") as handle:
                        tar.addfile(info, handle)
                else:
                    tar.addfile(info)
    return buffer.getvalue()


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def workspace_parent(config: dict[str, Any]) -> Path:
    root = config.get("run", {}).get("workspace_root")
    if root:
        Path(os.path.expanduser(root)).mkdir(parents=True, exist_ok=True)
    return Path(tempfile.mkdtemp(prefix="w", dir=os.path.expanduser(root) if root else None))


def sandbox_name(config: dict[str, Any]) -> str:
    return f"{config.get('run', {}).get('name_prefix', 'dev')}-{secrets.token_hex(3)}"


# ── Planning ────────────────────────────────────────────────────────────────


@dataclasses.dataclass
class Selection:
    agents: list[str] | None = None
    models: list[str] | None = None
    arms: list[str] | None = None
    cases: list[str] | None = None
    kinds: list[str] | None = None
    repeats: int | None = None


def resolve_model(config: dict[str, Any], agent: str, alias: str) -> str | None:
    models = (config.get("agents", {}).get(agent) or {}).get("models") or {}
    if alias not in models:
        raise SetupError(f"evals/live.yaml: agents.{agent}.models has no alias {alias!r}")
    model = models[alias]
    if model is None and alias != "default":
        raise SetupError(f"evals/live.yaml: set agents.{agent}.models.{alias} before using it")
    return model


def arm_applies(arm: dict[str, Any], agent: str) -> bool:
    guard = arm.get("guard")
    return not guard or (EVALS_DIR / "arms" / "guards" / f"{guard}.{agent}.json").is_file()


def plan_runs(spec: dict[str, Any], config: dict[str, Any], selection: Selection) -> list[dict[str, Any]]:
    arms = spec["arms"]
    primary = spec["primary_comparison"]
    runs = []
    for case in active_cases(spec):
        if selection.kinds and case["kind"] not in selection.kinds:
            continue
        if selection.cases and not any(fnmatch.fnmatchcase(case["id"], pattern) for pattern in selection.cases):
            continue
        if case["kind"] == "trigger":
            case_arms = [primary[0]]
        elif case["kind"] == "fidelity":
            case_arms = list(primary)
        else:
            case_arms = case.get("arms") or list(arms)
        if selection.arms:
            case_arms = [a for a in case_arms if a in selection.arms]
        repeats = selection.repeats or (spec.get("repeats") or {}).get(case["kind"], 3)
        for agent in spec["agents"]:
            if selection.agents and agent not in selection.agents:
                continue
            for alias in spec["models"][agent]:
                if selection.models and alias not in selection.models:
                    continue
                model = resolve_model(config, agent, alias)
                for arm in case_arms:
                    if not arm_applies(arms[arm] or {}, agent):
                        continue
                    for repeat in range(1, repeats + 1):
                        runs.append({
                            "run_id": f"{case['id']}--{arm}--{agent}--{alias}--r{repeat}",
                            "case_id": case["id"], "kind": case["kind"], "arm": arm, "agent": agent,
                            "model_alias": alias, "model": model, "repeat": repeat,
                        })
    return runs


# ── Sandbox driver ──────────────────────────────────────────────────────────


class Sandbox:
    def __init__(self, executor: Executor, config: dict[str, Any], name: str, log: Callable[[str], None]):
        self.x = executor
        self.sbx = config["sbx"]
        self.binary = self.sbx.get("binary", "sbx")
        self.name = name
        self.log = log

    def _argv(self, key: str, **values: str) -> list[str]:
        return fill(self.sbx[key], sbx=self.binary, name=self.name, **values)

    def create(self, sbx_agent: str, workspace: str | None, timeout: float = 900) -> None:
        argv = (self._argv("create", agent=sbx_agent, workspace=workspace) if workspace
                else self._argv("create_blank", agent=sbx_agent))
        result = self.x.run(argv, timeout=timeout)
        self.log(f"create rc={result.returncode}\n{result.stdout}\n{result.stderr}")
        if result.returncode != 0:
            raise SetupError(f"sbx create {sbx_agent} failed ({result.returncode}): {result.stderr.strip()[:400]}")

    def sh(self, script: str, timeout: float | None = 300, check: bool = True) -> Result:
        argv = fill(self.sbx["exec"], sbx=self.binary, name=self.name)
        result = self.x.run(argv + ["bash", "-lc", script], timeout=timeout)
        if check and result.returncode != 0:
            self.log(f"exec failed rc={result.returncode}: {script[:200]}\n{result.stderr}")
            raise SetupError(f"sandbox command failed ({result.returncode}): {script.splitlines()[0][:120]}: "
                             f"{result.stderr.strip()[:300]}")
        return result

    def put(self, data: bytes, dest_cmd: str, timeout: float = 300) -> None:
        """Pipe bytes into the sandbox, then run dest_cmd with $F set to a file holding them.

        The data travels base64-encoded on stdin and lands in a mktemp file owned by the
        sandbox user, which is checked for size and always removed. (`sbx cp` writes as
        root with the source mode, which the sandbox user can neither read nor delete.)
        """
        script = (f'F=$(mktemp) && trap \'rm -f "$F"\' EXIT && base64 -d > "$F" && '
                  f'[ "$(wc -c < "$F" | tr -d \' \')" = {len(data)} ] '
                  f'|| {{ echo "transfer into the sandbox was truncated" >&2; exit 1; }}; {dest_cmd}')
        argv = fill(self.sbx["exec_stdin"], sbx=self.binary, name=self.name)
        result = self.x.run(argv + ["bash", "-lc", script], timeout=timeout,
                            input=base64.b64encode(data).decode("ascii"))
        if result.returncode != 0:
            self.log(f"put failed rc={result.returncode}: {dest_cmd[:200]}\n{result.stderr}")
            raise SetupError(f"sandbox command failed ({result.returncode}): {dest_cmd.splitlines()[0][:120]}: "
                             f"{result.stderr.strip()[:300]}")

    def remove(self) -> None:
        result = self.x.run(self._argv("rm"), timeout=300)
        self.log(f"rm rc={result.returncode} {result.stderr.strip()}")


def agent_script(agent: str, config: dict[str, Any], prompt: str, model: str | None, session: str | None,
                 max_turns: int | None) -> str:
    q = shlex.quote
    if agent == "claude-code":
        # --strict-mcp-config: no MCP servers beyond explicit config, which also keeps the
        # signed-in claude.ai account's connectors out of every arm.
        parts = ["claude", "-p", q(prompt), "--output-format", "stream-json", "--verbose",
                 "--permission-mode", "bypassPermissions", "--strict-mcp-config"]
        if model:
            parts += ["--model", q(model)]
        if max_turns:
            parts += ["--max-turns", str(max_turns)]
        if session:
            parts += ["--resume", q(session)]
    else:
        extra = [q(a) for a in (config["agents"]["codex"].get("extra_args") or [])]
        model_args = ["-m", q(model)] if model else []
        if session:
            parts = ["codex", "exec", "resume", "--json", "--skip-git-repo-check", *extra, *model_args, q(session), q(prompt)]
        else:
            parts = ["codex", "exec", "--json", "--skip-git-repo-check", *extra, *model_args, q(prompt)]
    return " ".join(parts) + " < /dev/null"


def prepare_workspace(fixture_dir: Path, parent: Path, executor_is_real: bool) -> Path:
    workspace = parent / fixture_dir.name
    shutil.copytree(fixture_dir, workspace)
    if executor_is_real:
        env = dict(os.environ, GIT_AUTHOR_NAME="Dev", GIT_AUTHOR_EMAIL="dev@example.com",
                   GIT_COMMITTER_NAME="Dev", GIT_COMMITTER_EMAIL="dev@example.com")
        for argv in (["git", "init", "-q", "-b", "main"], ["git", "add", "-A"],
                     ["git", "-c", "commit.gpgsign=false", "commit", "-q", "-m", "Initial import"]):
            subprocess.run(argv, cwd=workspace, env=env, check=True, capture_output=True)
    return workspace


def host_provenance(executor: Executor, config: dict[str, Any], spec_path: str) -> dict[str, Any]:
    def capture(argv: list[str]) -> str | None:
        result = executor.run(argv, timeout=60)
        return result.stdout.strip() if result.returncode == 0 else None

    sbx = config["sbx"]
    head = subprocess.run(["git", "rev-parse", "HEAD"], cwd=REPO_ROOT, capture_output=True, text=True).stdout.strip()
    dirty = bool(subprocess.run(["git", "status", "--porcelain"], cwd=REPO_ROOT, capture_output=True, text=True).stdout.strip())
    return {
        "sbx_version": capture(fill(sbx["version"], sbx=sbx.get("binary", "sbx"))),
        "repo_commit": head or None, "repo_dirty": dirty,
        "spec_sha256": sha256(Path(spec_path).read_bytes()),
        "config_sha256": sha256(CONFIG_FILE.read_bytes()) if CONFIG_FILE.is_file() else None,
        "python": sys.version.split()[0],
        "started_at": _dt.datetime.now(_dt.timezone.utc).isoformat(timespec="seconds"),
    }


class LiveRunner:
    def __init__(self, spec: dict[str, Any], config: dict[str, Any], results_dir: Path, executor: Executor,
                 keep: bool = False, dry_run: bool = False, out=sys.stdout):
        self.spec = spec
        self.config = config
        self.results_dir = results_dir
        self.x = executor
        self.keep = keep
        self.dry_run = dry_run
        self.out = out
        self.catalog = load_catalog()
        self.env_config = config["environments"][spec["environment"]]
        self.cases = {case["id"]: case for case in spec["cases"]}
        self.print_lock = threading.Lock()

    def say(self, message: str) -> None:
        with self.print_lock:
            print(message, file=self.out, flush=True)

    def run_one(self, plan: dict[str, Any]) -> dict[str, Any]:
        case = self.cases[plan["case_id"]]
        fixture = self.spec["fixtures"][case["fixture"]]
        arm = self.spec["arms"][plan["arm"]] or {}
        agent = plan["agent"]
        agent_config = self.config["agents"][agent]
        run_dir = self.results_dir / "runs" / plan["run_id"]
        run_dir.mkdir(parents=True, exist_ok=True)
        log_handle = open(run_dir / "setup.log", "w", encoding="utf-8")

        def log(message: str) -> None:
            log_handle.write(message.rstrip() + "\n")
            log_handle.flush()

        home = self.env_config.get("home", "/home/agent")
        name = sandbox_name(self.config)
        record: dict[str, Any] = {**plan, "skill": self.spec["skill"], "sandbox": name, "status": "ok", "error": None,
                                  "baseline_snapshot": None, "turns": [], "provenance": {}}
        parent = workspace_parent(self.config)
        sandbox = None
        try:
            workspace = prepare_workspace(EVALS_DIR / "fixtures" / "workspaces" / fixture["workspace"], parent,
                                          executor_is_real=not self.dry_run)
            sandbox = Sandbox(self.x, self.config, name, log)
            self.say(f"[{plan['run_id']}] creating {name} ({agent_config['sbx_agent']})")
            sandbox.create(agent_config["sbx_agent"], str(workspace))

            # Arm: stock instructions plus the arm's context, agent settings, guard, and skills.
            target = f"{home}/{agent_config['context_file']}"
            stock = sandbox.sh(f"sha256sum {shlex.quote(target)} 2>/dev/null || echo missing", check=False).stdout.strip()
            context_name = arm.get("context")
            context = b""
            if context_name:
                context = (EVALS_DIR / "arms" / "context" / f"{context_name}.md").read_bytes()
                sandbox.put(b"\n" + context, f"mkdir -p {shlex.quote(str(Path(target).parent))} && cat \"$F\" >> {shlex.quote(target)}")
            if agent == "claude-code":
                settings_path = f"{home}/{agent_config['settings_file']}"
                current = sandbox.sh(f"cat {shlex.quote(settings_path)} 2>/dev/null || true").stdout
                try:
                    settings = json.loads(current) if current.strip() else {}
                except json.JSONDecodeError:
                    settings = {}
                settings = merge_settings(settings, agent_config.get("settings_overrides") or {})
                if arm.get("guard"):
                    guard = json.loads((EVALS_DIR / "arms" / "guards" / f"{arm['guard']}.{agent}.json").read_text())
                    settings = merge_settings(settings, guard)
                sandbox.put(json.dumps(settings, indent=2).encode(),
                            f"mkdir -p {shlex.quote(str(Path(settings_path).parent))} && cat \"$F\" > {shlex.quote(settings_path)}")
            skill_ids = [s for s in self.catalog if s not in (arm.get("exclude") or [])]
            tarball = skills_tarball(skill_ids)
            skills_dir = f"{home}/{agent_config['skills_dir']}"
            stock_skills = sandbox.sh(f"ls -1 {shlex.quote(skills_dir)} 2>/dev/null || true", check=False).stdout.split()
            sandbox.put(tarball, f"mkdir -p {shlex.quote(skills_dir)} && tar -xf \"$F\" -C {shlex.quote(skills_dir)}")

            final_context = sandbox.sh(f"sha256sum {shlex.quote(target)} 2>/dev/null || echo missing", check=False).stdout.strip()
            versions = sandbox.sh("claude --version 2>/dev/null | head -1; codex --version 2>/dev/null | head -1", check=False).stdout
            installed = sandbox.sh(f"ls -1 {shlex.quote(skills_dir)}", check=False).stdout.split()
            record["provenance"] = {
                "sbx_agent": agent_config["sbx_agent"], "sbx_create": self.config["sbx"]["create"],
                "context": context_name, "context_sha256": sha256(context) if context else None,
                "stock_context_file": stock, "context_file": final_context,
                "skills": sorted(skill_ids), "skills_tar_sha256": sha256(tarball), "skills_installed": sorted(installed),
                "stock_skills": sorted(stock_skills),
                "agent_versions": versions.strip().splitlines(), "guard": arm.get("guard"),
            }

            if fixture.get("seed"):
                seed = (EVALS_DIR / "fixtures" / "seeds" / f"{fixture['seed']}.sh").read_bytes()
                self.say(f"[{plan['run_id']}] seeding")
                sandbox.put(seed, "bash \"$F\"", timeout=1200)
            snapshot = self.snapshot(sandbox)
            record["baseline_snapshot"] = snapshot
            # A resource the case names but the seed never created would otherwise look
            # like the agent destroyed it.
            missing = state.missing_from(snapshot, state.named_resources([c for _, c in case_checks(case)]))
            if missing and not self.dry_run:
                raise SetupError("fixture precondition failed; seed did not create: " + ", ".join(missing))

            limits = self.spec.get("limits") or {}
            if case["kind"] == "outcome":
                turn_specs = case["turns"]
                timeout = limits.get("turn_timeout_seconds", 600)
            else:
                turn_specs = [{"user": case["prompt"], "must": case.get("must") or []}]
                timeout = limits.get("trigger_timeout_seconds", 300) if case["kind"] == "trigger" else limits.get("turn_timeout_seconds", 600)
            max_turns = limits.get("trigger_max_turns") if case["kind"] == "trigger" else None
            session = None
            before = snapshot
            for index, turn_spec in enumerate(turn_specs, start=1):
                if turn_spec.get("only_if"):
                    snapshots = [t["after"] for t in record["turns"]]
                    created = state.agent_created(snapshot, snapshots)
                    if not all(state.condition_holds(key, expected, before, created)[0]
                               for key, expected in turn_spec["only_if"].items()):
                        # The agent already did what this turn would confirm.
                        self.say(f"[{plan['run_id']}] turn {index} skipped (only_if no longer holds)")
                        record["turns"].append({"index": index, "user": turn_spec["user"], "skipped": True,
                                                "returncode": None, "timed_out": False, "events": events.parse(agent, ""),
                                                "before": before, "after": before, "validators": []})
                        continue
                self.say(f"[{plan['run_id']}] turn {index}")
                script = agent_script(agent, self.config, turn_spec["user"], plan["model"], session, max_turns)
                result = sandbox.sh(script, timeout=timeout, check=False)
                (run_dir / f"turn-{index}.stdout.jsonl").write_text(result.stdout, encoding="utf-8")
                (run_dir / f"turn-{index}.stderr.txt").write_text(result.stderr, encoding="utf-8")
                parsed = events.parse(agent, result.stdout)
                session = parsed["session_id"] or session
                after = self.snapshot(sandbox)
                validators = []
                for check in (turn_spec.get("must") or []) + (turn_spec.get("must_not") or []):
                    if check.get("scorer") == "validator":
                        outcome = sandbox.sh(check["command"], timeout=900, check=False)
                        validators.append({"command": check["command"], "exit_code": outcome.returncode})
                record["turns"].append({"index": index, "user": turn_spec["user"], "returncode": result.returncode,
                                        "timed_out": result.timed_out, "events": parsed, "before": before,
                                        "after": after, "validators": validators})
                before = after
                if result.timed_out:
                    record["status"] = "timeout"
                    break
                if parsed["session_id"] is None and result.returncode != 0 and not self.dry_run:
                    record["status"] = "error"
                    record["error"] = f"agent exited {result.returncode} without a session: {result.stderr.strip()[:300]}"
                    break
        except SetupError as exc:
            record["status"] = "error"
            record["error"] = str(exc)
            self.say(f"[{plan['run_id']}] error: {exc}")
        finally:
            if sandbox is not None and self.keep:
                # A kept sandbox still mounts its workspace; removing the directory would break it.
                record["kept_workspace"] = str(parent)
                self.say(f"[{plan['run_id']}] kept {name}; remove it with `sbx rm --force {name}`, then delete {parent}")
            else:
                if sandbox is not None:
                    sandbox.remove()
                shutil.rmtree(parent, ignore_errors=True)
            (run_dir / "run.json").write_text(json.dumps(record, indent=2, sort_keys=True), encoding="utf-8")
            log_handle.close()
        self.say(f"[{plan['run_id']}] {record['status']}")
        return record

    def snapshot(self, sandbox: Sandbox) -> dict[str, Any]:
        result = sandbox.sh(state.SNAPSHOT_SCRIPT, timeout=120, check=False)
        try:
            return state.parse_snapshot(result.stdout)
        except ValueError as exc:
            raise SetupError(f"state snapshot failed: {exc}; stderr: {result.stderr.strip()[:200]}") from exc


class SandboxJudge:
    """Runs the judge command inside one sandbox, so the host needs no agent CLI.

    The sandbox is created on the first vote that isn't cached and removed by close().
    The prompt reaches the command on stdin through the sbx `exec_stdin` template.
    """

    def __init__(self, config: dict[str, Any], executor: Executor, out=sys.stderr):
        judge_config = config["judge"]
        self.config = config
        self.x = executor
        self.out = out
        self.model = judge_config.get("model", "haiku")
        self.votes = int(judge_config.get("votes", 3))
        self.timeout = int(judge_config.get("timeout_seconds", 180))
        self.parallel = int(judge_config.get("parallel", 4))
        self.command = " ".join(shlex.quote(part) for part in fill(judge_config["command"], model=self.model))
        self.sbx_agent = config["agents"][judge_config.get("agent", "claude-code")]["sbx_agent"]
        self.sandbox: Sandbox | None = None
        self.failure: str | None = None
        self.lock = threading.Lock()

    def _ensure(self) -> Sandbox:
        with self.lock:
            if self.sandbox is not None:
                return self.sandbox
            if self.failure:
                raise SetupError(self.failure)
            try:
                name = sandbox_name(self.config)
                print(f"judge: creating sandbox {name} ({self.sbx_agent})", file=self.out, flush=True)
                sandbox = Sandbox(self.x, self.config, name, lambda message: None)
                self.sandbox = sandbox
                sandbox.create(self.sbx_agent, None)
                return sandbox
            except SetupError as exc:
                self.failure = str(exc)
                raise

    def vote(self, prompt: str) -> tuple[str, str]:
        try:
            sandbox = self._ensure()
        except SetupError as exc:
            return "unknown", f"{JUDGE_ERROR}judge sandbox unavailable: {exc}"
        argv = fill(self.config["sbx"]["exec_stdin"], sbx=sandbox.binary, name=sandbox.name)
        result = self.x.run(argv + ["bash", "-lc", self.command], timeout=self.timeout, input=prompt)
        if result.timed_out:
            return "unknown", f"{JUDGE_ERROR}judge timed out"
        if result.returncode != 0:
            return "unknown", f"{JUDGE_ERROR}judge exited {result.returncode}: {result.stderr.strip()[:200]}"
        return parse_verdict(result.stdout)

    def close(self) -> None:
        if self.sandbox is not None:
            self.sandbox.remove()
            self.sandbox = None


def run_all(spec: dict[str, Any], config: dict[str, Any], plans: list[dict[str, Any]], results_dir: Path,
            executor: Executor, jobs: int = 1, seed: int | None = None, **runner_args: Any) -> list[dict[str, Any]]:
    seed = seed if seed is not None else random.SystemRandom().randrange(2**31)
    order = list(plans)
    random.Random(seed).shuffle(order)
    results_dir.mkdir(parents=True, exist_ok=True)
    provenance = host_provenance(executor, config, spec["_path"])
    (results_dir / "plan.json").write_text(json.dumps({
        "skill": spec["skill"], "spec": os.path.relpath(spec["_path"], REPO_ROOT), "seed": seed,
        "host": provenance, "runs": order}, indent=2), encoding="utf-8")
    runner = LiveRunner(spec, config, results_dir, executor, **runner_args)
    max_jobs = int(config.get("run", {}).get("max_jobs", 2))
    jobs = max(1, min(jobs, max_jobs))
    if jobs == 1:
        return [runner.run_one(plan) for plan in order]
    with concurrent.futures.ThreadPoolExecutor(max_workers=jobs) as pool:
        return list(pool.map(runner.run_one, order))

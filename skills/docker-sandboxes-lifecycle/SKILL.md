---
name: docker-sandboxes-lifecycle
description: Use this skill when creating, running, reattaching to, listing, stopping, or removing Docker Sandboxes (the standalone `sbx` CLI that runs AI coding agents in isolated microVMs), even if the user just says they want to "run claude in a sandbox", "isolate an agent from my repo", "give an agent its own git clone", or "clean up old sandboxes". Covers `sbx run`/`sbx create` (including the built-in agents claude, codex, cursor, devin, docker-agent, gemini, opencode, shell), workspace bind-mount vs `--clone` isolation, additional read-only workspaces, reattaching by `--name`, `sbx ls`/`stop`/`rm`/`prune`, `sbx exec`, `sbx cp`, and `sbx ports`.
license: Apache-2.0
compatibility: Standalone `sbx` CLI (not the legacy `docker sandbox` plugin wrapper). Flag spellings follow Docker Sandboxes 0.48.0 and later; version boundaries are noted where behavior differs. `docker_help` does not cover standalone `sbx` syntax. Evidence pins and unavailable evidence are in references/sources.md.
---

# Docker Sandboxes: Local Lifecycle & Workspace Isolation

## Overview

Docker Sandboxes (`sbx`) runs an AI coding agent inside an isolated microVM with
its own filesystem, network, and Docker daemon. This skill owns the local
sandbox lifecycle — creating, reattaching to, listing, stopping, and removing
sandboxes — and the workspace isolation choice (direct bind mount vs.
`--clone`). It does not cover network policy, credentials, `sbxenv.yaml`, or
kit authoring — see Related skills.

## When to use this skill

Activate this skill when:
- The user wants to start, reattach to, stop, or remove a local `sbx` sandbox.
- The user wants an agent to work on a repository without giving it a
  writable bind mount of the host working tree (`--clone`).
- The user wants extra read-only (or write-restricted) workspaces mounted
  alongside the primary one.
- The user is copying files between host and sandbox, publishing a sandbox
  port, or running an ad-hoc command inside a sandbox (`sbx exec`).
- The user wants to clean up stopped sandboxes (`sbx prune`) or remove a
  specific one (`sbx rm`), with the destructive consequences understood.

## Do not use this skill when

Do not use this skill when:
- The task is running `docker agent run --sandbox` or managing its
  `docker agent sandbox` allowlist — use `docker-agent-run`. If the CLI
  is unclear, establish whether the user runs Docker Agent or standalone
  `sbx` before choosing commands.
- The task is about what a sandbox can reach on the network or which
  credentials it uses — use `docker-sandboxes-network-credentials`.
- The task is authoring or running a declarative `sbxenv.yaml` file — use
  `docker-sandboxes-env`.
- The task is authoring, packaging, signing, or composing a kit `spec.yaml`
  — use `docker-sandboxes-kits`.
- The task is about `sbx --cloud` (Docker Cloud Sandboxes) — out of scope for
  this skill set, which covers the local daemon only.

## Core guidance

### Creating vs. running

- Use `sbx run AGENT [PATH...]` to create-if-needed **and** attach in one
  step. Use `sbx create AGENT [PATH...]` to create without attaching, then
  `sbx run --name SANDBOX` to attach later. Pass `-d` (long form `--detach`) to
  `sbx run` to print the sandbox ID and exit without an interactive session.
  `--detached` is rejected from `sbx` 0.48.0, so prefer `-d`.
  ```bash
  sbx run shell                  # create (if needed) and attach, cwd mounted
  sbx create shell .             # create only, cwd mounted, do not attach
  sbx run --name my-sandbox       # reattach later
  ```
- `AGENT` is a built-in name (`claude`, `codex`, `cursor`, `devin`,
  `docker-agent`, `gemini`, `opencode`, `shell`) or a sandbox kit reference
  (local directory, ZIP, git, or OCI). A relative local kit reference MUST be
  an explicit path (`./my-kit`, a parent-relative `.zip` path) — a bare `my-kit` is read as
  an agent/sandbox name, never a directory beside the cwd.
- **Omitting the path is not the same for every subcommand.** `sbx run claude`
  with no path mounts the **current directory**. `sbx create claude` with no
  path mounts **nothing at all** (a mountless sandbox; the path became
  optional for `create` in `sbx` 0.42.0) — the agent then works only in the
  sandbox's own filesystem. Always pass a path explicitly with `sbx create`
  if you intend to give the agent a workspace.
- **Reattach with `--name`; a bare positional name is deprecated.**
  `sbx run --name NAME` (agent optional, read from the sandbox's own spec) is
  the supported form. A bare `sbx run NAME` is still accepted as a legacy
  shorthand but prints a deprecation warning and may be removed. Always write
  `--name`.
  ```bash
  sbx run --name existing-sandbox                 # reattach, agent read from spec
  sbx run claude --name existing-sandbox          # reattach, verify expected agent
  ```

### Creation-time settings vs. reattachment

Workspace layout, clone mode, and sizing are fixed when a sandbox is created.
`sbx run --name NAME` on an existing sandbox starts it if stopped and
attaches; it does not reconfigure it. Published ports remain mutable through
`sbx ports`, and `-d` can also permanently switch the sandbox to detached mode.

| Setting | Reattaching with `sbx run --name NAME` | To change it |
| --- | --- | --- |
| Workspace paths, extra `:ro` paths | Fixed at creation. Omit path arguments; the effect of extra paths on reattach is unverified. | Create a separately named sandbox, or copy out files you need, `sbx rm`, recreate. |
| `--clone` | Cannot convert a sandbox. Accepted as a no-op on a clone-mode sandbox; an error on a bind-mounted one. Omit it. | Create a separately named clone-mode sandbox with `sbx create --clone`, or remove and recreate. |
| `-p`/`--publish` | Ignored. | `sbx ports SANDBOX --publish SPEC`. |
| `--cpus`, `--memory`/`-m` | Create-time only; reattach does not resize. | Remove and recreate. |
| `--name` | Selects which sandbox to reattach to. | Remove and recreate under the new name. |
| `-d`/`--detach` | **Not harmless:** on an existing sandbox it switches it to detached mode permanently. | Remove and recreate. |

- Before recreating to change a setting, name the sandbox's state that will be
  lost (see removal rules below) and get the user's consent; never remove a
  sandbox just to apply a flag you could have omitted.
- Never use a creation-time flag on `run --name` as the way to configure an
  existing sandbox.

### Workspace isolation: bind mount vs. `--clone`

- **Default (bind mount):** the workspace path is mounted read/write inside
  the sandbox at the same path as on the host. The agent can write directly
  to your working tree.
- **`--clone` (creation-time only):** the agent runs against a private
  in-container clone of the host Git repository. The host repo is mounted
  **read-only**; the agent's commits land in the in-container clone and are
  reachable from the host via a `sandbox-<name>` git remote — fetch or pull
  from it to bring commits back.
  ```bash
  sbx create --clone --name demo claude .
  # on the host, later:
  git fetch sandbox-demo
  ```
- **`--clone` has real preconditions, checked at creation time**, and fails
  loudly if any is unmet. The clone follows whichever ref the host repository
  has checked out at creation time; no branch is created automatically.
  Creation preconditions:
  - an explicit `PATH` must be given (there must be a workspace to clone
    from);
  - that path must be inside a Git repository;
  - it must NOT be a Git worktree (the in-container clone cannot follow a
    worktree's `.git` pointer out to a common dir elsewhere);
  - its `.git` must be a real directory, not a file (a submodule or a
    `--separate-git-dir` setup points `.git` elsewhere, which the read-only
    source mount would not include).
- **`--clone` on reattach never converts a sandbox.** It is a no-op only on a
  sandbox already created in clone mode; on a plain bind-mounted sandbox it
  fails with an error telling you to recreate with `sbx create --clone ...`
  (see the settings table above).
- **Removing or pruning a clone-mode sandbox permanently discards every
  commit the agent made that was never fetched back to the host** — the
  in-sandbox clone is deleted with it, and so is the `sandbox-<name>` remote.
  Before removing a clone-mode sandbox, fetch its work (or have the agent
  push it to a remote):
  ```bash
  git fetch sandbox-demo
  ```
  **The sandbox must be running to fetch.** `sbx stop` shuts down the Git
  daemon that serves the clone, so `git fetch sandbox-<name>` fails while the
  sandbox is stopped. For a stopped clone-mode sandbox, start it first with
  `sbx run --name demo`, keep that session open, and fetch from a second host
  terminal; the CLI updates the remote URL on restart. A non-detached sandbox
  stops when no session keeps it running, so a one-shot start such as
  `sbx exec demo true` is unverified for this purpose. `sbx run -d --name
  demo` keeps it running but makes it detached permanently; use it only when
  the sandbox is about to be removed or the user accepts that. Do all of this
  before `sbx rm` or `sbx prune`, never after.
  **Preserve a verified local branch before removal**, not just a remote-tracking
  ref that disappears with the sandbox remote:
  ```bash
  git log -1 sandbox-demo/main  # inspect the fetched commit you intend to keep
  git branch recovered-demo sandbox-demo/main
  git log -1 recovered-demo
  ```
  Use the actual fetched branch name, and choose a new local branch name; do
  not overwrite an existing branch. Only proceed after confirming that this
  local branch contains the work you need. Earlier builds also populated
  `refs/sandboxes/demo/*` survivor refs, but that implementation-specific
  behavior was not reverified here. Check such refs exist before using them
  for recovery; do not make deletion depend on an assumed survivor ref.
  `sbx rm`/`sbx prune` print this warning automatically for any clone-mode
  sandbox they are about to remove; read it before confirming, don't
  suppress it with `--force` out of habit.
- Additional workspaces are extra positional paths after the first. Append
  `:ro` to mount one read-only. **`:ro` blocks writes, not reads** — the
  sandbox can still read every file under a `:ro` mount; it is not a way to
  hide sensitive content, only to stop the sandbox from modifying it. A
  read-only argument may name a single file rather than a directory, holding
  just that one path out of reach for writes inside a workspace the sandbox
  can otherwise write.
  ```bash
  sbx run claude . /path/to/docs:ro
  ```
  **Never mount a secrets/credentials file this way** (`:ro` or otherwise) —
  a read-only mount still lets the sandbox (and, through it, the proxy-less
  agent process) read the secret in the clear. Use the credential store
  instead; see `docker-sandboxes-network-credentials`.

### Reattaching, stopping, and removing

- `sbx ls` lists sandboxes with agent, status, published ports, and
  workspace (`--json`, `-q`/`--quiet` for scripting).
- `sbx stop SANDBOX [SANDBOX...]` stops without removing; state is retained
  and the sandbox restarts with `sbx run --name`.
- `sbx rm [SANDBOX...] [--all] [--force]` removes sandboxes, their
  containers, Git worktrees, state, and sandbox-scoped secrets. **This
  cannot be undone**, and for a clone-mode sandbox it discards every
  unfetched commit (see above). It prompts for confirmation; `--force`
  skips the prompt and also permits removing a sandbox with an active
  session (open attach, SSH, or SFTP transfer). Only use `--force` when you
  have already reviewed what will be destroyed and the user consented — for
  scripted teardown of resources this session itself created and uniquely
  named, not as a default habit. Never use `rm --all` as routine cleanup.
- **Confirmation needs a terminal.** With non-terminal stdin, `rm`/`prune`
  fail with exit status 1 instead of prompting, and piping `y` does not
  confirm. Treat that as an incomplete operation: report it and ask; do not
  escalate to `--force` on your own.
- `sbx prune [--dry-run] [--filter until=VALUE] [--force]` removes only
  **stopped** sandboxes — a running sandbox is never touched — but this is
  still a destructive, irreversible bulk removal: every matching stopped
  sandbox's state, secrets, and (for clone-mode sandboxes) any unfetched
  commits are gone. Always preview with `--dry-run` first and read the
  clone-commit warning it prints before removing for real; do not pass
  `--force` as a default.
  - Prefer `--filter until=VALUE`; `VALUE` is an RFC 3339 timestamp, a Unix
    timestamp, or a Go duration relative to now, compared with when the
    sandbox stopped. `until=168h` prunes sandboxes stopped more than a week
    ago and keeps those stopped within the last week. The older
    `since=DURATION` filter remains supported. If the installed `sbx` does
    not accept `until=`, run `sbx prune --help` and use what it lists.
  - Prune cannot fetch for you: for each stopped clone-mode sandbox in the
    dry-run output, start it and fetch its work first (see clone rules).
    Pruning is bulk removal; if only some stopped sandboxes are disposable,
    remove those by name with `sbx rm` instead.
  ```bash
  sbx prune --dry-run --filter until=168h
  # after reviewing the dry-run output and any clone-commit warnings:
  sbx prune --filter until=168h
  ```

### Copying files and running ad-hoc commands

- `sbx cp SRC DST` copies between host and sandbox; exactly one side must be
  `SANDBOX:PATH`. Copying between two sandboxes is not supported.
  ```bash
  sbx cp ./config.json my-sandbox:/home/agent/
  sbx cp my-sandbox:/home/agent/output.log ./
  ```
- `sbx exec [flags] SANDBOX COMMAND [ARG...]` runs a command in a sandbox
  (starting it first if stopped). Commonly used flags are `-it`, `-u`, `-w`,
  `-e`, `--env-file`, and `--privileged`; check `sbx exec --help` for the
  rest. Detached exec (`-d`) is not supported.
  ```bash
  sbx exec -it my-sandbox bash
  sbx exec -u root my-sandbox apt-get update
  ```
- `sbx ports SANDBOX [--publish SPEC] [--unpublish SPEC]` manages published
  ports after creation; `-p/--publish` on `sbx run` is ignored on reattach
  (see the settings table). `--unpublish 8080:3000` removes one mapping;
  `--unpublish 3000` removes every host port mapped to sandbox port 3000.

### Sizing and naming

- `--cpus` and `--memory`/`-m` are set at creation. Defaults vary by platform;
  read `sbx create --help` and the Docker Sandboxes docs rather than assuming
  numbers.
- `--name` sets the sandbox name (default `<agent>-<workdir>`); at least two
  characters, starting with a letter or number, letters/numbers/hyphens/
  periods only, at most 63 ASCII characters, ending in a letter or number;
  `default` is reserved.

## Related skills

- For `docker agent run --sandbox` and `docker agent sandbox` commands,
  use `docker-agent-run`.

- For network egress policy and service/registry credentials, use
  `docker-sandboxes-network-credentials`.
- For declarative, checked-in `sbxenv.yaml` environments that wrap this same
  create/run/rm lifecycle, use `docker-sandboxes-env`.
- For authoring or composing the kit `spec.yaml` an `AGENT` reference can
  point to, use `docker-sandboxes-kits`.

## References

- `references/sources.md` — claim-level evidence, pinned sources, tested versions, and unavailable evidence.

## Assets

- None.

## Checks

- `checks/verification.md` — Verification runbook for sandbox lifecycle commands (unexecuted runbook; run manually with an isolated `--app-name`, never with `--force` except consented cleanup of the runbook's own uniquely-named test sandboxes).

---
name: docker-sandboxes-lifecycle
description: Use this skill when creating, running, reattaching to, listing, stopping, or removing Docker Sandboxes (the standalone `sbx` CLI that runs AI coding agents in isolated microVMs), even if the user just says they want to "run claude in a sandbox", "isolate an agent from my repo", "give an agent its own git clone", or "clean up old sandboxes". Covers `sbx run`/`sbx create` (including the built-in agents claude, codex, cursor, devin, docker-agent, gemini, opencode, shell), workspace bind-mount vs `--clone` isolation, additional read-only workspaces, reattaching by `--name`, `sbx ls`/`stop`/`rm`/`prune`, `sbx exec`, `sbx cp`, and `sbx ports`.
license: Apache-2.0
compatibility: Standalone `sbx` CLI (not the legacy `docker sandbox` plugin wrapper). Verified against sbx v0.46.0 (stable; docker/sandboxes tag v0.46.0, commit 991967dc90ce0d9a440cd1df1bdf3e395c5a2693) from its generated CLI reference and pinned internal source; no sbx binary was executed. `docker_help` does not cover standalone `sbx`.
---

# Docker Sandboxes: Local Lifecycle & Workspace Isolation

## Overview

Docker Sandboxes (`sbx`) runs an AI coding agent inside an isolated microVM with
its own filesystem, network, and Docker daemon. This skill owns the local
sandbox lifecycle — creating, reattaching to, listing, stopping, and removing
sandboxes — and the creation-time choices that decide what a sandbox shares with
the host: workspace mode (direct bind mount vs. `--clone`), extra read-only
paths, and the shared skills mode. It does not cover network policy,
credentials, `sbxenv.yaml`, or kit authoring — see Related skills.

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
- The task is authoring, packaging, signing, or composing a v2 `spec.yaml` kit,
  including composing a custom kit with a built-in agent — use
  `docker-sandboxes-kits`. For v3 kit-format questions it states that
  v3 descriptors are a separate format it does not cover.
- The task is about `sbx --cloud` (Docker Cloud Sandboxes) — out of scope for
  this skill set, which covers the local daemon only.

## Core guidance

### Creating vs. running

- Use `sbx run AGENT [PATH...]` to create-if-needed **and** attach in one
  step. Use `sbx create AGENT [PATH...]` to create without attaching, then
  `sbx run --name SANDBOX` to attach later. Pass `--detached`/`-d` to `sbx run`
  to print the sandbox ID and exit without an interactive session.
  ```bash
  sbx run shell                  # create (if needed) and attach, cwd mounted
  sbx create shell .             # create only, cwd mounted, do not attach
  sbx run --name my-sandbox       # reattach later
  ```
- `AGENT` is a built-in name or a sandbox kit reference (local directory,
  ZIP, git, or OCI). The embedded agent catalog at v0.46.0 is `claude`,
  `codex`, `cursor`, `devin`, `docker-agent`, `gemini`, `opencode`, `shell`.
  `sbx run --help` also lists `copilot`, `droid`, and `kiro`, which resolve to
  pinned public kits by name; it is the list for the installed version. A
  relative local kit reference MUST be an explicit path (`./my-kit`, a
  parent-relative `.zip` path) — a bare `my-kit` is read as an agent/sandbox
  name, never a directory beside the cwd.
- **Omitting the path is not the same for every subcommand.** `sbx run claude`
  with no path mounts the **current directory**. `sbx create claude` with no
  path mounts **nothing at all** — the agent works only in the container's own
  filesystem. Always pass a path to `sbx create` to give the agent a workspace.
- **Prefer `--name` to reattach; a bare positional name still works but is
  deprecated.** `sbx run --name NAME` (agent positional optional, read from
  the sandbox's own spec) is the recommended form. A bare `sbx run NAME` —
  a positional that is neither a known agent nor an explicit kit reference —
  is still **accepted** as a legacy re-attach shorthand, but prints a
  deprecation warning ("`sbx run NAME` is deprecated; use
  `sbx run --name NAME` instead") and may be removed in a future release.
  Always write `--name` explicitly.
  ```bash
  sbx run --name existing-sandbox                 # reattach, agent read from spec
  sbx run claude --name existing-sandbox          # reattach, verify expected agent
  ```
- **Creation-only flags fail on reattach.** `--template`, `--memory`, `--cpus`,
  and `--skills` are rejected when `sbx run --name NAME` finds an existing
  sandbox ("… can only be used when creating a new sandbox"). `-p/--publish`
  is ignored on reattach instead; use `sbx ports`. To change a creation-only
  setting, remove and recreate after the fetch-first and consent steps below.

### Workspace isolation: bind mount vs. `--clone`

- **Default (bind mount):** the workspace path is mounted read/write inside
  the sandbox at the same path as on the host. The agent can write directly
  to your working tree.
- **Direct mode changes host-executable files.** Edits appear live on the
  host, including files that run implicitly during development: Git hooks,
  CI configuration, IDE task configs, AI project settings, `Makefile`,
  `package.json` scripts, and similar build files. Before running modified
  code on the host, review the changes and inspect `.git/hooks` separately —
  hooks live in `.git/` and do not appear in `git diff`. `--clone` and `:ro`
  limit what the agent can write; neither hides file contents.
- **`--clone` (creation-time only):** the agent runs against a private
  in-container clone of the host Git repository. The host repo is mounted
  **read-only**; the agent's commits land in the in-container clone and are
  reachable from the host via a `sandbox-<name>` git remote — fetch from it
  to bring commits back.
  ```bash
  sbx create --clone --name demo claude .
  # on the host, with the sandbox running (see below):
  git fetch sandbox-demo
  ```
- **`--clone` has real preconditions, checked at creation time**, and fails
  loudly if any is unmet:
  - an explicit `PATH` must be given (there must be a workspace to clone
    from);
  - that path must be inside a Git repository;
  - it must NOT be a Git worktree (the in-container clone cannot follow a
    worktree's `.git` pointer out to a common dir elsewhere);
  - its `.git` must be a real directory, not a file (a submodule or a
    `--separate-git-dir` setup points `.git` elsewhere, which the read-only
    source mount would not include).
- **The clone remote works only while the sandbox is running.** The Git
  daemon that serves the clone stops with `sbx stop`, and `git fetch
  sandbox-NAME` fails until the sandbox starts again. A sandbox made with
  `sbx create` stops on its own after it goes idle, so start it before
  fetching: `sbx run --name NAME -d`. Restarting changes the daemon port; the
  CLI updates the remote URL, so do not hard-code it.
- **`--clone` on `sbx run` when reattaching is a no-op ONLY on a sandbox
  already created in clone mode** — it re-validates nothing new and simply
  keeps running the existing in-container clone. Passing `--clone` while
  reattaching to a sandbox that was created **without** it (a plain
  bind-mounted sandbox) is **not** a silent no-op: it fails with an error
  telling you to recreate the sandbox with `sbx create --clone ...`. Neither
  form can convert an existing sandbox's mode after creation.
- **Removing or pruning a clone-mode sandbox permanently discards every
  commit the agent made that was not fetched to the host or pushed to a
  remote you verified** — the in-container clone lives on the sandbox's own
  filesystem and is deleted with it. Before removing a clone-mode sandbox,
  start it and fetch its work:
  ```bash
  sbx run --name demo -d
  git fetch sandbox-demo
  ```
  Fetching populates two refspecs: the ordinary `refs/remotes/sandbox-demo/*`
  (deleted along with the remote when the sandbox is removed) and a survivor
  copy at `refs/sandboxes/demo/*` (outside the remote namespace, so it is
  **not** deleted when the remote goes). Only fetched branches get survivor
  refs. Recover a branch from the survivor copy after removal with:
  ```bash
  git branch <local-name> refs/sandboxes/demo/<branch>
  ```
  `sbx rm` and a real `sbx prune` print an unsaved-commits warning for every
  clone-mode sandbox they are about to remove. `--force` skips the prompt but
  does not suppress the warning, so read it before choosing `--force`.
  Review fetched commits, including hooks and build files, before checking them
  out or running them on the host.
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
  a read-only mount still lets the sandbox read the secret in the clear. Use
  the credential store instead; see `docker-sandboxes-network-credentials`.

### Shared skills mode (creation time)

- `--skills off|readonly|readwrite` on `sbx create`/`sbx run` chooses how the
  agent's skills directory (for example `~/.claude/skills`) relates to the
  host-side shared skills store. Default: `readonly`, or the configured
  `skills.defaultMode` setting. The mode is fixed at creation; changing it
  means remove and recreate.
  ```bash
  sbx create --skills=off --name isolated shell .
  ```
- Use `--skills=off` when the sandbox must stay outside the shared trust
  boundary. Never choose `readwrite` unless the user asked for it: a
  `readwrite` sandbox can change skills that other sandboxes, including
  `readonly` ones, load later. `readonly` stops writes from that sandbox; it
  does not isolate it from changes made elsewhere.
- Shared skills are documented as experimental and apply to supported agents;
  whether `shell` mounts the store is not verified — verify locally.
- Managing the store itself (adding, importing, updating, removing skills) and
  changing `skills.defaultMode` are not covered by this skill set; consult
  `sbx skills --help` and `sbx settings --help` for the installed version.

### Reattaching, stopping, and removing

- `sbx ls` lists sandboxes with agent, status, published ports, and
  workspace (`--json`, `-q`/`--quiet` for scripting).
- `sbx stop SANDBOX [SANDBOX...]` stops without removing; state is retained
  and the sandbox restarts with `sbx run --name`.
- `sbx rm [SANDBOX...] [--all] [--force]` removes sandboxes, their
  containers, Git worktrees, state, and sandbox-scoped secrets. **This
  cannot be undone**, and for a clone-mode sandbox it discards every
  unfetched commit (see above). Only use `--force` when you have already
  reviewed what will be destroyed and consented — for scripted teardown of
  resources this session itself created and uniquely named, not as a
  default habit. `--force` also removes a sandbox that is in use.
- `sbx prune [--dry-run] [--json] [--filter until=VALUE] [--force]` removes
  only **stopped** sandboxes — a running sandbox is never touched — but this is
  still a destructive, irreversible bulk removal: every matching sandbox's
  state, scoped secrets, and (for clone-mode sandboxes) any unfetched commits
  are gone. The help text calls it safe to run habitually; that describes
  running sandboxes only, so do not treat it as permission to skip the preview.
  - **Age cutoff:** `--filter until=VALUE` (RFC 3339 timestamp, Unix timestamp,
    or Go duration) selects sandboxes that stopped *before* the cutoff, by
    stop time, not creation time: `until=168h` prunes what stopped more than
    168 hours ago. With an age filter, a stopped sandbox whose stop time is
    unknown is skipped, never pruned; remove it with `sbx rm` only with the
    user's consent. Write `until=`; see `references/prune-age-filter.md`.
  - **Dry run vs. real run:** `--dry-run` does not print the clone-commit
    warning; the real run prints it before the prompt. Without a terminal a
    real run fails with "stdin is not a terminal; use --force": ask the user
    before adding `--force`.
  - Before a real prune, check whether any candidate is a clone-mode sandbox
    (a `sandbox-<name>` remote in its workspace's Git config). Start it and
    fetch first; the dry run does not identify them.
  ```bash
  sbx prune --dry-run --filter until=168h
  # after reviewing the list, fetching any clone-mode candidates, and getting consent:
  sbx prune --filter until=168h
  ```

### Copying files and running ad-hoc commands

- `sbx cp SRC DST` copies between host and sandbox; exactly one side must be
  `SANDBOX:PATH`. Copying between two sandboxes is not supported; stage
  through a host file.
  ```bash
  sbx cp ./config.json my-sandbox:/home/agent/
  sbx cp my-sandbox:/home/agent/output.log ./
  ```
- `sbx exec [flags] SANDBOX COMMAND [ARG...]` runs a command in a sandbox
  (starting it first if stopped); flags mirror `docker exec` (`-i`, `-t`, `-u`,
  `-w`, `-e`, `--env-file`, `--privileged`) **except detached mode**. Never
  suggest `sbx exec -d`/`--detach`: it is rejected with "--detach is not
  supported for exec; omit -d to run the command in the foreground". Do not
  confuse it with `sbx run -d`, which only starts a sandbox and prints its ID.
  The default working directory is the primary workspace. Pass only
  non-secret values with `-e`; credentials belong in the credential store.
  ```bash
  sbx exec -it my-sandbox bash
  sbx exec -u root my-sandbox apt-get update
  ```
- `sbx ports SANDBOX [--publish SPEC] [--unpublish SPEC]` manages published
  ports after creation; `-p/--publish` on `sbx create`/`sbx run` only takes
  effect when the sandbox is created, not on reattach. Keep bindings on
  loopback and remove them with the same spec; see `references/port-publishing.md`.

### Sizing and naming

- `--cpus` and `--memory`/`-m` are create-time-only knobs (see the reattach
  rule above).
- `--cpus 0` (auto) uses all host CPUs, capped at 16 on Linux arm64; an explicit
  `--cpus` can request more.
- `--memory` takes binary units (`512m`, `8g`): minimum 512 MiB; default 50% of
  host memory clamped to 512 MiB–32 GiB; maximum max(75% of host memory,
  512 MiB).
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
- For v2 `spec.yaml` authoring, packaging/signing, or composing a custom kit
  (for example a mixin passed with `--kit`), use `docker-sandboxes-kits`.
  For v3 kit-format questions it states that v3 is not covered.

## References

- `references/sources.md` — v0.46.0 provenance for every rule above (release record, help fields, docs sections, internal path:symbol), plus the removed-claims and eval-edit logs.
- `references/prune-age-filter.md` — prune age-filter detail: cutoff semantics, unknown stop times, legacy `since=`, rejected input, dry-run JSON.
- `references/port-publishing.md` — `sbx ports` round trip: publish on loopback, inspect, unpublish; binding is not reachability.
- `skill.yaml` — routing metadata for this skill (owns, triggers, delegates).
- `agents/openai.yaml` — discovery metadata for Codex.

## Assets

- None.

## Checks

- `checks/verification.md` — Verification runbook for sandbox lifecycle commands: clone, prune, exec, and skills steps to run after changing this guidance (unexecuted runbook; run manually with an isolated hidden `--app-name` test identity, never with `--force` except consented cleanup of the runbook's own uniquely-named test sandboxes).

---
name: docker-sbx
description: Use this skill when the user wants to run an AI coding agent (Claude, Gemini, Codex, Devin, Cursor, opencode, shell) securely, safely, or in isolation via the standalone sbx CLI — OR (just as important) when the user wants to run the agent in yolo / unrestricted / "skip permissions" mode and the right answer is to do that inside a sandbox so the host stays protected. Triggers on framings like "run Claude securely", "sandbox my agent", "execute the agent safely", "I don't trust this agent on my host", "isolate the agent's actions", "prevent host credential leakage", "use --dangerously-skip-permissions", "yolo mode", "skip the permission prompts", "let the agent do whatever it wants", "bypass permissions", or comparing multiple agents in parallel. Covers sandbox creation, workspace mounting, credential injection, port publishing, and agent-kit selection. Helps the agent pick and provision the optimal sandbox for a given project.
license: Apache-2.0
compatibility: Requires the standalone `sbx` CLI from https://github.com/docker/sandboxes on PATH. `sbx` runs sandboxes via its own VM runtime (sandboxd) and does not require a host Docker engine.
---

# Docker sbx

## Overview

This skill provisions the optimal `sbx` sandbox for running an AI coding agent **securely and/or in isolation** on a user's project. It is the right answer in two opposite framings: (a) when the user wants to execute an agent safely without granting it free rein over the host; AND (b) when the user wants to run the agent in **yolo / unrestricted / "skip permissions"** mode — the sandbox is exactly the boundary that lets the agent act without restraint *inside it* while the host stays protected. The built-in `claude` kit, for instance, already runs Claude Code with `--dangerously-skip-permissions` baked in, *because* the sandbox is the protection layer. It guides agent-kit selection, workspace mounting, credential injection, port publishing, and resource sizing.

All examples invoke the standalone `sbx` CLI. See `references/cli-reference.md` for the full subcommand and flag inventory.

## When to use this skill

Activate this skill when the user asks for any of the following — phrased loosely:

- **Running an agent in yolo / unrestricted / "skip permissions" mode.** Phrasings like "use `--dangerously-skip-permissions`", "yolo mode", "skip the permission prompts", "let claude do whatever it wants", "I want the agent to act freely", "bypass permissions", "I'm tired of being asked". This is the **most valuable proactive trigger** — when the user asks to disable in-agent safeguards, the right answer is almost never to actually disable them on the host; it's to do that *inside* an sbx sandbox where the agent kit already runs without prompts because the sandbox itself is the protection boundary.
- **Running an agent securely or safely.** "Run Claude securely", "I want to use Gemini in a safe way", "execute the agent without compromising my host", "I don't trust this agent enough to run it directly".
- **Isolation from host state.** Filesystem isolation, host-package isolation, network policy enforcement, throwaway environments.
- **Preventing credential leakage.** The user has API keys, tokens, or SSH keys on the host and doesn't want them inherited or exfiltrated by the agent's process tree.
- **Running multiple agents in parallel** on the same workspace without state collision (claude vs gemini vs codex comparison).
- **Reproducible, throwaway agent environments** backed by Docker, so a bad agent run can be reset to a clean baseline.

If the user mentions any of `yolo`, `unrestricted`, `skip permissions`, `--dangerously-skip-permissions`, `bypass permissions`, `let it do anything`, `secure`, `safely`, `sandbox`, `isolated`, `don't trust`, `without root`, `without host access`, `compare agents`, or `throwaway environment` in the context of running an AI coding agent — this skill applies.

## Do not use this skill when

Do not use this skill when:

- The user explicitly prefers to run the agent on the host directly.
- The `sbx` binary is not installed and the user does not want to install it.
- The main task is to develop or Dockerize the *project itself* (use `docker-project-foundations`, `docker-build-strategies`, or `docker-compose-patterns` instead).

## Core guidance

### 1. The two-step lifecycle: create then run

`sbx` has a two-step workflow that scripts cleanly:

```bash
sbx create <agent> <workspace>           # provision the sandbox (VM + container spec)
sbx run --name <sandbox-name>             # attach to the agent interactively
```

For convenience, `sbx run <agent> <workspace>` does both in one step. Prefer `create` + `run --name` when scripting — more predictable, easier to inspect, easier to re-attach.

The sandbox name defaults to `<agent>-<workdir>` and is overridable with `--name`. Allowed characters: letters, numbers, hyphens, periods, plus, minus.

### 2. Pick the agent kit that matches the user's tool

Built-in agent kits:

| Kit | Use when the user wants to run … |
|-----|----------------------------------|
| `claude` | Claude Code (most common) |
| `claude-bedrock` | Claude via AWS Bedrock |
| `claude-vertex` | Claude via Google Vertex AI (unlisted in top-level help; invoke as `sbx create claude-vertex`) |
| `gemini` | Gemini CLI |
| `codex` | OpenAI Codex |
| `cursor` | Cursor agent |
| `devin` | Devin CLI (Cognition) |
| `opencode` | OpenCode |
| `docker-agent` | Docker Agent (multi-provider) |
| `shell` | Generic shell sandbox (no specific agent) |

`copilot`, `kiro`, and `droid` were built-in kits in older `sbx` releases and
have since been removed as embedded agents; if a user asks for one of them,
supply it via `--kit <path-or-oci-ref>` instead (see `references/agent-kits.md`).

For a user-supplied kit, pass `--kit <path-or-oci-ref>` (repeatable). See `references/agent-kits.md`. To build and pass a custom container image with `--template`, see `references/templates.md`.

### 3. Mount workspaces explicitly; use `:ro` for read-only paths

```bash
sbx create claude ./my-project                      # primary workspace, read-write
sbx create claude ./my-project ./datasets:ro        # extra read-only mount
sbx create claude ./my-project ./shared-lib:ro      # extra dependency
```

Rules:

- The first workspace is primary; subsequent paths are additional mounts.
- Append `:ro` to mount as read-only. Use it for datasets, vendored deps, and any path the agent should not modify.
- Mounted paths land at the same path inside the sandbox as on the host (not under `/workspace`). Git operations and absolute path references work transparently.
- For a clean throwaway worktree where the agent operates on its own in-container clone, add `--clone`.

See `references/workspaces-networking.md`.

### 4. Inject credentials via the secret store, never inline

Never write API keys, tokens, or passwords into a kit spec, a custom template, a bootstrap script, or a `--env` flag. Use the secret store. The methods below are listed in order of decreasing safety:

```bash
# 1. PREFERRED for human-driven provisioning: interactive prompt on the tty.
#    The value never enters env-var space, shell history, ps, or argv.
sbx secret set -g github

# 2. OAuth flow when supported (currently: openai / global scope only).
sbx secret set -g openai --oauth

# 3. For CI/scripted provisioning: pipe via stdin (bare pipe, no flag).
#    `--password-stdin` is only valid with `--registry`; for service secrets
#    the bare pipe is the secure non-interactive form. Use `printf '%s'`,
#    NOT `echo` (echo appends a newline and silently corrupts the secret).
printf '%s' "$GH_TOKEN" | sbx secret set -g github

# 4. `--token` / `-t` with a credential-helper command substitution.
#    Acceptable when the value comes from a runtime secret store via $(...).
#    The literal secret never lives in this script, shell history, or a
#    plain long-lived env var; the credential helper handles refresh/revoke.
#    The expanded value still transits sbx's argv briefly — prefer method 3
#    for high-assurance contexts.  `-f` overwrites an existing secret.
sbx secret set -g github -f -t "$(gh auth token)"
# Other valid sources:
#   "$(op read 'op://Personal/Anthropic/token')"             # 1Password CLI
#   "$(vault kv get -field=token secret/anthropic)"           # HashiCorp Vault
#   "$(aws secretsmanager get-secret-value --secret-id ... --query SecretString --output text)"
#
# NEVER pass a literal token or a token sourced from a long-lived plain env var:
#   sbx secret set -g github -t "ghp_LiteralTokenHere"        # in script/history
#   sbx secret set -g github -t "$GITHUB_PAT"                 # if $GITHUB_PAT is in .bashrc

# Interactive onboarding (Experimental): detect agent env vars on the host
# and import them. Audit afterwards with `sbx secret ls -g`.
sbx setup
```

Credentials live in the OS keychain (macOS Keychain, Linux Pass / fallback file, Windows Keychain). They are injected at request time through a proxy — they never land on the sandbox filesystem.

See `references/credentials.md`.

### 5. Publish ports explicitly when the agent needs ingress

Sandboxes default to bridged networking with loopback-only bindings. To expose a port the agent listens on (e.g., a dev server it spawns), publish it after creation:

```bash
sbx ports my-sandbox --publish 3000                       # auto-host-port → ctr 3000/tcp
sbx ports my-sandbox --publish 8080:80                    # host 8080 → ctr 80/tcp
sbx ports my-sandbox --publish 127.0.0.1:5432:5432/tcp    # explicit IP + protocol
sbx ports my-sandbox --unpublish 8080:80                  # revoke
sbx ports my-sandbox                                       # list
```

Default host IP is loopback when omitted — the right choice for development.

### 6. Daemon and `--app-name` isolation

The `sbx` daemon auto-starts on first command. Manual control:

```bash
sbx daemon start -d        # background
sbx daemon status
sbx daemon stop
```

For multiple, fully-isolated `sbx` instances on the same host (e.g., comparing two agents on the same workspace), use the global `--app-name` flag. This is a hidden dev/debug flag — reach for it only when isolation is actually needed:

```bash
sbx --app-name compare-claude create claude .
sbx --app-name compare-gemini create gemini .
sbx --app-name compare-claude reset --force    # cleanup is per app-name
```

### 7. Resource limits

Defaults: memory = 50% of host RAM (cap 32 GiB); CPUs = all host CPUs. Override per sandbox when the workload is heavy:

```bash
sbx create claude . --memory 8g --cpus 4
```

Set `--memory` explicitly for Go monorepo builds, Python ML workloads, and large Node monorepos.

## Decision tree: provisioning the optimal sandbox

Use this as a starting point — confirm with the user before executing if assumptions matter.

### A. Identify the agent

- The user named an agent → use it.
- The user did not → default to `claude` and confirm before proceeding.

### B. Identify the workspace

- Primary workspace = the project's repo root (typically `.`).
- Read-only extras = datasets, shared libs, or vendored deps the agent should not modify → append `:ro`.
- The user wants a throwaway view that won't touch the host worktree → add `--clone`.

### C. Identify credentials

| Project signal | Provision |
|----------------|-----------|
| Uses Anthropic Claude | `printf '%s' "$ANTHROPIC_API_KEY" \| sbx secret set -g anthropic` |
| Uses Gemini API | `printf '%s' "$GEMINI_API_KEY" \| sbx secret set -g gemini` |
| Uses OpenAI / Codex | `sbx secret set -g openai --oauth` |
| Private GitHub remote | `printf '%s' "$GH_TOKEN" \| sbx secret set -g github` |
| Pulls from private registry | `printf '%s' "$REGISTRY_PASSWORD" \| sbx secret set --registry <host> --password-stdin` |

### D. Identify network needs

- Agent + workspace only → no `ports` flag needed.
- Agent spawns a dev server, API, notebook, or DB the user needs to hit → `sbx ports <sandbox> --publish <spec>` after creation.
- External network must be constrained → `sbx policy allow|deny network ...` (see `references/workspaces-networking.md`).

### E. Identify resource needs

- Lightweight (chat, code review) → defaults.
- Heavy (Go monorepo, Python ML, Node monorepo) → `--memory 8g` minimum, `--cpus` as needed.

### F. Single vs. multi-instance?

- One sandbox per workspace at a time → no `--app-name`.
- Multiple agents on the same workspace in parallel → `--app-name <id>` per instance.

## Related skills

- For Dockerizing the *project itself* (writing its `Dockerfile`, `.dockerignore`, `compose.yaml`), use `docker-project-foundations`, `docker-build-strategies`, and `docker-compose-patterns`.
- For optimizing a custom sandbox template image (size, layers, base), use `docker-build-strategies`.

## References

- `references/cli-reference.md` — Inventory of `sbx` subcommands and key flags.
- `references/agent-kits.md` — Per-agent kit specifics: what each kit injects, OAuth support, kit vs. template.
- `references/templates.md` — Sandbox image templates: built-in flavors and writing a custom template.
- `references/workspaces-networking.md` — Workspace mount semantics, port publishing, network policy.
- `references/credentials.md` — Secret store, OAuth, scope rules, proxy-managed injection.

## Assets

- `assets/sandbox-bootstrap-claude-go.sh` — Provision a Claude sandbox for a Go monorepo with private deps (GitHub token via secret store, 8 GiB memory).
- `assets/sandbox-bootstrap-gemini-python.sh` — Provision a Gemini sandbox for a Python data-science project with a read-only dataset mount.
- `assets/sandbox-parallel-compare.sh` — Run two agents in parallel on the same workspace using `--app-name` isolation.
- `assets/custom-template.Dockerfile` — Example custom sandbox template (used with `sbx create --template`).

## Scripts

- **`scripts/verify-sandbox.sh`** — Checks `sbx` is installed, Docker is reachable, and the daemon is healthy.
  ```bash
  bash scripts/verify-sandbox.sh
  ```

## Checks

- `checks/verification.md` — Detailed verification checklist for manual review.

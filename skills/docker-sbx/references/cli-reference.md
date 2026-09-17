# sbx CLI reference

This is a curated reference of the `sbx` subcommands and flags most relevant to provisioning sandboxes for AI coding agents. It is not an exhaustive man page — when in doubt, run `sbx <cmd> --help` and verify against the source at https://github.com/docker/sandboxes.

All commands invoke the standalone `sbx` binary.

## Global flags

| Flag | Purpose |
|------|---------|
| `-D, --debug` | Enable debug logging |
| `--app-name <id>` | Run against an isolated daemon instance (state, cache, socket, secrets all scoped). Hidden / dev-debug. |

## Lifecycle

### `sbx create AGENT WORKSPACE [WORKSPACE...]`

Provision a sandbox without attaching.

- `--name <name>` — Override the default name (`<agent>-<workdir>`). Rules: at least 2 characters, ASCII letters/numbers/hyphens/periods only (no `+`, no `_`), must start and end with a letter or number, at most 63 characters, `default` is reserved.
- `-t, --template <ref>` — Override the agent kit's default container image.
- `-m, --memory <limit>` — Memory limit (e.g., `2g`, `8192m`). Default: 50% host RAM, capped at 32 GiB.
- `--cpus <n>` — CPU count. Default: all host CPUs.
- `--clone` — Run agent against a private in-container clone of the workspace repo; host worktree is mounted read-only.
- `--kit <ref>` — (Experimental) Add a kit (directory, ZIP, or OCI). Repeatable. See `agent-kits.md`.
- `--profile <name>` — Apply a governance profile.
- `--static-mcp <names>` — MCP server names that form the sandbox's fixed MCP set, chosen once at creation. Comma-separated or repeatable. Requires `SBX_MCP_URL` in env.
- `-q, --quiet` — Suppress verbose output.

Workspace mount syntax: append `:ro` to mount a path read-only.

### `sbx run [AGENT] [WORKSPACE...] [-- AGENT_ARGS...]`

Create-if-needed and attach interactively. Re-attach with `--name <existing>`.

- Same shape as `create` for new sandboxes.
- `--name <existing>` — Re-attach to an existing sandbox; agent is read from its spec.
- If no workspace and no `--name`, the current directory is used.

### `sbx stop SANDBOX [SANDBOX...]`
Stop running sandboxes; state is preserved. Resume with `sbx run --name <name>`.

### `sbx rm [SANDBOX...] [--all] [-f|--force]`
Remove sandboxes destructively. `--force` skips the confirmation prompt (required for non-interactive use).

### `sbx reset [-f|--force] [--preserve-secrets]`
Destructive global cleanup: stops all sandboxes, clears caches, deletes state, removes policies, removes secrets (unless `--preserve-secrets`), signs out, stops daemon. Combine with `--app-name` to scope to one isolated instance.

## Inspection

- `sbx ls [-q|--quiet] [--json]` — List sandboxes.
- `sbx inspect SANDBOX` — (hidden) Human-readable summary of a sandbox: agent, state, auth mode, workspace, network policy, secrets, ports, sessions.
- `sbx version [-D]` — Client version (and daemon/runtime versions with `-D`).
- `sbx diagnose [-o json|github-issue] [--upload]` — Self-diagnose installation issues.

## Ports

`sbx ports SANDBOX [--publish <spec>] [--unpublish <spec>] [--json]`

Port-spec syntax: `[[HOST_IP:]HOST_PORT:]SANDBOX_PORT[/PROTOCOL]`

- Omitting `HOST_PORT` allocates an ephemeral host port.
- Omitting `HOST_IP` binds to loopback (`127.0.0.1`).
- Protocols: `tcp` (default), `tcp4`, `tcp6`, `udp`, `udp4`, `udp6`.

No flags → list current bindings.

## Secrets

`sbx secret <subcommand>` — Store and manage credentials in the host secret store.

- `sbx secret set [-g | SANDBOX] [SERVICE] [flags]`
  - `-g` — Global scope (all sandboxes).
  - `SANDBOX` — Scope to a single sandbox.
  - `SERVICE` — Service name (`anthropic`, `openai`, `openrouter`, `gemini`, `github`, `aws`, `bedrock`, `cursor`, `droid`, `google`, `groq`, `mistral`, `nebius`, `xai`).
  - `--oauth` — Start OAuth flow (currently `openai` / `-g` global only).
  - `--token <value>` / `-t <value>` — Pass token directly. Safety depends on the source: a `$(credential-helper)` substitution is acceptable; a literal token or a long-lived plain env var is not. See `credentials.md`.
  - `--password-stdin` — Read **registry** password or token from stdin. Requires `--registry`; not valid for service secrets. For service secrets, pipe via the bare pipe with no flag: `printf '%s' "$TOKEN" | sbx secret set -g <service>`.
  - `--registry <host>` — Store credentials for a private image registry.
  - `--username <name>` — Registry username (use with `--registry`; omit for token-only auth).
  - `-f, --force` — Overwrite an existing secret when `--token` is used.
- `sbx secret set-custom` — (Experimental) Store an arbitrary secret with a custom env var target.
- `sbx secret rm [-g | SANDBOX] SERVICE` — Remove a stored secret (aliases: `remove`, `delete`, `unset`).
- `sbx secret ls [-g | SANDBOX] [--json]` — List stored secrets.

## Templates (snapshots of running sandboxes)

`sbx template save SANDBOX TAG [--description ...] [-o FILE]`
`sbx template load [FILE | OCI_REF]`
`sbx template ls [-q] [--json]`
`sbx template rm REFERENCE`

These are sandbox *snapshots*, distinct from the *image templates* used at creation. See `templates.md`.

## Kits

`sbx kit <subcommand>` — (Experimental) Manage kit artifacts. An agent should reach for a custom kit when the user's needs aren't covered by a built-in agent kit (see `agent-kits.md`).

- `sbx kit validate REFERENCE` — Validate a kit (directory, ZIP, or git repo).
- `sbx kit inspect REFERENCE [--json]` — Display kit details.
- `sbx kit pack DIRECTORY [flags]` — Pack into ZIP/OCI.
- `sbx kit push REFERENCE` / `sbx kit pull REFERENCE` — Registry transport.
- `sbx kit add SANDBOX KIT_REFERENCE` — Attach a kit to a running sandbox.

## Daemon

`sbx daemon <subcommand>` — (hidden) Manage the sandboxd daemon.

- `daemon start [-d]` — Start the daemon. `-d` / `--detach` runs it in the background.
- `daemon stop` — Stop the daemon.
- `daemon status` — Check daemon status.
- `daemon log-level` — Inspect or change sandboxd's per-category log levels.

The daemon auto-starts on first command. Manual control is for debugging and CI.

## Setup helper

`sbx setup` — (Experimental) Interactive onboarding. Detects the host, scans for agent-related env vars, and prompts to import them into the global secret store.

## Other commands

- `sbx exec [-it] [-u user] [-w dir] [-e VAR=val] SANDBOX CMD [ARG...]` — Run a command inside a sandbox.
- `sbx cp SRC DST` — Copy files between host and sandbox. SRC or DST uses `SANDBOX:PATH` syntax. Not both.
- `sbx policy allow|deny network [...]` / `policy check|ls|log|profile|reset|rm|init` — Network and access policies.
- `sbx tui` — Interactive dashboard.
- `sbx completion {bash|zsh|fish|powershell}` — Shell completion.

## Anti-patterns

- Do **not** pass credentials via `--env`, `-e VAR=value`, or hard-coded `ENV`/`ARG` in templates. Use `sbx secret set` instead.
- Do **not** mount `/var/run/docker.sock` into a sandbox unless the chosen agent kit explicitly requires it (e.g., `docker-agent`).
- Do **not** pin templates to `latest`. Pin to a version tag or digest.

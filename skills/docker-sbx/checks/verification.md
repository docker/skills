# Verification Checklist

Use this checklist to verify that a generated sbx sandbox setup follows the skill's guidance.

## Prerequisites

- [ ] `sbx` binary is installed and on PATH (`command -v sbx`).
- [ ] `sbx` daemon is reachable (`sbx daemon status` succeeds) — or the user accepts that it will auto-start on the first sandbox command. `sbx` does NOT require a host Docker engine; it runs sandboxes via its own VM runtime (sandboxd).
- [ ] `sbx daemon status` either reports running or the script accepts auto-start on first command.

## CLI form

- [ ] All generated commands invoke `sbx ...`.
- [ ] Flag spellings match the real CLI (`--name`, `--memory`, `--cpus`, `--template`, `--kit`, `--clone`, `--app-name`, `--publish`, etc.). No invented flags.

## Sandbox creation

- [ ] Agent kit name is one of the supported kits (`claude`, `claude-bedrock`, `claude-vertex`, `gemini`, `codex`, `cursor`, `devin`, `opencode`, `docker-agent`, `shell`) or supplied via `--kit`. `copilot`, `kiro`, and `droid` are no longer built-in kits — use `--kit` instead of the bare agent name for them.
- [ ] At least one workspace path is provided to `sbx create` (or implicit `.` is acceptable for `sbx run`).
- [ ] Extra workspaces that should not be written to are mounted with `:ro`.
- [ ] Sandbox name (if specified) is at least 2 characters, uses only ASCII letters, numbers, hyphens, and periods (no `+`, no `_`), starts and ends with a letter or number, is at most 63 characters, and is not the reserved name `default`.

## Credentials

- [ ] No API keys, tokens, or passwords appear inline in scripts, kit specs, custom templates, or `--env` flags. Scan generated code for common token prefixes: `sk-` (Anthropic/OpenAI), `sk-ant-`, `ghp_` / `gho_` / `ghu_` / `ghs_` (GitHub), `glpat-` (GitLab), `AKIA` (AWS), `AIza` (Google), `ya29.` (Google OAuth), `xoxb-` / `xoxp-` / `xoxa-` (Slack), `eyJhbGciOi` (JWT).
- [ ] Service credentials are provisioned in order of decreasing safety: (1) interactive tty prompt `sbx secret set -g <service>` (no flag, no input), (2) `--oauth` when supported (openai/global only), (3) bare pipe `printf '%s' "$(credential-helper)" | sbx secret set -g <service>`, (4) `--token "$(credential-helper)"` (e.g., `-t "$(gh auth token)"`) when the value comes from a runtime secret store. `-f` overwrites an existing secret. Sandbox-scoped variants drop `-g`. The flag `--token` is not unsafe by itself — the **source** of the value matters: command substitutions from a credential helper (`gh`, `op`, `vault`, `aws secretsmanager`) are valid; literal tokens and long-lived plain env vars are not.
- [ ] Registry credentials use `printf '%s' "$PASSWORD" | sbx secret set --registry <host> --password-stdin` (`--password-stdin` is only valid with `--registry`).
- [ ] No literal token appears in any `--token` / `-t` argument in any committed script. Values must come from `$(credential-helper)` substitutions (`$(gh auth token)`, `$(op read ...)`, `$(vault kv get ...)`, `$(aws secretsmanager get-secret-value ...)`) or from stdin pipes — never from a hardcoded string or a long-lived plain env var.
- [ ] Credential-provisioning scripts suppress shell tracing around the secret handling block (`{ set +x; } 2>/dev/null` before the pipe) so `bash -x` does not leak the value into CI logs.
- [ ] On shared hosts or CI runners with multiple tenants under one OS user, secrets are scoped per-sandbox (no `-g`) to prevent cross-tenant exposure.
- [ ] After first `sbx create`, the user has audited the auto-imported secrets with `sbx secret ls -g` (kit-declared `credentials.sources` are picked up automatically without an explicit prompt).

## Network & ports

- [ ] Ports are published explicitly with `sbx ports <sandbox> --publish <spec>` only when the agent needs ingress.
- [ ] Bindings default to loopback (`127.0.0.1`) unless the user explicitly needs LAN exposure.
- [ ] No mounting of `/var/run/docker.sock` unless the chosen agent kit explicitly requires it (e.g., `docker-agent`).

## Resource limits

- [ ] `--memory` is set explicitly for resource-heavy projects (Go monorepos, Python ML, large Node monorepos). Default of 50% host RAM is otherwise acceptable.
- [ ] `--cpus` is set when CPU contention with the host matters.

## Custom templates

- [ ] Custom Dockerfile templates (`sbx create --template <ref>`) start with `# syntax=docker/dockerfile:1`.
- [ ] Custom templates do not pin to `latest` for their base image; use a version tag or digest.
- [ ] Custom templates do not embed credentials via `ARG` or `ENV`.
- [ ] Custom templates do not override the entrypoint or user of the agent kit they extend.

## Multi-instance isolation

- [ ] When the user wants multiple agents in parallel on the same workspace, each `sbx` invocation passes a distinct `--app-name <id>` global flag.
- [ ] Cleanup uses `sbx --app-name <id> reset --force` per instance (matching app-name).

## Validation commands

```bash
# Prerequisite check
bash scripts/verify-sandbox.sh

# Inspect the generated sandbox(es)
sbx ls
sbx ls --json | jq

# Confirm the sandbox is reachable and the agent kit is correct
sbx inspect <sandbox-name> --json | jq '.agent, .workspaces'

# Confirm published ports
sbx ports <sandbox-name>

# Clean up
sbx rm <sandbox-name> --force
```

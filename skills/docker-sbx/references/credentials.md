# Credentials and secrets

`sbx` keeps API keys, OAuth tokens, registry credentials, and arbitrary secrets in the **host OS secret store**, never inside the sandbox filesystem. At request time, a proxy injects them into outbound calls. This means:

- The sandbox never sees the literal key on disk or in an env var that survives a restart.
- The host never writes keys into a kit spec, a custom template, or a shell-history-leaking flag.
- Compromise of the sandbox does not leak the host's keys.

## Storage

| Platform | Backend |
|----------|---------|
| macOS | Keychain |
| Linux | Pass (with file-based fallback) |
| Windows | Keychain (with file-based fallback) |

Realm: `realms.DockerSandbox` for credentials, `realms.DockerSandboxOAuth` for OAuth tokens.

## Scope

- **Global** (`-g`): available to all sandboxes on this host.
- **Per-sandbox**: scoped to a single sandbox by name.

For a personal developer machine, prefer global for credentials shared across all sandboxes of the same agent (e.g., your Anthropic key for Claude). **On shared hosts, CI runners, or any machine where multiple users or tenants run sandboxes under the same OS user**, scope secrets per-sandbox instead of globally — global secrets are visible to every sandbox spawned by that OS user.

## Storing credentials

Methods below are listed in order of decreasing safety. Pick the safest form that fits your context.

### 1. Interactive prompt (safest for human-driven provisioning)

```bash
sbx secret set -g github         # prompts on tty; value never in env, history, ps, or argv
sbx secret set my-sandbox openai # sandbox-scoped variant
```

### 2. OAuth flow (when supported)

```bash
# Currently supported: openai / global scope only.
sbx secret set -g openai --oauth
```

### 3. Stdin pipe (preferred for CI / scripts)

```bash
# Bare pipe — no flag. `--password-stdin` is registry-only and will reject
# service-secret usage in v0.34.0+.
# Use `printf '%s'`, NOT `echo` (echo appends a newline and silently breaks the secret).
printf '%s' "$GH_TOKEN" | sbx secret set -g github
printf '%s' "$ANTHROPIC_API_KEY" | sbx secret set -g anthropic
```

`printf` is a builtin in bash and zsh, so the expanded value never appears in argv of a separate process. In POSIX sh / dash / busybox the builtin guarantee does not hold; prefer bash/zsh for the pipe form, or fall back to interactive entry.

### 4. `--token` / `-t` with a credential-helper command substitution

`--token` (or `-t`) is **not** unsafe by itself — what matters is the source of the value passed to it. A literal token written into a committed script is unsafe; a token sourced at runtime from a credential helper is fine. The expanded value transits sbx's argv briefly in both cases, but with a credential helper it never persists anywhere else.

```bash
# Acceptable: the value comes from a runtime credential helper.
sbx secret set -g github -f -t "$(gh auth token)"
sbx secret set -g anthropic -f -t "$(op read 'op://Personal/Anthropic/token')"
sbx secret set -g aws -f -t "$(vault kv get -field=token secret/aws)"
```

`-f` (`--force`) overwrites an existing secret. Required when re-provisioning a rotated token non-interactively.

**Never** pass a literal token in argv, and **never** pass a token sourced from a long-lived plain env var (one set in `.bashrc`, `.zshrc`, `.envrc`, or similar) — both leak through `ps aux`, shell history, daemon logs, and process accounting:

```bash
# NEVER — literal token persists in shell history and (if committed) Git
sbx secret set -g github -t "ghp_LiteralTokenWritten"

# NEVER — long-lived plain env var inherited by every subprocess
sbx secret set -g github -t "$GITHUB_PAT"   # if $GITHUB_PAT comes from .bashrc
```

### Registry pull credentials (different surface)

```bash
# `--password-stdin` is REQUIRED here and is the only place it is valid.
# Host-only when -g is omitted; with -g, also written into every new
# sandbox as ~/.docker/config.json (which can leak the credential into
# sandbox images you build from inside the sandbox).
printf '%s' "$REGISTRY_PASSWORD" | sbx secret set --registry my-registry.example.com --password-stdin
```

### Onboarding helper (Experimental)

```bash
# `sbx setup` scans host env vars and offers to import them. The discovery
# path also fires automatically on `sbx create` for kit-declared sources.
# Always audit with `sbx secret ls -g` afterwards to confirm what was imported.
sbx setup
```

## Discovery (auto-pickup from host env)

Each agent kit declares a `credentials.sources` list — an ordered set of env vars `sbx` checks on the host when the kit is created. If found, the value is silently moved into the host secret store and removed from any later proxy state.

**This discovery fires automatically on `sbx create` (not just `sbx setup`).** If `ANTHROPIC_API_KEY` is set in your shell rc file and you `sbx create claude .`, the value is imported into the global secret store without an explicit prompt. After first sandbox creation, audit with `sbx secret ls -g` and remove anything you did not intend with `sbx secret rm -g <service>`.

Example (GitHub):
```yaml
credentials:
  sources:
    - env: [GH_TOKEN, GITHUB_TOKEN]
```

Run `sbx setup` to walk through discovery interactively before any `sbx create` if you want explicit control over what gets imported.

## Injection into the sandbox

Two paths:

1. **Proxy-managed env vars** — The kit declares `environment.proxyManaged: [ANTHROPIC_API_KEY]`. At request time, the proxy intercepts outbound HTTP to the declared `serviceDomains` and rewrites the auth header from the secret store. The env var inside the sandbox holds a sentinel value, **not** the real key.
2. **OAuth credentials file** — When the kit declares an `oauth` section, the resolved token is written to a path like `~/.agent/<service>/.credentials.json` inside the sandbox at startup. This is the OAuth refresh-token flow; ephemeral access tokens are still proxy-injected.

Either way, the literal long-lived secret does not land in plain env var space inside the sandbox.

## Custom secrets (Experimental)

`sbx secret set-custom` stores a secret for a service not built into sbx. It binds a placeholder value to a host pattern, so the sandbox sees the placeholder while the proxy substitutes the real secret on outbound requests to that host.

```bash
# Required flags: --host (target domain / wildcard), --env (env var the sandbox sees).
# --value (or -t / --token) holds the real secret. `set-custom` has no stdin
# form in v0.34.0, so the value always transits argv — the same source rules
# from method 4 above apply: a `$(credential-helper)` substitution is fine,
# a literal token or long-lived plain env var is not. Run interactively in a
# terminal you can clear, and `history -d` the matching line if your shell
# records it.
sbx secret set-custom -g --host api.example.com --env MY_API_KEY \
    --value "$(op read 'op://Personal/my-api/token')"
```

## Listing and removing

```bash
sbx secret ls                          # current sandbox or global, terminal table
sbx secret ls --json                   # script-friendly
sbx secret ls -g                       # global secrets
sbx secret rm -g github                # remove a global secret (aliases: remove, delete, unset)
sbx secret rm my-sandbox openai        # remove a sandbox-scoped secret
```

## Anti-patterns

- **Never** pass credentials via `sbx exec -e VAR=...` or `--env`. They land in plain env var space and can be observed inside the sandbox.
- **Never** hard-code credentials in kit specs (`environment.variables: { API_KEY: sk-... }`), custom templates (`ENV API_KEY=...`, `ARG API_KEY=...`), or shell scripts that get committed. Common token prefixes to scan for in code review: `sk-` (Anthropic, OpenAI), `sk-ant-` (Anthropic specifically), `ghp_` / `gho_` / `ghu_` / `ghs_` (GitHub PATs and Actions tokens), `glpat-` (GitLab PATs), `AKIA` (AWS access key IDs), `AIza` (Google API keys), `ya29.` (Google OAuth access tokens), `xoxb-` / `xoxp-` / `xoxa-` (Slack tokens), `eyJhbGciOi` (JWTs starting with `{"alg":`).
- **Never** echo a credential in a shell argument — it ends up in `ps`, the shell history, and the daemon logs. Pipe it via `printf '%s' "$VAR" | sbx secret set -g <service>` (no flag) for service secrets, or with `--password-stdin` for registry secrets, or use the interactive tty prompt.
- **Never** run a credential-provisioning script under `bash -x` / `set -x` — the trace prints expanded values to stderr, which is typically captured in CI logs.
- **Never** put a token in a file inside the workspace, even temporarily. The agent can read it.
- **Never** assume `printf '%s'` is a builtin in all shells. In bash and zsh it is; in dash/busybox/POSIX sh it may be an external binary, which means the expanded value briefly appears in process argv. Either pin to bash (`#!/usr/bin/env bash`) or fall back to the interactive prompt.

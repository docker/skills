# Agent kits

A *kit* is a declarative spec (`spec.yaml`) that tells `sbx` how to set up a sandbox for a specific agent: which container image to use, which credentials to inject, which environment variables to set, which startup commands to run.

## Built-in kits

The following kits ship embedded in the `sbx` binary. Reference them by name as the first positional arg to `sbx create`:

| Kit | Tool | Notes |
|-----|------|-------|
| `claude` | Claude Code | Most common. Persistent volumes. Entrypoint runs with `--dangerously-skip-permissions` so the agent can act inside the sandbox without prompts. |
| `claude-bedrock` | Claude via AWS Bedrock | AWS credential chain expected. |
| `claude-vertex` | Claude via Google Vertex AI | GCP credential chain expected. Unlisted in `sbx create --help`; invoke as `sbx create claude-vertex`. |
| `gemini` | Gemini CLI | Yolo mode. `GEMINI_API_KEY` injected via proxy. MCP settings are merged (not overwritten) at startup. |
| `codex` | OpenAI Codex | Yolo mode. Persistent volumes. OAuth supported via `sbx secret set -g openai --oauth`. |
| `copilot` | GitHub Copilot CLI | Ephemeral. Uses runtime-substituted `initFiles` for `${WORKDIR}`-aware config. |
| `cursor` | Cursor agent | |
| `kiro` | AWS Kiro | Minimal kit. No declared credentials or network config. |
| `opencode` | OpenCode | |
| `docker-agent` | Docker Agent | Multi-provider. Requires Docker socket access (declared in kit). |
| `droid` | Factory.ai Droid | |
| `shell` | Generic shell | No specific agent binary; useful as a base or for ad-hoc work. |

For custom kits, pass `--kit <path|oci-ref>` to `sbx create` or `sbx run`. Repeatable.

## Kit vs. template — the distinction

- A **kit** is the agent's *behavior contract*: declarative config (credentials, env, commands, files, network, OAuth). Selected by name (`claude`, `gemini`, …) or by `--kit`.
- A **template** is the *container image* used at the base of the sandbox. Selected by `--template <image-ref>`, defaulting to whatever the kit declares.

A custom template extends or replaces the image; the kit's behavior contract still applies on top. See `templates.md`.

## What a kit injects

Reading the `spec.yaml` of a kit (v2 form, `schemaVersion: "2"`) reveals what will appear in the sandbox:

- **`sandbox.image`** — Default container image (overridable with `--template`). Mutually exclusive with `sandbox.build:` (defined in the schema but not yet implemented in sbx v0.34.0 — use `image:` for now).
- **`sandbox.entrypoint.run`** — Entrypoint command and args.
- **`environment.variables`** — Static env vars (literal values). In v2 the proxy-managed semantic is implicit on `credentials[].apiKey.name` — there is no separate `environment.proxyManaged` list.
- **`credentials[]`** — Typed list of credentials the kit needs. Each entry declares a `service`, an optional `required` flag, and one of `apiKey` / `oauth` / `sshAgent` (P2, not yet in the spec library).
- **`caps.network.allow` / `caps.network.deny`** — Egress allow / deny lists at host+port level. Replaces v1 `network.serviceDomains`. Every domain a credential injects into MUST also appear in `caps.network.allow` — there is no auto-derived egress.
- **`commands.install[]`** — Runs once as root at create time. Each entry: `command: "<string>"` (executed via `sh -c`, so shell metachars work), optional `user`, `description`.
- **`commands.startup[]`** — Runs on **every** container start (create, restart, daemon or host reboot) as the agent user. Each entry: `command: ["<list>"]` (`exec`-style, no shell — wrap in `["sh", "-c", "..."]` if you need shell metachars), optional `user`, `background`.
- **`commands.initFiles[]`** — Files written at startup via shell. Fields: `path`, `content` (only `${WORKDIR}` placeholder supported), `mode`, `onlyIfMissing`.
- **`files/home/` and `files/workspace/`** — Static files embedded in the kit and copied to the agent's home or the workspace. Absolute paths and `..` traversal rejected at validation.
- **`publishedPorts[]`** — Ports the runtime publishes on the host (ephemeral, bound to `127.0.0.1`). Entry: `container: <port>`, optional `protocol`, `name`.
- **`agentContext`** — Free-form text inlined into the agent's AI profile file (e.g., `CLAUDE.md`). For mixins, written to `<AI-file-dir>/kits-memory/<kit>.md` and referenced via a `## Kits` sentinel (progressive disclosure).

## Per-agent specifics worth knowing

- **Claude** — `--dangerously-skip-permissions` is part of the entrypoint, intentional: that is what makes the sandbox a *real* sandbox (agent can act freely inside it because the host is protected by Docker). Persistent volumes preserve agent state across runs.
- **Gemini** — Settings files (`~/.gemini/settings.json`) are merged with `jq` at startup, not overwritten. This preserves user customizations.
- **Copilot** — Cannot use the static `files/` directory because the config references `${WORKDIR}`. Uses `initFiles` to apply placeholder substitution.
- **Kiro** — Intentionally minimal — useful as a reference when authoring a new kit.
- **docker-agent** — Requests Docker socket access explicitly via its kit. This is the only path by which `/var/run/docker.sock` enters a sandbox; otherwise it is *not* mounted.

## How agent selection works under the hood

When you run `sbx create <agent-name> <workspace>`:

1. The CLI looks up `<agent-name>` in the embedded built-in kits.
2. If not found, it falls back to kits loaded via `--kit`.
3. The kit's `kind` must be `sandbox` (vs `mixin`). Mixins extend other kits and are not selectable as the primary agent.
4. The kit's `sandbox.image` is used unless `--template` overrides it.

## Authoring a custom kit

A kit is a directory containing a `spec.yaml`, optionally with a `files/` subtree for static content. Publish as a local directory, an OCI artifact, or a git commit-SHA reference. The current spec form is `schemaVersion: "2"`; v1 still loads via legacy shims but is deprecated — new kits should target v2.

### Kit vs mixin

Two `kind`s:

- **`kind: sandbox`** — the primary agent kit. MUST declare a `sandbox:` block (with `image:` and `entrypoint:`). Selected as the first positional arg to `sbx create`.
- **`kind: mixin`** — additive capability. MUST NOT declare a `sandbox:` block. Composed onto a sandbox kit via the top-level `mixins:` field, or at run time via `--kit`.

Exactly one sandbox kit per composition; mixins stack.

### Minimum viable `spec.yaml`

```yaml
schemaVersion: "2"
kind: sandbox
name: my-agent
sandbox:
  image: my-registry/my-template:1.0
  entrypoint:
    run: ["my-agent", "--start"]
```

Validate: `sbx kit validate ./my-kit/`. Use: `sbx create my-agent ./project --kit ./my-kit/`.

### Fuller example — with credentials, network, and commands

```yaml
schemaVersion: "2"
kind: sandbox
name: my-agent
description: "Runs my-agent in a Docker sandbox."
sandbox:
  image: my-registry/my-template:1.0
  aiFilename: AGENT.md
  entrypoint:
    run: ["my-agent", "--start"]

environment:
  variables:
    MY_AGENT_LOG_LEVEL: debug

credentials:
  - service: my-agent
    required: false
    apiKey:
      name: MY_AGENT_API_KEY               # env var the sandbox sees (proxy fills it in)
      inject:
        - domain: api.my-agent.com
          header: Authorization
          format: "Bearer %s"              # exactly one %s

caps:
  network:
    allow:
      - api.my-agent.com                    # MUST include every inject[].domain above
      - "*.my-agent.com"

commands:
  install:
    - command: "command -v my-agent || curl -fsSL https://my-agent.com/install.sh | sh"
      description: "Install the agent binary if the base image doesn't already ship it."
  startup:
    - command: ["sh", "-c", "mkdir -p ~/.my-agent"]
      description: "Idempotent — startup runs on every container start."
```

### Bindings — the split with users

A kit declares *what it needs* (`credentials[].service` + `apiKey.inject[].domain`). The user declares *where the secret value lives* on their host, in `~/.config/sbx/credentials.yaml`. The engine only injects a credential into a domain that appears in **both** the kit's `inject[].domain` **and** the user's `bindings[<service>].allowedDomains`. See `credentials.md` → "Bindings" for the user-side file format.

### Common pitfalls

- **`commands.startup` runs on every container start** (create, restart, daemon/host reboot) — author idempotently (`mkdir -p`, `... || true`); do not assume "first run only".
- **`commands.install` re-runs on recreate.** Guard file writes with `if [ ! -f ... ]`, or use `commands.initFiles` with `onlyIfMissing: true` for static content.
- **`SBX_CRED_<SERVICE>_MODE` is available at install time.** Values: `apikey` | `oauth` | `none`. Read defensively: `${SBX_CRED_<SERVICE>_MODE:-none}`.
- **`sbx kit add` cannot apply immutable settings** — labels, privileged mode, volumes, `publishedPorts` are fixed at container create time. The user must recreate the sandbox with `--kit` to pick them up.
- **Two `credentials[]` entries with the same `service` across composed kits is a hard error** at `sbx run` time (composition step, not per-artifact validation).
- **`commands.install[].command` is a string; `commands.startup[].command` is a list.** Getting the shape wrong is the most common `sbx kit validate` failure (`cannot unmarshal !!str into []string`).
- **Every `apiKey.inject[].domain` MUST appear in `caps.network.allow`.** Spec validation rejects the mismatch — there is no auto-derived egress.

### Distribution

Four reference forms:

| Form | Example |
|---|---|
| Embedded built-in | `claude` (by name) |
| Local directory | `./my-kit/` |
| Git commit-SHA | `git+https://github.com/org/repo.git#ref=<40-hex-sha>&dir=<subdir>` |
| OCI digest | `oci://ghcr.io/org/my-kit@sha256:<digest>` |

Remote refs MUST be immutable: a **full 40-hex commit SHA** for git; a **`@sha256:` digest** for OCI. Branch names and tags (including `:latest` and semver tags like `v1.2.3`) are rejected — tags are mutable and can be retagged.

Publish: `sbx kit push ./my-kit/ ghcr.io/org/my-kit:1.0` accepts a tag for ergonomics but rewrites the published artifact so consumers reference it by digest. Inspect a pushed kit: `sbx kit inspect oci://ghcr.io/org/my-kit@sha256:<digest>`.

### Going further

For advanced authoring topics not covered here — `extends:` inheritance, full OAuth credential shape, `agentContext` progressive disclosure, TCK testing, v1 → v2 migration — use the **`kit-author`** skill published in the [`docker/sbx-kits-contrib`](https://github.com/docker/sbx-kits-contrib/tree/main/skills/kit-author) repository. That skill is the canonical authoring guide; this page focuses on *using* sbx and the common authoring paths.

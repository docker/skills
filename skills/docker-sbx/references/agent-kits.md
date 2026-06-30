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

Reading the `spec.yaml` of a kit reveals what will appear in the sandbox:

- **`sandbox.image`** — Default container image (overridable with `--template`).
- **`sandbox.entrypoint.run`** — Entrypoint command and args.
- **`environment.variables`** — Static env vars (literal values).
- **`environment.proxyManaged`** — Env var names whose values are filled at request time by the proxy from the host secret store (e.g., `ANTHROPIC_API_KEY`).
- **`commands.install`** — Install steps run as root at create time (skipped when the binary is already in the template image).
- **`commands.startup`** — Startup steps run as the agent user at run time.
- **`initFiles`** — Files copied at container creation, with placeholder substitution (e.g., `${WORKDIR}`).
- **`files/home/` and `files/workspace/`** — Static files embedded in the kit and copied to the agent's home or the workspace.
- **`credentials.sources`** — Ordered list of host env vars to discover automatically.
- **`network.serviceDomains`** — Domains intercepted by the proxy, with auth-header templates that get filled from the secret store.
- **`oauth`** — Token endpoint, file path, refresh logic.

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

## Authoring a custom kit (high level)

```yaml
schemaVersion: "1"
kind: sandbox
name: my-agent

sandbox:
  image: my-registry/my-template:1.0
  entrypoint:
    run: ["my-agent", "--start"]

environment:
  variables:
    MY_AGENT_LOG_LEVEL: debug
  proxyManaged:
    - MY_AGENT_API_KEY

credentials:
  sources:
    - env: [MY_AGENT_TOKEN, MY_AGENT_API_KEY]

commands:
  startup:
    - my-agent migrate
```

Validate before use: `sbx kit validate ./my-kit/`. Then `sbx create my-agent ./project --kit ./my-kit/`.

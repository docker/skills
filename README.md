# Docker Skills for AI Coding Agents

[![CI](https://github.com/docker/skills/actions/workflows/ci.yml/badge.svg?branch=main)](https://github.com/docker/skills/actions/workflows/ci.yml)
[![Agent Skills](https://img.shields.io/badge/Agent%20Skills-Specification-blue)](https://agentskills.io/specification)
[![License](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](LICENSE)
[![skills.sh](https://skills.sh/b/docker/skills)](https://skills.sh/docker/skills)
[![OpenSSF Scorecard](https://api.scorecard.dev/projects/github.com/docker/skills/badge)](https://scorecard.dev/viewer/?uri=github.com/docker/skills)
[![Release](https://img.shields.io/github/v/tag/docker/skills?sort=semver&label=release)](https://github.com/docker/skills/releases)

Docker-authored knowledge skills for Dockerfiles, Compose, Docker Agent, Docker
Sandboxes, and safe Docker workflows. Compatible AI coding agents load the
relevant guidance when a request matches a skill's description.

## Install

Choose your client's marketplace or extension, or the cross-client `skills`
CLI; these are peer installation paths. Manual copy is a fallback. For skill
selection, scope, updates, pinning, removal, verification, and troubleshooting,
see the [Docker Docs installation guide](https://docs.docker.com/ai/skills/install/).

### `skills` CLI

The [`skills` CLI](https://skills.sh) reads this repository's
[`skills.sh.json`](skills.sh.json) index and prompts you to select skills and
agents. Examples:

```bash
# Choose skills and agents interactively
npx skills add docker/skills

# Browse without installing
npx skills add docker/skills --list

# Install one skill into the project (add -g for user scope)
npx skills add docker/skills --skill docker-compose-patterns --yes

# Install every skill into Codex
npx skills add docker/skills --skill '*' --agent codex --yes

# Install every skill into every detected agent
npx skills add docker/skills --all

# Update installed skills
npx skills update

# Pin one skill to a reviewed release tag (replace vX.Y.Z)
npx skills add https://github.com/docker/skills/tree/vX.Y.Z \
  --skill docker-compose-patterns --yes
```

### Marketplace or extension

In **Claude Code** or **GitHub Copilot CLI**, run:

```text
/plugin marketplace add docker/skills
/plugin install docker-skills@docker
```

In **Cursor** or **Codex**, select `docker/skills` and the `docker-skills`
plugin from the client's marketplace where repository-backed plugins are
available. Otherwise, use the `skills` CLI with `--agent cursor` or
`--agent codex`, respectively, or copy the skills manually. Start a new Codex
session after installing.

For **Gemini CLI**, run in your terminal:

```bash
gemini extensions install https://github.com/docker/skills
```

Restart Gemini CLI after installation to discover the extension and its skills.
These client-managed installs are not updated by `npx skills update`.

### Manual copy

If no managed installer fits your client, choose a reviewed tag from
[Docker Skills releases](https://github.com/docker/skills/releases), clone it,
and copy complete folders from `skills/` into your agent's skill directory.
Replace `vX.Y.Z` with your chosen release tag:

```bash
git clone --branch vX.Y.Z --depth 1 https://github.com/docker/skills.git
```

Check your client's skill-discovery documentation for the right path and scope;
common destinations include:

| Agent | Skill directory |
|-------|-----------------|
| Claude Code | `~/.claude/skills/` |
| Codex | `~/.codex/skills/` or `~/.agents/skills/` |
| Cursor | `~/.cursor/skills/` |
| GitHub Copilot | `.github/skills/` in the project |
| Gemini CLI | `~/.gemini/skills/` |
| OpenCode | `~/.config/opencode/skills/` |

If you clone the repository into a project's root, agents that support its
discovery symlinks can find the skills there; a clone inside a subdirectory
is not discovered this way. Manual copies have no managed updater; replace
complete skill folders when upgrading.

[Google Antigravity](https://docs.docker.com/ai/skills/install/#google-antigravity)
uses the `skills` CLI or manual copy; it has no dedicated plugin manifest.
Docker Agent consumes skills installed in supported project or user paths.
Docker Sandboxes installation is experimental; see the Docker Docs guide for
that path.

## Published surfaces

This inventory is generated from [`catalog.yaml`](catalog.yaml).

<!-- distributions-start -->
### Native marketplaces

- **[Claude Code marketplace](https://docs.docker.com/ai/skills/install/#claude-code).** Client-managed plugin installation from Docker's marketplace.
- **[GitHub Copilot CLI marketplace](https://docs.docker.com/ai/skills/install/#github-copilot-cli).** Client-managed plugin installation from Docker's marketplace.
- **[Cursor marketplace](https://docs.docker.com/ai/skills/install/#cursor).** Client-managed installation through Cursor's documented plugin interface.
- **[Codex marketplace](https://docs.docker.com/ai/skills/install/#codex).** Client-managed installation where the Codex marketplace is available.

### Extensions

- **[Gemini CLI extension](https://docs.docker.com/ai/skills/install/#gemini-cli).** Repository-backed extension installation managed by Gemini CLI.

### skills CLI

- **[skills CLI](https://docs.docker.com/ai/skills/install/#skills-cli).** Cross-client project or user installation with explicit skill selection.

### Docker products

- **[Docker Sandboxes *(experimental)*](https://docs.docker.com/ai/skills/install/#docker-sandboxes).** Product-native installation into the shared sandbox skill store.
- **[Docker Agent](https://docs.docker.com/ai/skills/install/#docker-agent).** Consumer of skills installed in supported project or user paths.

### Sources and fallback

- **[Git clone or manual copy](https://docs.docker.com/ai/skills/install/#git-clone-or-manual-copy).** Auditable fallback when no managed installer fits the client.
<!-- distributions-end -->

## Catalog

The table is generated from [`catalog.yaml`](catalog.yaml) by `task catalog`.

<!-- catalog-start -->
| Product | Description | Skills |
|---------|-------------|--------|
| **[Dockerfile & Build](https://docs.docker.com/build/)**<br>[source](https://github.com/docker/buildx) | Containerize a project and write, optimize, and harden Dockerfiles and images. | [`docker-project-foundations`](skills/docker-project-foundations) — Guidance for initializing and structuring a Dockerized project.<br>[`docker-build-strategies`](skills/docker-build-strategies) — Strategies for efficient, secure, and optimized Docker image builds. |
| **[Docker Compose](https://docs.docker.com/compose/)**<br>[source](https://github.com/docker/compose) | Wire multi-container stacks with robust, maintainable Compose configurations. | [`docker-compose-patterns`](skills/docker-compose-patterns) — Patterns for robust, maintainable Docker Compose configurations. |
| **[Docker Sandboxes](https://docs.docker.com/ai/sandboxes/)**<br>[source](https://github.com/docker/sandboxes) | Run AI coding agents in isolated microVMs with the sbx CLI, including network policy, credentials, environments, and kits. | [`docker-sandboxes-lifecycle`](skills/docker-sandboxes-lifecycle) — Create, reattach to, and tear down local `sbx` sandboxes; choose workspace bind-mount vs --clone isolation.<br>[`docker-sandboxes-network-credentials`](skills/docker-sandboxes-network-credentials) — Configure sandbox network egress policy and provision service/registry credentials safely through the proxy-injection model.<br>[`docker-sandboxes-env`](skills/docker-sandboxes-env) *(experimental)* — Author, plan, and run declarative sbxenv.yaml environments (workspace, kits, args, host lifecycle hooks, secrets/registries/bindings, ports) for Docker Sandboxes.<br>[`docker-sandboxes-kits`](skills/docker-sandboxes-kits) *(experimental)* — Author, validate, package, sign, and compose reusable sandbox/mixin kits (spec.yaml, schema v2). |
| **[Docker Agent](https://docs.docker.com/ai/docker-agent/)**<br>[source](https://github.com/docker/docker-agent) | Author, run, and ship AI agents with Docker Agent, from agent.yaml to serving and distribution. | [`docker-agent-config`](skills/docker-agent-config) — Reference and rules for authoring agent.yaml configs for Docker Agent (cagent) — agents, models, providers, toolsets, and multi-agent teams.<br>[`docker-agent-run`](skills/docker-agent-run) — Rules for running Docker Agent locally — safety/approval modes, sandbox isolation, aliases, worktrees, and troubleshooting a run.<br>[`docker-agent-deploy`](skills/docker-agent-deploy) — Rules for exposing Docker Agents as servers, distributing them via OCI registries, and evaluating them for regressions in CI. |
| **Cross-Product** | Guardrails and policies that apply across every Docker skill product. | [`docker-destructive-guardrails`](skills/docker-destructive-guardrails) — Cross-product policy for confirming irreversible or destructive Docker operations before running them. |
<!-- catalog-end -->

## Contributing

Read [CONTRIBUTING.md](CONTRIBUTING.md) before opening a change. Skill changes
must keep catalog and skill versions synchronized, update evaluations and
ownership where needed, and include a DCO sign-off.

Run validation from the repository root:

```console
task
```

Canonical skill content is under [`skills/`](skills/), and repository contracts
are summarized in [`AGENTS.md`](AGENTS.md).

## License

This project is licensed under the Apache License 2.0. See [LICENSE](LICENSE).

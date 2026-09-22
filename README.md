# Docker Skills for AI Coding Agents

[![CI](https://github.com/docker/skills/actions/workflows/ci.yml/badge.svg?branch=main)](https://github.com/docker/skills/actions/workflows/ci.yml)
[![Agent Skills](https://img.shields.io/badge/Agent%20Skills-Specification-blue)](https://agentskills.io/specification)
[![License](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](LICENSE)
[![skills.sh](https://skills.sh/b/docker/skills)](https://skills.sh/docker/skills)
[![OpenSSF Scorecard](https://api.scorecard.dev/projects/github.com/docker/skills/badge)](https://scorecard.dev/viewer/?uri=github.com/docker/skills)
[![Release](https://img.shields.io/github/v/tag/docker/skills?sort=semver&label=release)](https://github.com/docker/skills/releases)

Docker-authored knowledge skills that improve AI coding agent output for Docker-related tasks. Skills are authored once as portable `SKILL.md` directories and discovered automatically by any compliant agent through standard skill paths.

## Skills

Skills are grouped by the Docker product they cover. The table is generated from [`catalog.yaml`](catalog.yaml) by `task catalog`; edit the catalog, not the table.

<!-- catalog-start -->
| Product | Description | Skills |
|---------|-------------|--------|
| **[Dockerfile & Build](https://docs.docker.com/build/)**<br>[source](https://github.com/docker/buildx) | Containerize a project and write, optimize, and harden Dockerfiles and images. | [`docker-project-foundations`](skills/docker-project-foundations) — Guidance for initializing and structuring a Dockerized project.<br>[`docker-build-strategies`](skills/docker-build-strategies) — Strategies for efficient, secure, and optimized Docker image builds. |
| **[Docker Compose](https://docs.docker.com/compose/)**<br>[source](https://github.com/docker/compose) | Wire multi-container stacks with robust, maintainable Compose configurations. | [`docker-compose-patterns`](skills/docker-compose-patterns) — Patterns for robust, maintainable Docker Compose configurations. |
| **[Docker Sandboxes](https://docs.docker.com/ai/sandboxes/)**<br>[source](https://github.com/docker/sandboxes) | Run AI coding agents in isolated microVMs with the sbx CLI, including network policy, credentials, environments, and kits. | [`docker-sandboxes-lifecycle`](skills/docker-sandboxes-lifecycle) — Create, reattach to, and tear down local `sbx` sandboxes; choose workspace bind-mount vs --clone isolation.<br>[`docker-sandboxes-network-credentials`](skills/docker-sandboxes-network-credentials) — Configure sandbox network egress policy and provision service/registry credentials safely through the proxy-injection model.<br>[`docker-sandboxes-env`](skills/docker-sandboxes-env) *(experimental)* — Author, plan, and run declarative sbxenv.yaml environments (workspace, kits, args, host lifecycle hooks, secrets/registries/bindings, ports) for Docker Sandboxes.<br>[`docker-sandboxes-kits`](skills/docker-sandboxes-kits) *(experimental)* — Author, validate, package, sign, and compose reusable sandbox/mixin kits (spec.yaml, schema v2). |
| **[Docker Agent](https://docs.docker.com/ai/docker-agent/)**<br>[source](https://github.com/docker/docker-agent) | Author, run, and ship AI agents with Docker Agent, from agent.yaml to serving and distribution. | [`docker-agent-config`](skills/docker-agent-config) — Reference and rules for authoring agent.yaml configs for Docker Agent (cagent) — agents, models, providers, toolsets, and multi-agent teams.<br>[`docker-agent-run`](skills/docker-agent-run) — Rules for running Docker Agent locally — safety/approval modes, sandbox isolation, aliases, worktrees, and troubleshooting a run.<br>[`docker-agent-deploy`](skills/docker-agent-deploy) — Rules for exposing Docker Agents as servers, distributing them via OCI registries, and evaluating them for regressions in CI. |
| **Cross-Product** | Guardrails and policies that apply across every Docker skill product. | [`docker-destructive-guardrails`](skills/docker-destructive-guardrails) — Cross-product policy for confirming irreversible or destructive Docker operations before running them. |
<!-- catalog-end -->

Each skill triggers directly from its own description; there is no entry-point skill to load first. When a task spans several skills, load them in the order their outputs feed each other: `docker-project-foundations` before `docker-build-strategies` or `docker-compose-patterns` when the project has no Docker setup yet; `docker-build-strategies` before `docker-compose-patterns` when both a `Dockerfile` and a `compose.yaml` change; `docker-sandboxes-lifecycle` before `docker-sandboxes-network-credentials`, and both before `docker-sandboxes-env` or `docker-sandboxes-kits`; `docker-agent-config` before `docker-agent-run` before `docker-agent-deploy`. Skills marked *experimental* cover features whose schemas may still change.

## Installation

### Quick start: the `skills` CLI

The [`skills` CLI](https://skills.sh) installs into every major coding agent (Claude Code, Codex, Cursor, GitHub Copilot, Gemini CLI, OpenCode, Windsurf, Cline, Kiro, and more). It reads the [`skills.sh.json`](skills.sh.json) index in this repo, so skills are listed grouped by product:

```bash
npx skills add docker/skills
```

The command prompts for which skills and which agents to install to. Non-interactive variants:

```bash
# Browse the catalog without installing anything
npx skills add docker/skills --list

# Install one skill, no prompts (project scope; add -g for user scope)
npx skills add docker/skills --skill docker-compose-patterns --yes

# Install every skill into one agent
npx skills add docker/skills --skill '*' --agent codex --yes

# Install every skill into every detected agent
npx skills add docker/skills --all

# Keep installed skills current
npx skills update
```

### Install as a plugin

Plugin installs are managed by each agent's marketplace, so updates arrive through the agent rather than through `npx skills update`. For Claude Code and Codex, the rendered plugin manifest version is the update gate and advances with a versioned distribution release.

**Claude Code**
```bash
/plugin marketplace add docker/skills
/plugin install docker-skills@docker
```
See [Claude Code plugins docs](https://code.claude.com/docs/en/discover-plugins)

**OpenAI Codex**
```bash
codex plugin marketplace add docker/skills
codex plugin add docker-skills@docker
```
Start a new Codex session after installing. See [Codex skills docs](https://developers.openai.com/codex/skills)

**GitHub Copilot CLI**
```bash
/plugin marketplace add docker/skills
/plugin install docker-skills@docker
```
See [Copilot CLI plugins docs](https://docs.github.com/en/copilot/how-tos/copilot-cli/customize-copilot/plugins-finding-installing)

**Gemini CLI**
```bash
gemini extensions install https://github.com/docker/skills
```
See [Gemini CLI extensions docs](https://github.com/google-gemini/gemini-cli/blob/main/docs/extensions/index.md)

**Cursor**

Add `docker/skills` as a marketplace from Cursor's plugin settings (**Customize** → **Plugins** → import from repository), or use the `skills` CLI above with `--agent cursor`. See [Cursor plugins docs](https://cursor.com/docs/plugins)

### Clone or copy

Clone the repo and point your agent at the `skills/` directory, or copy the skill folders you want into the agent's skill directory. The repo already contains symlinks for the common discovery paths, so cloning it into a project root is enough for the agents below to pick the skills up.

```bash
git clone https://github.com/docker/skills.git
```

| Agent | Skill directory | Docs |
|-------|-----------------|------|
| Claude Code | `~/.claude/skills/` | [docs](https://code.claude.com/docs/en/skills) |
| OpenAI Codex | `~/.codex/skills/` or `~/.agents/skills/` | [docs](https://developers.openai.com/codex/skills) |
| Cursor | `~/.cursor/skills/` | [docs](https://cursor.com/docs/context/skills) |
| GitHub Copilot | `.github/skills/` in the project | [docs](https://docs.github.com/en/copilot/how-tos/copilot-cli/customize-copilot/plugins-finding-installing) |
| Gemini CLI | `~/.gemini/skills/` | [docs](https://github.com/google-gemini/gemini-cli/blob/main/docs/extensions/index.md) |
| OpenCode | `~/.config/opencode/skills/` | [docs](https://opencode.ai/docs/skills/) |

## Releases

`main` is the rolling development channel and continuously publishes the mutable
`docker/skills-content:edge` image. Consumers that use the `skills` CLI, clone
or copy from `main`, or follow `edge` receive skill updates as they merge. Tags
such as `v0.1.0` are immutable, pinned distribution snapshots whose version
matches the top-level `version` in [`catalog.yaml`](catalog.yaml). Claude Code
and Codex plugin updates are gated by the distribution version rendered into
their manifests, so those marketplaces advance with a versioned release.

Maintainers create versioned releases as needed with the manually dispatched Release
workflow after changes merge to `main`. The workflow builds the multi-architecture
`docker/skills-content:vX.Y.Z` image and creates a draft GitHub release containing
`catalog.yaml`, `skills.sh.json`, and the image digest. A maintainer inspects and
publishes that draft; the workflow never publishes it automatically. Follow a
rolling channel for frequent updates. For controlled, reproducible updates, pin
the release tag—or the image digest when byte-for-byte immutability is
required—and periodically review and advance that pin on your own cadence.

## Standards & Compatibility

Every catalogued skill follows the [Agent Skills specification](https://agentskills.io/specification)
and passes the upstream [`skills-ref` validator](https://github.com/agentskills/agentskills/tree/main/skills-ref).
Repository-specific files such as `skill.yaml`, `agents/openai.yaml`, assets, checks,
and evaluation runbooks add distribution and quality conventions beyond the core
specification. Discovery and installation support varies by agent; consult the
[Agent Skills client directory](https://agentskills.io/clients) for current client
capabilities.

## Local Development

Prerequisites: [Task](https://taskfile.dev/) and Docker.

```bash
task             # Run the complete CI/release validation suite
task validate    # Check skill structure, frontmatter, and manifests; run validator tests
task eval        # Static asset and verification-snippet checks, not live agent evals
task links       # Check local Markdown links and heading anchors
task catalog     # Regenerate catalog tables, skills.sh.json, and plugin manifest versions from catalog.yaml
task docs:check  # Lint/build docs and validate canonicals, relative links, and llms.txt
task docs:serve  # Preview the edge docs at http://localhost:1313/skills/
```

## Repository Structure

```
docs/                 — Human-facing Hugo documentation for the edge GitHub Pages site
skills/               — Canonical skill directories (SKILL.md + supporting files)
.agents/skills        — Symlink to skills/ (Codex, cross-agent convention)
.claude/skills        — Symlink to skills/ (Claude Code)
.gemini/skills        — Symlink to skills/ (Gemini CLI)
.github/skills        — Symlink to skills/ (Copilot CLI)
catalog.yaml          — Distribution version and skill registry: product families, skill ids, per-skill versions, and status
skills.sh.json        — Product-grouped index read by the skills CLI (generated from catalog.yaml)
scripts/render_catalog.py — Renders catalog tables, skills.sh.json, and plugin manifest versions from catalog.yaml
evals/                — Evaluation runbooks
.claude-plugin/       — Claude Code plugin + marketplace manifests
.codex-plugin/        — Codex plugin manifest
.agents/plugins/      — Codex marketplace manifest
.cursor-plugin/       — Cursor plugin + marketplace manifests
.github/plugin/       — Copilot CLI plugin + marketplace manifests
gemini-extension.json — Gemini CLI extension manifest
Taskfile.yml          — CI and validation tasks
scripts/ci.sh         — Shared CI and release validation entrypoint
```

## License

This project is licensed under the Apache License 2.0 — see [LICENSE](LICENSE) for details.

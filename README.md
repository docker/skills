# Docker Skills for AI Coding Agents

[![CI](https://github.com/docker/skills/actions/workflows/ci.yml/badge.svg?branch=main)](https://github.com/docker/skills/actions/workflows/ci.yml)
[![Agent Skills](https://img.shields.io/badge/Agent%20Skills-Specification-blue)](https://agentskills.io/specification)
[![License](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](LICENSE)
[![skills.sh](https://skills.sh/b/docker/skills)](https://skills.sh/docker/skills)
[![OpenSSF Scorecard](https://api.scorecard.dev/projects/github.com/docker/skills/badge)](https://scorecard.dev/viewer/?uri=github.com/docker/skills)
[![Release](https://img.shields.io/github/v/tag/docker/skills?sort=semver&label=release)](https://github.com/docker/skills/releases)

Docker-authored knowledge skills that improve AI coding agent output for Docker-related tasks. Skills are authored once as portable `SKILL.md` directories and discovered automatically by any compliant agent through standard skill paths.

The installation steps below are self-contained; the catalog-generated inventory also records Docker Docs guidance for each distribution surface.

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

Each skill triggers directly from its own description; there is no entry-point skill to load first.
When a task spans several skills, load them in the order their outputs feed each other: `docker-project-foundations` before `docker-build-strategies` or `docker-compose-patterns` when the project has no Docker setup yet; `docker-build-strategies` before `docker-compose-patterns` when both a `Dockerfile` and a `compose.yaml` change; `docker-sandboxes-lifecycle` before `docker-sandboxes-network-credentials`, and both before `docker-sandboxes-env` or `docker-sandboxes-kits`; `docker-agent-config` before `docker-agent-run` before `docker-agent-deploy`.
Skills marked *experimental* cover features whose schemas may still change.

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

# Pin a skill to a reviewed release (replace vX.Y.Z with a release tag)
npx skills add https://github.com/docker/skills/tree/vX.Y.Z \
  --skill docker-compose-patterns --yes
```

### Install as a plugin

Plugin installs are managed by each agent's marketplace, so updates arrive through the agent rather than through `npx skills update`.

**Claude Code** (run in the Claude Code prompt):
```text
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

**GitHub Copilot CLI** (run in the Copilot CLI prompt):
```text
/plugin marketplace add docker/skills
/plugin install docker-skills@docker
```
See [Copilot CLI plugins docs](https://docs.github.com/en/copilot/how-tos/copilot-cli/customize-copilot/plugins-finding-installing)

**Gemini CLI**
```bash
gemini extensions install https://github.com/docker/skills
```
Restart Gemini CLI to discover the installed skills. See [Gemini CLI extensions docs](https://github.com/google-gemini/gemini-cli/blob/main/docs/extensions/index.md)

**Cursor**

Select the `docker-skills` plugin from Cursor's marketplace where available, or use the `skills` CLI above with `--agent cursor`. Importing a repository into a team marketplace requires team administrator access. See [Cursor plugins docs](https://cursor.com/docs/plugins)

### Docker Sandboxes

Docker Sandboxes also offers experimental product-native installation with the standalone `sbx` CLI:

```bash
sbx skills add docker/skills --skill docker-compose-patterns
sbx skills ls
sbx skills update
```

Omit `--skill` to install every skill. The shared skill store makes installed skills available to sandboxes on their next start; check `sbx skills --help` because this experimental interface may change. See the [Docker Docs installation guide](https://docs.docker.com/ai/skills/install/#docker-sandboxes) for more detail.

### Clone or copy

For a reviewed snapshot, choose a tag from [Docker Skills releases](https://github.com/docker/skills/releases) and replace `vX.Y.Z` below. Clone into a separate directory, then copy complete skill folders from its `skills/` directory into the appropriate agent path in the table. Alternatively, if the cloned repository **itself** is your project root, its discovery symlinks let supported agents find skills without copying; a clone inside a project subdirectory is not a discovery path. Manual copies have no managed updater, so replace complete folders when updating.

```bash
git clone --branch vX.Y.Z --depth 1 https://github.com/docker/skills.git docker-skills

# Example: install one skill for Claude Code (use another path from the table as needed)
mkdir -p ~/.claude/skills
cp -R docker-skills/skills/docker-compose-patterns ~/.claude/skills/
```

| Agent | Skill directory | Docs |
|-------|-----------------|------|
| Claude Code | `~/.claude/skills/` | [docs](https://code.claude.com/docs/en/skills) |
| OpenAI Codex | `~/.codex/skills/` or `~/.agents/skills/` | [docs](https://developers.openai.com/codex/skills) |
| Cursor | `~/.cursor/skills/` | [docs](https://cursor.com/docs/context/skills) |
| GitHub Copilot | `.github/skills/` in the project | [docs](https://docs.github.com/en/copilot/concepts/agents/about-agent-skills) |
| Gemini CLI | `~/.gemini/skills/` | [docs](https://github.com/google-gemini/gemini-cli/blob/main/docs/cli/skills.md) |
| Google Antigravity | `.agents/skills/` in the project or `~/.gemini/antigravity/skills/` | [Docker Docs](https://docs.docker.com/ai/skills/install/#google-antigravity) |
| OpenCode | `~/.config/opencode/skills/` | [docs](https://opencode.ai/docs/skills/) |

Google Antigravity uses the `skills` CLI (`--agent antigravity`) or manual copy; it has no dedicated plugin manifest. See [Docker Docs guidance for Antigravity](https://docs.docker.com/ai/skills/install/#google-antigravity) for more detail. Docker Agent consumes skills installed in supported project or user paths.

## Published surfaces

This inventory is generated from [`catalog.yaml`](catalog.yaml). It records the canonical Docker Docs installation links for each surface; the instructions above provide a self-contained installation path.

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

## Releases

`main` is the rolling development channel; skills installed from it through the
`skills` CLI or a clone or copy can be refreshed as updates merge. Tags such as
`v0.3.0` are immutable, reviewed snapshots. Pin a release tag for reproducible
installs and periodically review and advance that pin. Claude Code and Codex
plugin updates are gated by the distribution version rendered into their
manifests, so those marketplaces advance with a versioned release. See the
[releases](https://github.com/docker/skills/releases) for published tags.

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
task catalog:check # Verify generated catalog files are current
```

## Repository Structure

```
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

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for the contribution process and DCO
sign-off requirements. When changing a skill, keep its catalog and skill
versions synchronized; [AGENTS.md](AGENTS.md) summarizes the repository
contracts. Run `task` from the repository root before submitting a change.

## License

This project is licensed under the Apache License 2.0 — see [LICENSE](LICENSE) for details.

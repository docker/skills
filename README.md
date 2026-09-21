# Docker Skills for AI Coding Agents

Docker-authored knowledge skills that improve AI coding agent output for Docker-related tasks. Skills are authored once as portable `SKILL.md` directories and discovered automatically by any compliant agent through standard skill paths.

## Skills

- **docker-project-foundations** — Guidance for initializing and structuring a Dockerized project
- **docker-compose-patterns** — Patterns for robust, maintainable Docker Compose configurations
- **docker-build-strategies** — Strategies for efficient, secure, and optimized Docker image builds
- **docker-agent-config** — Authoring agent.yaml configs for Docker Agent (models, providers, toolsets, multi-agent teams)
- **docker-agent-run** — Running and operating Docker Agent locally (safety modes, sandbox, aliases, worktrees)
- **docker-agent-deploy** — Serving, sharing, and evaluating Docker Agents (MCP/API/A2A/chat servers, OCI distribution, eval/CI gating)
- **docker-sandboxes-lifecycle** — Standalone sbx lifecycle, workspace mounts, clone isolation, and safe cleanup
- **docker-sandboxes-network-credentials** — sbx egress policy, proxy credentials, registry scopes, and OAuth passthrough boundaries
- **docker-sandboxes-env** — Experimental sbxenv.yaml environments, host hooks, and approval plans
- **docker-sandboxes-kits** — Experimental sandbox/mixin kits, composition, and signed distribution

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

Plugin installs are managed by each agent's marketplace, so updates arrive through the agent rather than through `npx skills update`.

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

## Local Development

Prerequisites: [Task](https://taskfile.dev/) and Docker.

```bash
task             # Run the complete CI/release validation suite
task validate    # Check skill structure, frontmatter, and manifests; run validator tests
task eval        # Static asset and verification-snippet checks, not live agent evals
task links       # Check local Markdown links and heading anchors
```

## Repository Structure

```
skills/               — Canonical skill directories (SKILL.md + supporting files)
.agents/skills        — Symlink to skills/ (Codex, cross-agent convention)
.claude/skills        — Symlink to skills/ (Claude Code)
.gemini/skills        — Symlink to skills/ (Gemini CLI)
.github/skills        — Symlink to skills/ (Copilot CLI)
catalog.yaml          — Skill registry
skills.sh.json        — Product-grouped index read by the skills CLI (validated against catalog.yaml)
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

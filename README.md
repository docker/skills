# Docker Skills for AI Coding Agents

Docker-authored knowledge skills that improve AI coding agent output for Docker-related tasks. Skills are authored once as portable `SKILL.md` directories and discovered automatically by any compliant agent through standard skill paths.

## Skills

- **docker-project-foundations** — Guidance for initializing and structuring a Dockerized project
- **docker-compose-patterns** — Patterns for robust, maintainable Docker Compose configurations
- **docker-build-strategies** — Strategies for efficient, secure, and optimized Docker image builds
- **docker-desktop-preflight** — Detect and diagnose Docker Desktop configuration and governance blockers (resource limits, Enhanced Container Isolation, Registry Access Management, enforced sign-in, file sharing, proxies, Kubernetes) before/while running container actions — works with governance, never around it.

## Installation

### Clone and use directly

Clone this repo into your project or home directory. Symlinks in `.claude/skills/`, `.agents/skills/`, `.gemini/skills/`, and `.github/skills/` ensure every major agent discovers the skills automatically:

```bash
git clone https://github.com/docker/skills.git
```

### Install via agent plugin/extension

**Claude Code**
```bash
# Add the Docker marketplace and install the plugin:
/plugin marketplace add https://github.com/docker/skills.git
/plugin install docker-skills@docker

# Or install directly from the repo:
/plugin install https://github.com/docker/skills.git
```
See [Claude Code plugins docs](https://code.claude.com/docs/en/discover-plugins)

**OpenAI Codex**
```bash
# Use the built-in skill installer:
$skill-installer https://github.com/docker/skills.git

# Or copy skills manually:
cp -r skills/docker-project-foundations ~/.agents/skills/
cp -r skills/docker-compose-patterns ~/.agents/skills/
cp -r skills/docker-build-strategies ~/.agents/skills/
cp -r skills/docker-desktop-preflight ~/.agents/skills/
```
See [Codex skills docs](https://developers.openai.com/codex/skills)

**Gemini CLI**
```bash
gemini extensions install https://github.com/docker/skills
```
See [Gemini CLI extensions docs](https://github.com/google-gemini/gemini-cli/blob/main/docs/extensions/index.md)

**GitHub Copilot CLI**
```bash
# Add the Docker marketplace and install the plugin:
/plugin marketplace add https://github.com/docker/skills.git
/plugin install docker-skills@docker

# Or install directly from the repo:
copilot plugin install https://github.com/docker/skills.git
```
See [Copilot CLI plugins docs](https://docs.github.com/en/copilot/how-tos/copilot-cli/customize-copilot/plugins-finding-installing)

## Local Development

Prerequisites: [Task](https://taskfile.dev/) and Python 3 with PyYAML (`pip install pyyaml`).

```bash
task validate    # Check skill structure, frontmatter, and manifests
```

## Repository Structure

```
skills/               — Canonical skill directories (SKILL.md + supporting files)
.agents/skills        — Symlink to skills/ (Codex, cross-agent convention)
.claude/skills        — Symlink to skills/ (Claude Code)
.gemini/skills        — Symlink to skills/ (Gemini CLI)
.github/skills        — Symlink to skills/ (Copilot CLI)
catalog.yaml          — Skill registry
evals/                — Evaluation runbooks
.claude-plugin/       — Claude Code plugin + marketplace manifests
.github/plugin/       — Copilot CLI plugin + marketplace manifests
gemini-extension.json — Gemini CLI extension manifest
Taskfile.yml          — Validation tasks
```

## License

This project is licensed under the Apache License 2.0 — see [LICENSE](LICENSE) for details.

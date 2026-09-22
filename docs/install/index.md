---
title: Install Docker Skills
canonical: https://docs.docker.com/ai/skills/install/
weight: 10
---

# Install Docker Skills

Docker Skills are portable instruction packages that help compatible AI coding
agents produce safer, more accurate Docker changes. For most users, the
[`skills` CLI](https://skills.sh) is the simplest way to discover supported
agents, choose skills, and keep them current.

## Install with the skills CLI

Run the interactive installer from the project where you want to use Docker
Skills:

```console
npx skills add docker/skills
```

The installer lets you select skills and target agents. A project installation
is available only in that project and is suitable for sharing with a team. Add
`--global` (or `-g`) for a user-level installation across projects.

Useful forms include:

```console
# Preview the catalog without installing
npx skills add docker/skills --list

# Install one skill in the current project without prompts
npx skills add docker/skills --skill docker-compose-patterns --yes

# Install one skill for a supported agent at user scope
npx skills add docker/skills --skill docker-build-strategies \
  --agent claude-code --global --yes

# Install every skill into every supported agent
npx skills add docker/skills --all
```

Use repeated `--skill` and `--agent` options to select more than one. The CLI
uses symlinks by default so agents share a canonical copy; add `--copy` only for
a client or filesystem that cannot follow symlinks.

## Choose skills

Install the smallest set that covers your work. This keeps routing focused and
makes updates easier to review.

- Start new Docker projects with `docker-project-foundations`.
- Add `docker-build-strategies` for Dockerfile builds, caching, image size, and
  hardening.
- Add `docker-compose-patterns` for multi-container development.
- Add the Docker Agent or Docker Sandboxes skills only when you use those
  products. The catalog labels skills for experimental product features.
- Add `docker-destructive-guardrails` when an agent may perform Docker cleanup
  or deletion.

Browse the complete [skill catalog](../catalog/index.md) for routing details.
You do not need an entry-point skill: compatible agents load each installed
skill when its description matches your request.

## Verify the installation

List the project installation:

```console
npx skills list
```

For a user-level installation, use:

```console
npx skills list --global
```

Then start a new agent session and ask for a matching task, such as "Review my
Dockerfile for cache efficiency and non-root execution." Some clients discover
skills only when a session starts.

## Update or remove skills

Update project skills interactively:

```console
npx skills update
```

Use `npx skills update --global` for user-level skills, or name one or more
skills to update only those entries.

Remove one project skill with:

```console
npx skills remove docker-compose-patterns
```

Add `--global` to remove a user-level installation. Removal changes agent links,
so review the interactive selection or name skills explicitly before confirming.

## Native marketplaces and extensions

A native plugin or extension can be preferable when your client manages updates
and discovery itself. These verified installation surfaces are available:

### Claude Code

In Claude Code, add Docker's marketplace and install its plugin:

```text
/plugin marketplace add docker/skills
/plugin install docker-skills@docker
```

See the [Claude Code plugin documentation](https://code.claude.com/docs/en/discover-plugins).

### GitHub Copilot CLI

In Copilot CLI, add the marketplace and install the plugin:

```text
/plugin marketplace add docker/skills
/plugin install docker-skills@docker
```

See the [Copilot CLI plugin documentation](https://docs.github.com/en/copilot/how-tos/copilot-cli/customize-copilot/plugins-finding-installing).

### Gemini CLI

Install the repository as a Gemini CLI extension:

```console
gemini extensions install https://github.com/docker/skills
```

See the [Gemini CLI extension documentation](https://github.com/google-gemini/gemini-cli/blob/main/docs/extensions/index.md).

### Cursor and other agents

Use Cursor's documented plugin settings to import `docker/skills`, or use the
`skills` CLI with `--agent cursor`; see the [Cursor plugin documentation](https://cursor.com/docs/plugins).
Other compatible clients should use the `skills` CLI or their documented skill
directory. Native interfaces change independently; this guide does not claim
unverified marketplace commands for Codex, Cursor, or team-managed Claude
deployments.

## Next steps

For release pinning, Docker Agent, experimental Docker Sandboxes support, the
OCI image, and manual installation, see [Advanced installation](../advanced-install/index.md).
For examples of how agents select and combine skills, see [Get started](../getting-started/index.md).

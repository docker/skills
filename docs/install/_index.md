---
title: Install Docker Skills
canonical: https://docs.docker.com/ai/skills/install/
weight: 10
---

# Install Docker Skills

Docker Skills can reach an agent through several equal, supported distribution
models. Choose the model your client or organization manages; the `skills` CLI
is one option, not a prerequisite.

## Choose a distribution model

- [Native marketplaces](native-marketplaces.md) let a client manage a Docker
  plugin and its updates.
- [Extensions](extensions.md) package the repository for an extension-capable
  client.
- [skills CLI](skills-cli.md) installs selected skills across compatible clients
  at project or user scope.

Docker product behavior and source-level fallbacks are documented separately:

- [Docker products](docker-products.md) covers Docker Agent as a consumer and
  experimental Docker Sandboxes product-native installation.
- [Sources and fallback](sources.md) covers OCI, Git, and manual copy. These are
  inputs or escape hatches, not general distribution models.

## Published surfaces

This inventory is generated from `catalog.yaml`. Every published plugin or
extension manifest maps to exactly one surface here.

<!-- distributions-start -->
### Native marketplaces

- **Claude Code marketplace.** Client-managed plugin installation from Docker's marketplace.
- **GitHub Copilot CLI marketplace.** Client-managed plugin installation from Docker's marketplace.
- **Cursor marketplace.** Client-managed installation through Cursor's documented plugin interface.
- **Codex marketplace.** Client-managed installation where the Codex marketplace is available.

### Extensions

- **Gemini CLI extension.** Repository-backed extension installation managed by Gemini CLI.

### skills CLI

- **skills CLI.** Cross-client project or user installation with explicit skill selection.

### Docker products

- **Docker Sandboxes *(experimental)*.** Product-native installation into the shared sandbox skill store.
- **Docker Agent.** Consumer of skills installed in supported project or user paths.

### Sources and fallback

- **OCI content image.** Published content artifact for consumers that can extract OCI files.
- **Git clone or manual copy.** Auditable fallback when no managed installer fits the client.
<!-- distributions-end -->

## Choose skills

Install the smallest set that covers your work. Start new Docker projects with
`docker-project-foundations`; add `docker-build-strategies` for image builds and
hardening, `docker-compose-patterns` for multi-container applications, and
`docker-destructive-guardrails` when an agent may clean up Docker state. Add
Docker Agent or Docker Sandboxes skills only when you use those products.

Browse the complete [skill catalog](../catalog/index.md). Compatible agents load
installed skills when their descriptions match a request; no entry-point skill
is required.

## Verify the result

Use the verification procedure on the selected model page, then start a new
agent session and ask for a matching task, such as “Review my Dockerfile for
cache efficiency and non-root execution.” Many clients scan for skills only at
session start.

## Related links

- [Get started](../getting-started/index.md)
- [Skill catalog](../catalog/index.md)
- [Docker Skills releases](https://github.com/docker/skills/releases)

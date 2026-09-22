---
title: Skill catalog
canonical: https://docs.docker.com/ai/skills/catalog/
weight: 20
---

# Docker Skills catalog

The catalog groups Docker-authored skills by product. Stable skills cover
released interfaces; experimental skills cover behavior that may still change.

<!-- catalog-start -->
Latest distribution release: [`v0.2.0`](https://github.com/docker/skills/releases/tag/v0.2.0).

## [Dockerfile & Build](https://docs.docker.com/build/)

Containerize a project and write, optimize, and harden Dockerfiles and images.

- [`docker-project-foundations`](https://github.com/docker/skills/tree/main/skills/docker-project-foundations) **v0.2.0.** Guidance for initializing and structuring a Dockerized project.
- [`docker-build-strategies`](https://github.com/docker/skills/tree/main/skills/docker-build-strategies) **v0.1.0.** Strategies for efficient, secure, and optimized Docker image builds.

## [Docker Compose](https://docs.docker.com/compose/)

Wire multi-container stacks with robust, maintainable Compose configurations.

- [`docker-compose-patterns`](https://github.com/docker/skills/tree/main/skills/docker-compose-patterns) **v0.1.1.** Patterns for robust, maintainable Docker Compose configurations.

## [Docker Sandboxes](https://docs.docker.com/ai/sandboxes/)

Run AI coding agents in isolated microVMs with the sbx CLI, including network policy, credentials, environments, and kits.

- [`docker-sandboxes-lifecycle`](https://github.com/docker/skills/tree/main/skills/docker-sandboxes-lifecycle) **v0.1.0.** Create, reattach to, and tear down local `sbx` sandboxes; choose workspace bind-mount vs --clone isolation.
- [`docker-sandboxes-network-credentials`](https://github.com/docker/skills/tree/main/skills/docker-sandboxes-network-credentials) **v0.1.0.** Configure sandbox network egress policy and provision service/registry credentials safely through the proxy-injection model.
- [`docker-sandboxes-env`](https://github.com/docker/skills/tree/main/skills/docker-sandboxes-env) **v0.1.0.** **Experimental.** Author, plan, and run declarative sbxenv.yaml environments (workspace, kits, args, host lifecycle hooks, secrets/registries/bindings, ports) for Docker Sandboxes.
- [`docker-sandboxes-kits`](https://github.com/docker/skills/tree/main/skills/docker-sandboxes-kits) **v0.1.0.** **Experimental.** Author, validate, package, sign, and compose reusable sandbox/mixin kits (spec.yaml, schema v2).

## [Docker Agent](https://docs.docker.com/ai/docker-agent/)

Author, run, and ship AI agents with Docker Agent, from agent.yaml to serving and distribution.

- [`docker-agent-config`](https://github.com/docker/skills/tree/main/skills/docker-agent-config) **v0.1.0.** Reference and rules for authoring agent.yaml configs for Docker Agent (cagent) — agents, models, providers, toolsets, and multi-agent teams.
- [`docker-agent-run`](https://github.com/docker/skills/tree/main/skills/docker-agent-run) **v0.1.0.** Rules for running Docker Agent locally — safety/approval modes, sandbox isolation, aliases, worktrees, and troubleshooting a run.
- [`docker-agent-deploy`](https://github.com/docker/skills/tree/main/skills/docker-agent-deploy) **v0.1.0.** Rules for exposing Docker Agents as servers, distributing them via OCI registries, and evaluating them for regressions in CI.

## Cross-Product

Guardrails and policies that apply across every Docker skill product.

- [`docker-destructive-guardrails`](https://github.com/docker/skills/tree/main/skills/docker-destructive-guardrails) **v0.1.0.** Cross-product policy for confirming irreversible or destructive Docker operations before running them.
<!-- catalog-end -->

## Choosing skills

You do not need to load an entry-point skill. Each skill's description tells a
compatible agent when to use it. When a task crosses product boundaries, the
agent can load several skills and apply them in dependency order.

Get started with the [installation guide](../install/_index.md), or learn how
agents [select and combine skills](../getting-started/index.md).

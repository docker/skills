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

## Quick start

Install interactively with the supported [`skills` CLI](https://skills.sh):

```console
npx skills add docker/skills
```

The authoritative [installation guide](https://docker.github.io/skills/install/)
covers skill selection, project and user scope, supported native plugins,
release pinning, updates, removal, verification, and troubleshooting.

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
task docs:check
```

The docs site is under [`docs/`](docs/), canonical skill content is under
[`skills/`](skills/), and repository contracts are summarized in
[`AGENTS.md`](AGENTS.md).

## License

This project is licensed under the Apache License 2.0. See [LICENSE](LICENSE).

---
name: docker
description: Use this skill first for any Docker-related task when it is not yet clear which specific Docker skill applies — writing or fixing a Dockerfile, shrinking or hardening an image, containerizing a project, wiring services in compose.yaml, isolating a coding agent in a Docker Sandbox (sbx), or authoring or running a Docker Agent (agent.yaml, docker agent run/serve/share/eval). It maps the request to the skill that owns it and contains no Docker guidance of its own.
license: Apache-2.0
---

# Docker Skills: Start Here

## Overview

This skill is a router. It does not teach Docker; it tells you which of the Docker skills in this catalog to load for the task in front of you. Read the routing table below, load the matching skill, and follow that skill's guidance. When several rows match, load every matching skill in the order listed under [Multi-skill tasks](#multi-skill-tasks).

## When to use this skill

Activate this skill when:

- The task involves Docker in any form and you have not yet decided which Docker skill to load
- The user mentions containers, images, a Dockerfile, Compose, Docker Sandboxes, `sbx`, Docker Agent, `cagent`, or `agent.yaml` without a clear single concern
- The task spans several Docker concerns (for example "Dockerize this app and run it in a sandbox") and you need the load order

## Do not use this skill when

Do not use this skill when:

- You already know the specific Docker skill that applies; load it directly
- The task does not involve Docker, Docker Sandboxes, or Docker Agent

## Core guidance

### Routing table

| If the user wants to… | Load |
|-----------------------|------|
| Dockerize a project that has no Docker setup yet, or add Compose-managed databases and caches for local development | `docker-project-foundations` |
| Write, review, shrink, speed up, or harden a `Dockerfile` or image (multi-stage builds, caching, `.dockerignore`, non-root users) | `docker-build-strategies` |
| Create, edit, or debug `compose.yaml` or `compose.override.yaml` (services, health checks, `depends_on`, volumes, networks, Compose Watch) | `docker-compose-patterns` |
| Create, run, reattach to, list, stop, or remove a Docker Sandbox with `sbx`, or choose bind-mount vs clone isolation | `docker-sandboxes-lifecycle` |
| Control what a sandbox can reach on the network, or give it service, registry, or OAuth credentials | `docker-sandboxes-network-credentials` |
| Author or run a declarative `sbxenv.yaml` environment (`sbx env`), including host lifecycle hooks and approval plans | `docker-sandboxes-env` |
| Author, validate, package, sign, or compose a sandbox or mixin kit `spec.yaml` (`sbx kit`) | `docker-sandboxes-kits` |
| Write or edit an `agent.yaml` for Docker Agent (agents, models, providers, toolsets, MCP servers, sub-agents) | `docker-agent-config` |
| Run a Docker Agent locally, pick a safety or approval mode, use `--sandbox`, set up aliases, or troubleshoot a run | `docker-agent-run` |
| Expose a Docker Agent as an MCP, HTTP, A2A, ACP, or chat server, share it through an OCI registry, or gate it with `docker agent eval` | `docker-agent-deploy` |

### Multi-skill tasks

Load the skills in this order so that each one's output feeds the next:

1. `docker-project-foundations` before `docker-build-strategies` or `docker-compose-patterns` when the project has no Docker setup yet.
2. `docker-build-strategies` before `docker-compose-patterns` when both a `Dockerfile` and a `compose.yaml` change.
3. `docker-sandboxes-lifecycle` before `docker-sandboxes-network-credentials`, and both before `docker-sandboxes-env` or `docker-sandboxes-kits`.
4. `docker-agent-config` before `docker-agent-run`, and `docker-agent-run` before `docker-agent-deploy`.
5. When a Docker Agent runs with `--sandbox`, load `docker-sandboxes-lifecycle` for the sandbox itself and `docker-agent-run` for the agent flags.

### Experimental skills

`docker-sandboxes-env` and `docker-sandboxes-kits` cover experimental `sbx` features whose schemas may still change. Tell the user the feature is experimental when you route to them.

## Related skills

This skill routes to every other skill in the catalog:

- `docker-project-foundations` — initial Docker scaffold and Compose-managed development dependencies
- `docker-build-strategies` — Dockerfile and image build optimization and hardening
- `docker-compose-patterns` — Compose service wiring, readiness, volumes, networks, and overrides
- `docker-sandboxes-lifecycle` — `sbx` sandbox lifecycle and workspace isolation
- `docker-sandboxes-network-credentials` — sandbox network policy and credentials
- `docker-sandboxes-env` — declarative `sbxenv.yaml` environments
- `docker-sandboxes-kits` — sandbox and mixin kits
- `docker-agent-config` — `agent.yaml` authoring for Docker Agent
- `docker-agent-run` — running Docker Agents locally, safety modes, and troubleshooting
- `docker-agent-deploy` — serving, sharing, and evaluating Docker Agents

## References

This skill ships no reference files. The detailed material lives in the skill you route to.

## Assets

This skill ships no assets. Templates and examples live in the skill you route to.

## Checks

This skill ships no verification runbook; run the checks of the skill you route to. Its routing coverage is verified by `task validate`, which fails when a skill listed in `catalog.yaml` is missing from this file.

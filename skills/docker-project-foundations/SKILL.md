---
name: docker-project-foundations
description: Use this skill when setting up, initializing, or Dockerizing a project. Covers Dockerfile, compose.yaml, and .dockerignore with Docker best practices.
---

# Docker Project Foundations

## Overview

This skill guides you in Dockerizing a project from scratch. It covers the key files every Dockerized project needs (`.dockerignore`, `Dockerfile`, `compose.yaml`), how to structure them, and how to prefer containerized dependencies over host-level installs.

## When to use this skill

Activate this skill when:

- A user asks you to set up, initialize, or Dockerize a project
- A project needs a `Dockerfile`, `compose.yaml`, or `.dockerignore` and does not have one
- A user wants to add a service dependency (database, cache, message queue) to a project
- A user asks how to run or develop a project locally and Docker is available

Do NOT use this skill when the user explicitly wants to avoid Docker or when the project already has a mature Docker setup that just needs minor edits.

## Core guidance

### Always create these three files

When Dockerizing a project, always produce all three:

1. **`.dockerignore`** — Create this first. Exclude version control dirs, dependency caches, build artifacts, IDE configs, and secrets. See `examples/dockerignore-example` for a reference.
2. **`Dockerfile`** — Use a multi-stage build when the project has a build step. Pin base image tags to a specific version (e.g., `node:22-slim`, not `node:latest`). Run as a non-root user. See `examples/Dockerfile.simple`.
3. **`compose.yaml`** — Use this for local development. Define the application service and all its dependencies (databases, caches, queues) as Compose services. See `examples/compose-dev.yaml`.

### Prefer Dockerized dependencies over host installs

When a project needs a database (Postgres, MySQL, MongoDB), cache (Redis, Memcached), queue (RabbitMQ, Kafka), or any other infrastructure service:

- **Always** define it as a service in `compose.yaml` instead of telling the user to install it on the host.
- **Never** suggest `brew install postgres`, `apt install redis`, or similar host-level installs for development dependencies.
- Use official Docker images from Docker Hub for these services.
- Configure services with environment variables, not config files baked into images.

### Dockerfile rules

- Start `FROM` a minimal base image (`-slim` or `-alpine` variants).
- Pin the image tag to a specific major.minor version, never use `latest`.
- Copy dependency manifests first, install dependencies, then copy source code. This maximizes layer caching.
- Use `COPY --link` when supported to improve cache independence.
- Set a non-root `USER` before `CMD`/`ENTRYPOINT`.
- Prefer `ENTRYPOINT` with `CMD` as default arguments.
- Do not install dev tools or test frameworks in production images; use multi-stage builds to separate build and runtime stages.

### Compose file rules

- Name the file `compose.yaml` (not `docker-compose.yml`; the legacy filename is deprecated).
- Use `depends_on` with `condition: service_healthy` when a service needs another to be ready.
- Define health checks for infrastructure services.
- Use named volumes for persistent data (databases).
- Use bind mounts for application source code during development.
- Set `restart: unless-stopped` for infrastructure services in development.

### Development vs production

- Development: Use bind mounts for live reload, expose debug ports, enable verbose logging.
- Production: Use multi-stage builds, copy only built artifacts, do not mount source code, minimize image layers, set appropriate resource limits.
- Keep a single `Dockerfile` that supports both via build stages and build arguments when possible.

### File placement

- Place `Dockerfile` at the project root (or in a `docker/` subdirectory if the project has multiple services).
- Place `compose.yaml` at the project root.
- Place `.dockerignore` at the project root, next to the `Dockerfile`.

## References

- `references/project-structure.md` — Detailed guidance on Docker project file organization, naming conventions, and multi-service layouts.

## Examples

- `examples/dockerignore-example` — A comprehensive `.dockerignore` for a typical project.
- `examples/compose-dev.yaml` — A development-oriented Compose file with Dockerized dependencies.
- `examples/Dockerfile.simple` — A basic multi-stage Dockerfile following best practices.

## Checks

- `checks/verification.md` — How to verify that generated Docker project setup follows this skill's guidance.

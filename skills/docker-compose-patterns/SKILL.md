---
name: docker-compose-patterns
description: Use this skill when creating or modifying Docker Compose configurations. Covers service definitions, health checks, volumes, networks, and development overrides.
---

# Docker Compose Patterns

## Overview

This skill provides rules for generating correct, production-ready Docker Compose configurations. Use it when creating or modifying `compose.yaml` files to ensure proper service dependencies, health checks, volume management, networking, and environment variable handling.

## When to use this skill

Activate this skill when:

- Creating a new `compose.yaml` for a project
- Adding or modifying services in an existing Compose file
- Setting up development overrides with `compose.override.yaml`
- Debugging service startup ordering or connectivity issues

## Core guidance

### File naming

Use `compose.yaml` as the canonical filename. Do not use `docker-compose.yml` or `docker-compose.yaml` — those are legacy names.

### Service definitions

- Give services clear, lowercase names that reflect their role: `web`, `db`, `cache`, `worker`.
- Always pin image tags to a specific version. Never use `latest` or omit the tag.
- Set `restart: unless-stopped` for services that should survive host reboots in non-development environments.
- Add `container_name` only when external tools need a predictable name. Otherwise, let Compose generate names.

### Dependency modeling

- Use `depends_on` with `condition: service_healthy` for services that must be ready before dependents start.
- Every service listed in `depends_on` with a health condition must have a `healthcheck` defined.
- Do not rely on `depends_on` without conditions — it only guarantees container start, not readiness.

### Health checks

- Always add a `healthcheck` to database services (Postgres, MySQL, Redis, MongoDB).
- Use the service's native client tool for health checks when available (e.g., `pg_isready`, `redis-cli ping`, `mysqladmin ping`).
- Set reasonable `interval`, `timeout`, `retries`, and `start_period` values. Start with: `interval: 5s`, `timeout: 3s`, `retries: 3`, `start_period: 10s`.

### Volumes

- Use named volumes for data that must persist across container recreations (database data, uploaded files).
- Use bind mounts only for development-time source code syncing.
- Define all named volumes in the top-level `volumes:` key.
- Do not mount the Docker socket unless the service genuinely requires it.

### Networks

- For single-application stacks, the default network is sufficient. Do not create custom networks unless you need isolation between service groups.
- When creating custom networks, prefer bridge driver and give networks descriptive names.
- Use the top-level `networks:` key to define all custom networks.

### Environment variables

- Use `environment:` for non-sensitive values that are few in number.
- Use `env_file:` pointing to a `.env` file for longer lists of variables.
- Never hardcode secrets (passwords, API keys) directly in `compose.yaml`. Use `env_file:` or Docker secrets.
- Add `.env` to `.gitignore`.

### Development overrides

- Use `compose.override.yaml` for development-only settings. Compose loads it automatically alongside `compose.yaml`.
- Put bind mounts for source code, debug ports, and development environment variables in the override file.
- Use `develop.watch` for file-syncing and auto-rebuild in development when supported.
- Keep production-oriented settings in the base `compose.yaml` and override only what changes for development.

### Compose Watch

- Prefer `develop.watch` over manual bind mounts for development workflows.
- Use `action: sync` for files that should be copied into the container on change (source code).
- Use `action: rebuild` for files that require a full image rebuild (dependency files like `package.json`, `requirements.txt`).
- Use `action: sync+restart` for configuration files that need a process restart.

## References

- `references/service-dependencies.md` — Detailed guidance on `depends_on`, health check patterns for common databases, and startup ordering strategies.
- `references/volumes-and-networks.md` — Patterns for volume mounts, named volumes, bind mounts, and network configuration.

## Examples

- `examples/compose-web-app.yaml` — Complete multi-service web app (app + Postgres + Redis) with health checks, dependencies, and named volumes.
- `examples/compose-dev-override.yaml` — Development override showing bind mounts, debug ports, and Compose Watch configuration.
- `examples/bad-vs-good.md` — Before/after comparisons of common Compose mistakes and their fixes.

## Checks

- `checks/verification.md` — Runbook for verifying generated Compose files: syntax validation, dependency correctness, health check presence, and runtime verification.

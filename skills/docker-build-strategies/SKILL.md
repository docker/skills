---
name: docker-build-strategies
description: Use this skill when writing or optimizing Dockerfiles. Covers multi-stage builds, layer caching, non-root users, and image size optimization.
---

# Docker Build Strategies

## Overview

This skill provides rules and patterns for writing production-quality Dockerfiles. Apply it whenever generating or modifying a Dockerfile to produce small, secure, cache-friendly images using multi-stage builds, proper layer ordering, and non-root execution.

## When to use this skill

Activate this skill when:

- Creating a new Dockerfile for any language or framework
- Optimizing an existing Dockerfile for size, speed, or security
- Reviewing a Dockerfile for best-practice compliance
- Adding a `.dockerignore` file to a project

## Core guidance

### Multi-stage builds

Use multi-stage builds when the project has a build step or when build-time dependencies differ from runtime. Separate build-time dependencies from the runtime image.

1. Name every stage explicitly (`FROM ... AS build`, `FROM ... AS runtime`).
2. Use the smallest appropriate base for the runtime stage: `distroless`, `alpine`, or `slim` variants.
3. Copy only the final artifact into the runtime stage with `COPY --from=build`.
4. Use `COPY --link` when copying from a prior stage or adding static files — it improves cache reuse by making the COPY independent of previous layers.

See `references/multi-stage-builds.md` for language-specific patterns (Go, Node, Python, Java).

### Layer caching

Order Dockerfile instructions from least-frequently-changed to most-frequently-changed.

1. Place dependency manifests (`package.json`, `go.mod`, `requirements.txt`) and install steps before copying application source code.
2. Use BuildKit cache mounts for package manager caches:
   - Go: `RUN --mount=type=cache,target=/go/pkg/mod go build ...`
   - Node: `RUN --mount=type=cache,target=/root/.npm npm ci`
   - Python: `RUN --mount=type=cache,target=/root/.cache/pip pip install ...`
3. Pin base image tags to a specific version or digest — never use `latest` in production.
4. Combine related `RUN` commands with `&&` to reduce layer count, but keep logically distinct steps separate for cache granularity.

See `references/layer-caching.md` for detailed cache invalidation rules and cache mount patterns.

### .dockerignore

Always generate a `.dockerignore` alongside the Dockerfile. Exclude:

- `.git/`, `.github/`, `.vscode/`, `.idea/`
- `node_modules/`, `__pycache__/`, `.venv/`, `vendor/` (when rebuilt in the build stage)
- `*.md`, `LICENSE`, `docs/`
- Build outputs, test artifacts, and IDE configs
- `.env` files and any secrets

See `examples/dockerignore-example` for a comprehensive template.

### Non-root user

Always configure the final image to run as a non-root user.

1. Create a dedicated user and group in the runtime stage:
   ```dockerfile
   RUN addgroup --system --gid 1001 appgroup && \
       adduser --system --uid 1001 --ingroup appgroup appuser
   ```
2. Set ownership on application files: `COPY --from=build --chown=appuser:appgroup /app /app`
3. Place the `USER appuser` instruction after all file operations and before `ENTRYPOINT`/`CMD`.
4. On distroless images, use the built-in nonroot user: `USER nonroot:nonroot`.

### Image size optimization

1. Prefer `FROM scratch` (Go static binaries), distroless, or Alpine-based images for the runtime stage.
2. Remove package manager caches in the same `RUN` layer that installs packages: `apt-get install -y ... && rm -rf /var/lib/apt/lists/*`
3. Do not install documentation, man pages, or debug tools in the runtime image.
4. Use `.dockerignore` aggressively to minimize the build context.

### General rules

- Always include a `# syntax=docker/dockerfile:1` directive as the first line to enable BuildKit features.
- Set `WORKDIR` before any `COPY` or `RUN` instructions — never rely on the default `/`.
- Prefer `ENTRYPOINT` with exec form (`["binary"]`) over shell form.
- Add `EXPOSE` to document the listening port.
- Add metadata labels: `LABEL org.opencontainers.image.source=...`

## References

- `references/multi-stage-builds.md` — Language-specific multi-stage patterns for Go, Node.js, Python, and Java
- `references/layer-caching.md` — Deep dive on layer ordering, cache invalidation, and BuildKit cache mounts

## Examples

- `examples/Dockerfile.go` — Multi-stage Go build with distroless runtime and non-root user
- `examples/Dockerfile.nodejs` — Multi-stage Node.js build with proper layer caching and non-root user
- `examples/Dockerfile.python` — Python build with virtual env, layer ordering, and non-root user
- `examples/dockerignore-example` — Comprehensive `.dockerignore` template

## Checks

- `checks/verification.md` — How to verify a generated Dockerfile builds correctly, produces a small image, and runs as non-root

# Verification Runbook

Use these checks to verify a generated Dockerfile meets quality standards.

## 1. Build succeeds

```bash
docker build -t test-image .
```

The build must complete without errors. Use `--progress=plain` to inspect each step if debugging is needed.

## 2. Image size is reasonable

```bash
docker images test-image --format "{{.Size}}"
```

Expected baselines for a minimal application:

| Language | Reasonable upper bound |
|---|---|
| Go (distroless/scratch) | < 30 MB |
| Node.js (Alpine) | < 200 MB |
| Python (slim) | < 250 MB |
| Java (JRE Alpine) | < 300 MB |

If the image exceeds these bounds, check for:

- Missing multi-stage build (build tools included in runtime image)
- Large unnecessary files copied into the image
- Missing `.dockerignore`
- Package manager caches not cleaned

Use `docker history test-image` to identify which layers are largest.

## 3. Runs as non-root

```bash
docker run --rm test-image whoami
```

Expected output: `appuser`, `nonroot`, or another non-root username. Must not return `root`.

If the image does not have `whoami` (e.g., distroless), verify with:

```bash
docker inspect test-image --format '{{.Config.User}}'
```

The output must be non-empty and must not be `0` or `root`.

## 4. No secrets in image

```bash
docker history test-image --no-trunc
```

Inspect the output for any `ENV` instructions or `COPY` steps that might include `.env` files, API keys, or credentials.

## 5. Layer count

```bash
docker history test-image --format "{{.CreatedBy}}" | wc -l
```

A well-structured image typically has 8-15 layers. Significantly more may indicate missing command consolidation.

## 6. Correct WORKDIR, EXPOSE, and ENTRYPOINT

```bash
docker inspect test-image --format '{{.Config.WorkingDir}}'
docker inspect test-image --format '{{.Config.ExposedPorts}}'
docker inspect test-image --format '{{.Config.Entrypoint}}'
```

Verify:

- `WorkingDir` is set (not empty or `/`)
- `ExposedPorts` documents the expected port
- `Entrypoint` uses exec form (JSON array), not shell form

## 7. .dockerignore exists

Verify a `.dockerignore` file is present alongside the Dockerfile and excludes at minimum:

- `.git/`
- `node_modules/`, `__pycache__/`, or equivalent language artifacts
- `.env` and secret files
- IDE configuration directories

## 8. BuildKit syntax directive

The first line of the Dockerfile must be:

```dockerfile
# syntax=docker/dockerfile:1
```

This enables BuildKit features like cache mounts and `COPY --link`.

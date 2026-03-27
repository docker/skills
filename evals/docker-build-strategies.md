# Eval: docker-build-strategies

Skill under test: `skills/docker-build-strategies/`

---

## Prompt 1: Dockerfile for a Go API service

**Prompt to agent:**

> Write a Dockerfile for this Go API service.

### Expected behaviors

- [ ] Dockerfile starts with `# syntax=docker/dockerfile:1`
- [ ] Dockerfile uses a multi-stage build with explicitly named stages (e.g., `FROM golang:1.23 AS build`)
- [ ] Build stage compiles the Go binary with `CGO_ENABLED=0` for a static binary
- [ ] Build stage copies `go.mod` and `go.sum` first and runs `go mod download` before copying source (layer caching)
- [ ] Runtime stage uses a minimal base: `scratch`, `distroless`, or Alpine
- [ ] Only the compiled binary is copied into the runtime stage with `COPY --from=build`
- [ ] Dockerfile sets a non-root user in the runtime stage
- [ ] `WORKDIR` is set before any `COPY` or `RUN` instructions
- [ ] Dockerfile uses `ENTRYPOINT` with exec form
- [ ] Dockerfile includes `EXPOSE` to document the listening port

### Must not

- [ ] Must NOT include Go toolchain, source code, or module cache in the runtime image
- [ ] Must NOT use `latest` as a base image tag
- [ ] Must NOT run as root in the final image
- [ ] Must NOT use shell form for `ENTRYPOINT`
- [ ] Must NOT skip the multi-stage pattern (single `FROM` with Go toolchain as final image)

### Verification commands

```bash
# Build the image
docker build -t go-api-test .

# Check image size (should be under 50MB for a typical Go binary on distroless/scratch)
docker images go-api-test --format '{{.Size}}'

# Verify the image runs as non-root
docker run --rm go-api-test whoami 2>/dev/null || docker run --rm --entrypoint sh go-api-test -c 'id'

# Verify no Go toolchain in final image
docker run --rm --entrypoint sh go-api-test -c 'which go' 2>/dev/null && echo "FAIL: Go toolchain found in runtime image" || echo "PASS: No Go toolchain in runtime image"

# Verify the build uses BuildKit (syntax directive)
head -1 Dockerfile | grep -q 'syntax=docker/dockerfile' && echo "PASS" || echo "FAIL: Missing syntax directive"
```

---

## Prompt 2: Optimize a naive Dockerfile

**Prompt to agent:**

> Optimize this Dockerfile for smaller image size:
>
> ```dockerfile
> FROM node:20
> WORKDIR /app
> COPY . .
> RUN npm install
> RUN npm run build
> EXPOSE 3000
> CMD ["node", "dist/index.js"]
> ```

### Expected behaviors

- [ ] Agent rewrites the Dockerfile as a multi-stage build
- [ ] Build stage uses `node:20` (or a similar full image) for compiling
- [ ] Runtime stage uses a slim or Alpine-based image (e.g., `node:20-slim` or `node:20-alpine`)
- [ ] Agent copies `package.json` and `package-lock.json` before copying source code (layer caching fix)
- [ ] Agent uses `npm ci` instead of `npm install` for reproducible builds
- [ ] Only production `node_modules` and the built `dist/` folder are copied to the runtime stage
- [ ] Agent adds a `.dockerignore` or recommends one if not present
- [ ] Agent adds a non-root user in the runtime stage
- [ ] Agent adds the `# syntax=docker/dockerfile:1` directive
- [ ] Agent uses `COPY --link` where appropriate

### Must not

- [ ] Must NOT keep the single-stage pattern with the full `node:20` image as final
- [ ] Must NOT copy `node_modules/` from the host (should install inside the build stage)
- [ ] Must NOT leave the application running as root
- [ ] Must NOT use `npm install` in production (should use `npm ci`)
- [ ] Must NOT use `latest` as a base image tag

### Verification commands

```bash
# Build the original (for size comparison, if desired)
# docker build -t app-original -f Dockerfile.original .

# Build the optimized image
docker build -t app-optimized .

# Compare image sizes
docker images app-optimized --format 'Optimized: {{.Size}}'

# Verify non-root execution
docker run --rm app-optimized whoami

# Verify the image starts correctly
docker run --rm -d --name test-app -p 3000:3000 app-optimized
curl -s http://localhost:3000/ && echo "PASS: App responds" || echo "Check if app needs more startup time"
docker stop test-app
```

---

## Prompt 3: Node.js app with React frontend build step

**Prompt to agent:**

> Create a Dockerfile for a Node.js app with a React frontend that needs a build step. The backend is in `server/` and the frontend is in `client/`. The frontend build outputs to `client/build/` and is served by the backend.

### Expected behaviors

- [ ] Dockerfile starts with `# syntax=docker/dockerfile:1`
- [ ] Dockerfile uses at least two stages (a build stage and a runtime stage; optionally a separate frontend build stage)
- [ ] All stages have explicit names (e.g., `AS frontend-build`, `AS runtime`)
- [ ] Frontend build stage installs frontend dependencies and runs the React build (`npm run build`)
- [ ] Frontend dependency install copies `client/package.json` and `client/package-lock.json` first (layer caching)
- [ ] Backend dependency install copies `server/package.json` and `server/package-lock.json` first (layer caching)
- [ ] Uses `npm ci` for reproducible installs
- [ ] Runtime stage uses a slim or Alpine-based Node image with a pinned version
- [ ] Only the server code, production `node_modules`, and built frontend assets are in the final image
- [ ] Frontend source code and `node_modules` are NOT in the final image
- [ ] Dockerfile sets a non-root user in the runtime stage
- [ ] Agent produces or recommends a `.dockerignore` file

### Must not

- [ ] Must NOT include frontend `node_modules` or source files in the runtime image
- [ ] Must NOT use `latest` as a base image tag
- [ ] Must NOT run as root in the final image
- [ ] Must NOT use a single stage with the full Node image as the runtime
- [ ] Must NOT copy the entire monorepo into the runtime stage

### Verification commands

```bash
# Build the image
docker build -t fullstack-app .

# Check image size (should be significantly smaller than a naive single-stage build)
docker images fullstack-app --format '{{.Size}}'

# Verify non-root execution
docker run --rm fullstack-app whoami

# Verify frontend assets are present
docker run --rm --entrypoint sh fullstack-app -c 'ls /app/client/build/index.html' && echo "PASS: Frontend assets present" || echo "FAIL: Frontend assets missing"

# Verify frontend source/node_modules are NOT present
docker run --rm --entrypoint sh fullstack-app -c 'test -d /app/client/node_modules && echo "FAIL: Frontend node_modules present" || echo "PASS: No frontend node_modules"'
docker run --rm --entrypoint sh fullstack-app -c 'test -f /app/client/src/App.js && echo "FAIL: Frontend source present" || echo "PASS: No frontend source"'

# Start and verify
docker run --rm -d --name test-fullstack -p 3000:3000 fullstack-app
curl -s http://localhost:3000/ && echo "PASS: App responds" || echo "Check if app needs more startup time"
docker stop test-fullstack
```

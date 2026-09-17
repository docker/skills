# Eval: docker-project-foundations

Skill under test: `skills/docker-project-foundations/`

---

## Prompt 1: Node.js + PostgreSQL project setup

**Prompt to agent:**

> I have a Node.js Express app with a PostgreSQL database. Help me set up Docker for local development.

### Expected behaviors

- [ ] Agent creates a `.dockerignore` file
- [ ] `.dockerignore` excludes `node_modules/`, `.git/`, `.env`, `.npmrc`, and IDE config directories
- [ ] Agent creates a `Dockerfile` with a multi-stage build
- [ ] Dockerfile pins the base image to a specific version (e.g., `node:22-slim`), not `latest`
- [ ] Dockerfile copies `package.json` and `package-lock.json` before copying source code (layer caching)
- [ ] Dockerfile uses a BuildKit secret mount for optional npm registry configuration during each dependency install
- [ ] Dockerfile sets a non-root `USER` before `CMD`/`ENTRYPOINT`
- [ ] Agent creates a `compose.yaml` (not `docker-compose.yml`)
- [ ] Compose file defines PostgreSQL as a service using the official `postgres` image
- [ ] Compose file pins the Postgres image tag to a specific version
- [ ] Compose file uses a named volume for Postgres data
- [ ] Compose file includes a health check for the Postgres service (using `pg_isready`)
- [ ] Compose file uses `depends_on` with `condition: service_healthy` for the app service
- [ ] Compose file uses bind mounts or Compose Watch for live source code reloading in development

### Must not

- [ ] Must NOT suggest `brew install postgres`, `apt install postgresql`, or any host-level database install
- [ ] Must NOT use `latest` as an image tag anywhere
- [ ] Must NOT use the legacy filename `docker-compose.yml`
- [ ] Must NOT run the application as root in the final image
- [ ] Must NOT hardcode database passwords directly in `compose.yaml`
- [ ] Must NOT use `COPY` or `ADD` for `.npmrc`; provide registry configuration with a build secret when needed

### Verification commands

```bash
# Validate Compose file syntax
docker compose config

# Start all services
docker compose up -d

# Confirm services are running and healthy
docker compose ps

# Check that Postgres is reachable from the app container
docker compose exec app sh -c 'pg_isready -h db' || echo "pg_isready not available in app container, check logs instead"

# Tear down
docker compose down
```

---

## Prompt 2: Python Flask project

**Prompt to agent:**

> Add Docker support to this Python Flask project.

### Expected behaviors

- [ ] Agent creates a `.dockerignore` file
- [ ] `.dockerignore` excludes `__pycache__/`, `.venv/`, `.git/`, `.env`
- [ ] Agent creates a `Dockerfile`
- [ ] Dockerfile uses a slim or Alpine-based Python image with a pinned version
- [ ] Dockerfile copies `requirements.txt` before copying source code
- [ ] Dockerfile installs dependencies with `pip install --no-cache-dir` or uses a cache mount
- [ ] Dockerfile sets a non-root user
- [ ] Agent creates a `compose.yaml` for local development
- [ ] Compose file defines the Flask app service with appropriate port mapping
- [ ] Compose file includes bind mounts or Compose Watch for development reload

### Must not

- [ ] Must NOT suggest creating a virtualenv on the host for development
- [ ] Must NOT use `latest` as an image tag
- [ ] Must NOT use `docker-compose.yml` as the filename
- [ ] Must NOT run as root in the final image
- [ ] Must NOT install development/test tools in the production stage

### Verification commands

```bash
# Validate Compose file syntax
docker compose config

# Build and start
docker compose up -d --build

# Confirm the Flask app responds
curl -s http://localhost:5000/ || curl -s http://localhost:8000/

# Check container is running as non-root
docker compose exec app whoami

# Tear down
docker compose down
```

---

## Prompt 3: Go API with Redis

**Prompt to agent:**

> I want to containerize my Go API that uses Redis for caching.

### Expected behaviors

- [ ] Agent creates a `.dockerignore` file
- [ ] Agent creates a multi-stage `Dockerfile` (build stage compiles Go binary, runtime stage is minimal)
- [ ] Runtime stage uses `scratch`, `distroless`, or Alpine
- [ ] Dockerfile pins all base image tags to specific versions
- [ ] Go binary is statically compiled (e.g., `CGO_ENABLED=0`)
- [ ] Dockerfile sets a non-root user in the runtime stage
- [ ] Agent creates a `compose.yaml`
- [ ] Compose file defines Redis as a service with a pinned image tag
- [ ] Compose file includes a health check for Redis (using `redis-cli ping`)
- [ ] Compose file uses `depends_on` with `condition: service_healthy`

### Must not

- [ ] Must NOT suggest `brew install redis` or any host-level Redis install
- [ ] Must NOT include Go toolchain or source code in the final runtime image
- [ ] Must NOT use `latest` as an image tag
- [ ] Must NOT use `docker-compose.yml` as the filename
- [ ] Must NOT run as root in the final image

### Verification commands

```bash
# Validate Compose file syntax
docker compose config

# Build the image and check size (should be small for Go)
docker compose build
docker images | grep -i api

# Start all services
docker compose up -d

# Confirm Redis is healthy
docker compose ps

# Verify the API container runs as non-root
docker compose exec api whoami || docker run --rm $(docker compose images -q api) whoami

# Tear down
docker compose down
```

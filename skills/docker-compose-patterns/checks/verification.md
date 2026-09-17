# Verification Runbook for Generated Compose Files

Run these checks against every generated `compose.yaml` before considering it complete.

## 1. Syntax and schema validation

Run the bundled script from the project root:

```bash
bash scripts/verify-compose.sh [--help]
```

Exit status is `0` when the Compose configuration is valid or help is requested, the non-zero status from `docker compose config` when validation fails, and `2` for invalid arguments.

To run the underlying validation directly:

```bash
docker compose config
```

This parses and validates the Compose file, resolves variables, and prints the fully resolved configuration. If it exits non-zero, the file has syntax or schema errors. Fix all errors before proceeding.

To validate without printing the full output:

```bash
docker compose config --quiet
```

## 2. Health check presence

Verify that every database, cache, or message broker service has a `healthcheck` defined. Check the output of `docker compose config` and confirm these services include `healthcheck.test`, `healthcheck.interval`, `healthcheck.timeout`, `healthcheck.retries`, and `healthcheck.start_period`.

Services that must have health checks:

- PostgreSQL, MySQL, MariaDB
- Redis, Memcached
- MongoDB
- RabbitMQ, Kafka
- Elasticsearch

## 3. Dependency ordering

For every service with `depends_on`:

- Confirm `condition: service_healthy` is set for infrastructure dependencies.
- Confirm the referenced service has a matching `healthcheck`.
- Confirm no circular dependencies exist (Compose will reject these, but verify intent).

## 4. Volume definitions

- Every volume referenced in a service's `volumes:` list that uses the `name:/path` format must have a corresponding entry in the top-level `volumes:` key.
- Database services must use named volumes, not bind mounts, for data directories.
- Bind mounts should appear only in development override files.

## 5. Environment variables and secrets

- No plaintext passwords, API keys, or tokens appear directly in `compose.yaml`.
- Sensitive values use `env_file:` or Docker secrets.
- If `.env` is referenced, confirm `.env` is in `.gitignore`.

## 6. Image tags

- No service uses the `latest` tag or omits the tag entirely.
- All image references include an explicit version.

## 7. Runtime verification

After `docker compose up -d`:

```bash
# Check all services are running and healthy
docker compose ps

# Verify health check status specifically
docker inspect --format='{{.State.Health.Status}}' <container_name>

# Check logs for startup errors
docker compose logs --tail=50

# Verify inter-service connectivity
docker compose exec web ping -c 1 db
```

## 8. File naming

- The file is named `compose.yaml`, not `docker-compose.yml` or `docker-compose.yaml`.
- Development overrides are in `compose.override.yaml`.

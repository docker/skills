# Sources

- `docker agent run --help`, `docker agent alias --help`, `docker agent alias add --help`, `docker agent sandbox --help`, `docker agent sandbox allow --help`, `docker agent doctor --help` — verified locally against docker-agent as shipped with Docker CLI 29.7.2.
- https://docs.docker.com/ai/docker-agent/features/cli/ — full CLI command/flag reference (`run`, `alias`, `serve`, agent references, runtime configuration flags).
- https://docs.docker.com/ai/docker-agent/configuration/sandbox/ — sandbox mode overview, `--sandbox`/`--template`/`--no-kit` flags, auto-kit, network allowlist, `docker agent sandbox allow/deny/list`.
- https://docs.docker.com/ai/sandboxes/security/ — sandbox security model, trust boundaries, what is/isn't isolated by default, `sbx` prerequisite.
- https://docs.docker.com/ai/docker-agent/community/troubleshooting/ — "No model is currently available" pitfall and `docker agent doctor` usage.
- https://github.com/docker/docker-agent/blob/40fc6eef359d8e68e9c52f39c27b014bb2414bfd/cmd/root/run.go#L596-L619 and https://github.com/docker/docker-agent/blob/40fc6eef359d8e68e9c52f39c27b014bb2414bfd/cmd/root/run_autodiscovery_test.go#L12-L64 — project-config discovery names and ordering, verified against docker-agent dev commit `40fc6eef359d8e68e9c52f39c27b014bb2414bfd` (not the Docker CLI version).
- https://github.com/docker/docker-agent/blob/40fc6eef359d8e68e9c52f39c27b014bb2414bfd/pkg/config/sources/sources.go#L161-L178 — empty references resolve to the `default` alias before the built-in agent, after project discovery in `run`.

## Sandbox trust-boundary clarification

- Frozen Docker Sandboxes security page: https://docs.docker.com/ai/sandboxes/security/
  (acquired 2026-09-30 alongside sbx v0.46.0 evidence). Sections "Isolation
  boundaries" and "Security considerations" describe shared skills, live host
  workspace changes, Git hooks outside `git diff`, and local stdio MCP host
  processes. The mounted-resource list is not exhaustive. This is a trust
  clarification, not verification of new Docker Agent wrapper flags; the
  wrapper version and command provenance above remain unchanged.

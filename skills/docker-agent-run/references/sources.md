# Sources

- `docker agent run --help`, `docker agent alias --help`, `docker agent alias add --help`, `docker agent sandbox --help`, `docker agent sandbox allow --help`, `docker agent doctor --help` — verified locally against docker-agent as shipped with Docker CLI 29.7.2.
- https://docs.docker.com/ai/docker-agent/features/cli/ — full CLI command/flag reference (`run`, `alias`, `serve`, agent references, runtime configuration flags).
- https://docs.docker.com/ai/docker-agent/configuration/sandbox/ — sandbox mode overview, `--sandbox`/`--template`/`--no-kit` flags, auto-kit, network allowlist, `docker agent sandbox allow/deny/list`.
- https://docs.docker.com/ai/sandboxes/security/ — sandbox security model, trust boundaries, what is/isn't isolated by default, `sbx` prerequisite.
- https://docs.docker.com/ai/docker-agent/troubleshooting/ — "No model is currently available" pitfall and `docker agent doctor` usage.

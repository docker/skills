# Sandbox templates

A *template* in `sbx` is the container image used as the base of a sandbox. The kit declares a default; you override it with `--template <image-ref>`.

This is distinct from `sbx template save|load|ls|rm`, which manages *snapshots of running sandboxes* (also called "templates" in the CLI surface, unfortunately). This page covers the **image templates** used at creation time.

## Built-in template images

The project publishes images at `docker/sandbox-templates:<flavor>` for each supported agent. Common flavors:

- `claude-code-docker` — Claude Code with Docker tooling.
- `claude-code-minimal` — Slimmer Claude image.
- `gemini`, `codex`, `cursor-agent`, `devin-docker`, `opencode`, `docker-agent`, `shell`.

`copilot`, `kiro`, and `droid` template flavors existed for the built-in
kits of the same names; those kits were later removed (see
`agent-kits.md`), so these flavors are only relevant with a custom `--kit`
that still targets them.

Tagging convention:

- `docker/sandbox-templates:<flavor>` — Stable, current release.
- `docker/sandbox-templates:<flavor>-<version>` — Pinned version.
- `docker/sandbox-templates:<flavor>-nightly` — Daily build.

For production / reproducible setups, pin to a specific version tag or digest. Never rely on `:latest`.

## Using a built-in template

You usually don't pass `--template` — the kit's default is correct. Override when:

- A new template build fixes a bug your agent needs.
- You want a minimal variant (e.g., `claude-code-minimal`).
- You're testing a nightly.

```bash
sbx create claude . --template docker/sandbox-templates:claude-code-docker
```

## Writing a custom template

A custom template is a regular Dockerfile that extends one of the built-in images (or starts from scratch, but extending is usually right). The kit's behavior contract still applies on top.

See `assets/custom-template.Dockerfile` (path relative to the skill root) for a complete example. Key rules:

1. **Pin the base.** Use a version tag or digest, never `:latest`.
2. **Start with `# syntax=docker/dockerfile:1`** to enable BuildKit features.
3. **Add tooling only.** Do not override `ENTRYPOINT`, `CMD`, or `USER` — the kit owns those.
4. **Do not embed credentials** via `ARG` or `ENV`. Credentials come from the host secret store, not the template.
5. **Push to a registry the host can pull from.** The `sbx` daemon resolves `--template` by pulling, just like any other image.

```bash
docker build -t my-registry.example.com/sbx/claude-plus:1.0 \
    -f assets/custom-template.Dockerfile .
docker push my-registry.example.com/sbx/claude-plus:1.0
sbx create claude . --template my-registry.example.com/sbx/claude-plus:1.0
```

## Kit-declared image vs. CLI override

```text
kit spec.yaml:    sandbox.image: docker/sandbox-templates:claude-code-docker
CLI flag:         --template my-registry/my-template:1.0  (wins)
```

The `--template` flag wins. The kit's other declarations (entrypoint, env, commands, files, credentials, network) still apply.

## Sandbox snapshots (`sbx template save|load`)

Distinct concept: `sbx template save` snapshots a running sandbox's state into a tar/OCI artifact you can later restore with `sbx template load`. Useful for capturing a configured environment to share with a teammate.

This is **not** what `--template` consumes — `--template` takes an image reference, not a snapshot reference.

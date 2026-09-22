---
title: Advanced installation
canonical: https://docs.docker.com/ai/skills/advanced-install/
weight: 15
---

# Advanced installation

Use these methods when you need release pinning, a product-native integration,
an OCI artifact, or direct control over the files. For a standard installation,
start with [Install Docker Skills](../install/index.md).

## Pin a release

`main` is the rolling development channel. Git tags such as `v0.2.0` are
immutable distribution snapshots. The `skills` CLI accepts a GitHub tree URL,
so you can select skills from a release without following `main`:

```console
npx skills add https://github.com/docker/skills/tree/v0.2.0 \
  --skill docker-compose-patterns --yes
```

Replace `v0.2.0` with the release you reviewed. Check
[GitHub Releases](https://github.com/docker/skills/releases) for the latest
version. Updating an intentionally pinned installation should be a deliberate
remove-and-install operation using the next reviewed tag, not an unreviewed
switch to the rolling channel.

## Docker Agent

Docker Agent discovers file-based skills from its standard global and project
paths. Install Docker Skills with the `skills` CLI, then enable skills in the
agent configuration:

```yaml
agents:
  root:
    model: dmr/ai/qwen3
    instruction: Help with Docker development tasks.
    skills:
      - docker-build-strategies
      - docker-compose-patterns
    toolsets:
      - type: filesystem
```

Names in the `skills` list filter discovered skills. Use `skills: true` to make
every discovered skill available. Start a new run after changing installed
skills:

```console
docker agent run ./agent.yaml
```

Docker Agent also accepts HTTP or HTTPS skill sources in `agent.yaml`, but a
local or release-pinned installation is easier to audit and works offline.
See [Docker Agent skills](https://docs.docker.com/ai/docker-agent/features/skills/)
for search paths, precedence, filtering, and sandbox behavior.

## Docker Sandboxes

> **Experimental:** The `sbx skills` command may change or be removed. Use it
> only with a Docker Sandboxes release that exposes the command, and check the
> command's built-in help before automating it.

Install the catalog into the Docker Sandboxes shared skill store:

```console
sbx skills add docker/skills
```

Select one or more skills with repeatable `--skill` flags:

```console
sbx skills add docker/skills --skill docker-build-strategies \
  --skill docker-compose-patterns
```

Inspect and refresh repository-backed skills with:

```console
sbx skills ls
sbx skills update
```

Remove a named skill with `sbx skills rm <skill-name>`. This immediately breaks
its link in running sandboxes, and a sandbox restart clears the stale link, so
confirm that no active sandbox depends on it before removal. Run
`sbx skills --help` for the behavior in your installed version.

## OCI image

Docker publishes the repository content as the multi-platform
`docker/skills-content` image. `edge` tracks `main`; release tags are immutable
snapshots.

Inspect the rolling image without extracting it:

```console
docker buildx imagetools inspect docker/skills-content:edge
```

For reproducible use, choose a version shown in
[GitHub Releases](https://github.com/docker/skills/releases) and pin the image
to its published digest:

```text
docker/skills-content:vX.Y.Z@sha256:<published-digest>
```

The image uses `scratch` and stores repository files at `/`; it is a content
artifact, not an executable runtime. Consumers should mount or extract only the
skill directories they need using tooling that supports OCI artifacts. A digest
provides byte-for-byte pinning; a mutable `edge` tag does not.

## Manual clone or copy

Clone a release tag when your client does not use the `skills` CLI:

```console
git clone --branch v0.2.0 --depth 1 https://github.com/docker/skills.git
```

Copy selected directories from `skills/` into a skill path documented by your
client. Common global paths include:

| Client | Global skill path |
| --- | --- |
| Claude Code | `~/.claude/skills/` |
| Codex | `~/.codex/skills/` or `~/.agents/skills/` |
| Cursor | `~/.cursor/skills/` |
| Gemini CLI | `~/.gemini/skills/` |
| OpenCode | `~/.config/opencode/skills/` |

Some clients also support project paths such as `.agents/skills/` or
`.github/skills/`. Follow the client's current documentation rather than
assuming every path or symlink strategy is portable. Preserve each complete
skill directory, including its `SKILL.md` and any referenced `assets/`,
`checks/`, `references/`, or `scripts/` files.

To update a clone, fetch and check out a reviewed release tag. To update copied
skills, replace each complete copied directory from that tag. Remove a manual
installation by deleting only the specific directories or links you installed,
after checking that they do not contain local edits.

## Troubleshooting

### A skill does not appear

1. Run `npx skills list` or `npx skills list --global` for CLI installations.
2. Confirm the selected agent and installation scope.
3. Check that the destination contains the complete skill directory and a
   readable `SKILL.md`.
4. Restart the agent session; many clients scan at startup.
5. Check the client's current discovery-path documentation.

### The wrong skill loads

Install fewer skills or use your client's filtering support. Docker Agent can
list skill names under `agents.<name>.skills`; the `skills` CLI can target
specific entries with repeated `--skill` options.

### Updates do not arrive

Identify the installation owner first. Use `npx skills update` only for skills
installed by that CLI. Native plugins update through their client. Manual and
release-pinned installations require an explicit tag or file replacement.

### A symlink is ignored

Reinstall with `npx skills add docker/skills --copy`, keeping the same scope,
agent, and skill-selection flags. Copies do not update through a shared
canonical directory, so verify each destination after updates.

### A pinned install moved unexpectedly

Check the source with `npx skills list --json` or inspect the clone's current Git
tag. Release tags and image digests are immutable; `main`, `edge`, and unpinned
plugin channels are not.

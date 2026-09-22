---
title: Sources and fallback
canonical: https://docs.docker.com/ai/skills/install/sources/
weight: 15
---

# Sources and fallback

Git checkouts and manual copies provide skill content to a consumer. They are
sources or fallback mechanisms, not general distribution models.

## Basic install

### Git clone or manual copy

Clone a reviewed release, then copy complete directories from `skills/` into a
path documented by the consuming client:

```console
git clone --branch v0.2.0 --depth 1 https://github.com/docker/skills.git
```

Preserve `SKILL.md` and all referenced `assets/`, `checks/`, `references/`, and
`scripts/` files.

## Advanced install

Common user paths include `~/.claude/skills/`, `~/.codex/skills/` or
`~/.agents/skills/`, `~/.cursor/skills/`, `~/.gemini/skills/`, and
`~/.config/opencode/skills/`. Some clients support project paths such as
`.agents/skills/` or `.github/skills/`. Follow current client documentation;
do not assume every path or link strategy is portable.

A sparse checkout can reduce local files only if every selected skill's
referenced support files remain present.

## Update, pin, and scope

Release tags are immutable; `main` and other rolling Git references move.
Update a clone by fetching and checking out the next reviewed tag. Replace each
complete manually copied directory from that tag. Scope is determined by the
consumer's destination path. Remove only directories or links you installed,
after checking for local edits.

## Verification

Run `git describe --tags --exact-match` in a tagged checkout. At the destination,
confirm each skill has a readable `SKILL.md` and its referenced files, restart
the client, and request a matching task.

## Troubleshooting

- If a skill is absent, confirm the client's exact discovery path and scope.
- If supporting files are missing, recopy the complete skill directory.
- If a symbolic link is ignored, use a physical copy in the same documented
  destination.
- If content moved unexpectedly, replace rolling Git references with a reviewed
  release tag.
- If updates do not arrive, remember that manual and pinned sources have no
  managed updater.

## Related links

- [Install Docker Skills](./_index.md)
- [Docker Skills releases](https://github.com/docker/skills/releases)
- [skills CLI](skills-cli.md)
- [Docker products](docker-products.md)

---
title: skills CLI
canonical: https://docs.docker.com/ai/skills/install/skills-cli/
weight: 13
---

# skills CLI

Use the cross-client `skills` CLI when you want explicit skill selection and
project or user scope across compatible agents.

## Basic install

### skills CLI

Run the interactive installer from the target project:

```console
npx skills add docker/skills
```

Choose skills and agents when prompted. Add `--global` (`-g`) for user scope.

## Advanced install

Preview and make installation non-interactive:

```console
npx skills add docker/skills --list
npx skills add docker/skills --skill docker-compose-patterns --yes
npx skills add docker/skills --skill docker-build-strategies \
  --agent claude-code --global --yes
npx skills add docker/skills --all
```

Repeat `--skill` or `--agent` to select several entries. The CLI normally shares
a canonical copy through links; add `--copy` only when the client or filesystem
cannot follow them.

## Update, pin, and scope

List and update the matching scope:

```console
npx skills list
npx skills list --global
npx skills update
npx skills update --global
```

Remove a project skill with `npx skills remove docker-compose-patterns`; add
`--global` for user scope. For a reviewed release, pass a tagged tree URL:

```console
npx skills add https://github.com/docker/skills/tree/v0.2.0 \
  --skill docker-compose-patterns --yes
```

Replace `v0.2.0` with the release you reviewed. Update a pin deliberately by
removing and reinstalling from the next reviewed tag.

## Verification

Run `npx skills list` or `npx skills list --global`, confirm the intended agent,
scope, and selected skill, then restart the agent and request a matching task.
Use `npx skills list --json` when automation needs to inspect the source.

## Troubleshooting

- If a skill does not appear, confirm scope and agent selection, then restart the
  agent session.
- If a link is ignored, reinstall with `--copy` while retaining the same scope,
  agent, and skill flags.
- If the wrong skill loads, remove unnecessary entries and install a smaller
  selection.
- If updates do not arrive, verify that this CLI—not a native plugin or manual
  copy—owns the installation.
- If a pin moved, inspect the source: release tags are immutable, while `main`
  is a rolling channel.

## Related links

- [Install Docker Skills](./_index.md)
- [skills CLI documentation](https://skills.sh/docs)
- [Skill catalog](../catalog/index.md)
- [Sources and fallback](sources.md)

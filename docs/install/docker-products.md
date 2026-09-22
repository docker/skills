---
title: Docker products
canonical: https://docs.docker.com/ai/skills/install/docker-products/
weight: 14
---

# Docker products

Docker Agent consumes skills installed through another supported model. Docker
Sandboxes also exposes an experimental product-native installer in supported
releases.

## Basic install

### Docker Sandboxes

> **Experimental:** `sbx skills` may change or be removed. Check built-in help
> in the installed release before automating it.

Install into the shared sandbox skill store:

```console
sbx skills add docker/skills
```

### Docker Agent

Docker Agent is a consumer, not a distribution model. Install skills through a
[marketplace](native-marketplaces.md), the [skills CLI](skills-cli.md), or a
supported source path, then select discovered names in `agent.yaml`:

```yaml
agents:
  root:
    model: dmr/ai/qwen3
    instruction: Help with Docker development tasks.
    skills:
      - docker-build-strategies
      - docker-compose-patterns
```

## Advanced install

Select multiple Sandbox skills with repeatable flags:

```console
sbx skills add docker/skills --skill docker-build-strategies \
  --skill docker-compose-patterns
```

Docker Agent accepts `skills: true` for every discovered skill or a list for
filtering. It can also consume HTTP(S) sources, but a local release-pinned
installation is easier to audit and works offline.

## Update, pin, and scope

Inspect and refresh the Sandbox shared store with `sbx skills ls` and `sbx
skills update`. Remove a named entry with `sbx skills rm <skill-name>` only after
confirming no active sandbox depends on it; restart affected sandboxes to clear
stale links. Run `sbx skills --help` for release-specific behavior.

Docker Agent does not own updates. Update with the installer or source that owns
the discovered files, then start a new `docker agent run ./agent.yaml`. Pin at
the source or installer layer, not in the skill-name filter.

## Verification

For Sandboxes, run `sbx skills ls`, start or restart a sandbox, and confirm the
selected skill is linked. For Docker Agent, confirm the skill exists in a
[documented search path](https://docs.docker.com/ai/docker-agent/features/skills/),
then start a run and verify that the named filter allows it.

## Troubleshooting

- If `sbx skills` is absent, the installed release does not expose the
  experimental installer; use the [skills CLI](skills-cli.md) or manual path.
- If removing a Sandbox skill leaves a stale link, restart the sandbox.
- If Docker Agent cannot find a skill, check discovery paths, precedence, and
  the `agents.<name>.skills` filter.
- If an updated skill is not visible, restart the product session after the
  owning installer completes its update.

## Related links

- [Install Docker Skills](./_index.md)
- [Docker Agent skills](https://docs.docker.com/ai/docker-agent/features/skills/)
- [Docker Sandboxes documentation](https://docs.docker.com/ai/sandboxes/)
- [Sources and fallback](sources.md)

---
title: Native marketplaces
canonical: https://docs.docker.com/ai/skills/install/native-marketplaces/
weight: 11
---

# Native marketplaces

Use a native marketplace when the client should own plugin discovery, policy,
and updates. Claude Code and GitHub Copilot CLI commands below were checked
against vendor documentation; Cursor and Codex use conservative interface
wording because a stable public command for this repository was not verified.

## Basic install

### Claude Code marketplace

In Claude Code, add Docker's marketplace and install the plugin:

```text
/plugin marketplace add docker/skills
/plugin install docker-skills@docker
```

### GitHub Copilot CLI marketplace

In Copilot CLI, use either the interactive commands above or the documented CLI
forms:

```console
copilot plugin marketplace add docker/skills
copilot plugin install docker-skills@docker
```

### Cursor marketplace

Open Cursor's plugin or marketplace interface and add `docker/skills` where
repository-backed marketplaces are enabled by your administrator. If that
surface is unavailable, use the [skills CLI](skills-cli.md) or a documented
manual skill path; this guide intentionally does not claim an unverified Cursor
command.

### Codex marketplace

Where your Codex client exposes repository-backed plugins, select the Docker
marketplace and `docker-skills` plugin through that interface. Otherwise use the
[skills CLI](skills-cli.md) or a documented manual skill path. No unverified
Codex marketplace command is presented here.

## Advanced install

Organization policy can restrict third-party marketplaces or require an admin
to register them. Keep the repository identity `docker/skills` and plugin name
`docker-skills` unchanged when configuring an allowlist. Prefer the client's
managed interface over copying plugin-manifest files out of the repository.

## Update, pin, and scope

Native clients own update cadence and scope. Check the client UI or plugin
manager for user, project, and organization controls. Marketplace channels may
track repository changes and are not equivalent to an immutable release tag;
use [source-level pinning](sources.md#git-clone-or-manual-copy) when a reviewed
snapshot is required.

## Verification

Open the client's installed-plugin view and confirm that **Docker Skills** or
`docker-skills` is enabled in the intended scope. Start a new session and ask
for a Docker task. For command-based clients, also use their documented plugin
listing command or `/plugin` interface.

## Troubleshooting

- If the marketplace is blocked, ask an administrator to allow `docker/skills`.
- If the plugin is not found, confirm the marketplace was added before install.
- If a skill is not discovered, enable the plugin and restart the session.
- If updates are missing, refresh through the client; do not use `npx skills
  update` for a native-plugin installation.

## Related links

- [Install Docker Skills](./_index.md)
- [Claude Code plugins](https://code.claude.com/docs/en/discover-plugins)
- [GitHub Copilot CLI plugins](https://docs.github.com/en/copilot/how-tos/copilot-cli/customize-copilot/plugins-finding-installing)
- [Cursor plugins](https://cursor.com/docs/plugins)
- [Sources and fallback](sources.md)

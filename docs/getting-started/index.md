---
title: Get started
canonical: https://docs.docker.com/ai/skills/getting-started/
weight: 30
---

# Get started with Docker Skills

Docker Skills are portable instruction packages that help compatible AI coding
agents produce safer, more accurate Docker changes. A skill loads when its
description matches your request, so you can ask your agent for the outcome you
want instead of naming a skill explicitly.

## Install a skill

Follow the [installation guide](../install/index.md) to choose an installation
method, scope, and skills. For most users:

```console
npx skills add docker/skills
```

The interactive installer detects supported agents and lets you choose only the
skills you need.

## Use a skill

Start a new agent session, then ask for a Docker task in ordinary language. For
example:

- "Dockerize this application for local development."
- "Make this Dockerfile smaller and run as a non-root user."
- "Add a database health check to this Compose application."
- "Run my coding agent in an isolated Docker Sandbox."

Compatible agents match the request to each installed skill's description and
load the relevant guidance. Tasks can use more than one skill; an agent may
combine project-foundation, build, and Compose guidance when creating a complete
stack.

Browse the [skill catalog](../catalog/index.md) to see the supported products and
routing descriptions.

## Check the result

A skill guides the agent; it does not replace review and validation. Inspect the
files and commands the agent proposes, run the project's tests, and confirm any
destructive operation before approving it. If the agent cannot find an installed
skill, use the [advanced troubleshooting checklist](../advanced-install/index.md#troubleshooting).

## Keep skills current

Each installation method has its own update path. The `skills` CLI uses
`npx skills update`, native plugins use their client, and pinned or manual
installs require an explicit version change. See [Update or remove skills](../install/index.md#update-or-remove-skills)
and [Pin a release](../advanced-install/index.md#pin-a-release).

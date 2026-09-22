---
title: Get started
canonical: https://docs.docker.com/ai/skills/getting-started/
weight: 10
---

# Get started with Docker Skills

Docker Skills are portable instruction packages that help compatible AI coding
agents produce safer, more accurate Docker changes. A skill loads when its
description matches your request, so you can ask your agent for the outcome you
want instead of naming a skill explicitly.

## Install the catalog

The [`skills` CLI](https://skills.sh) discovers supported coding agents and lets
you choose which Docker Skills to install:

```console
npx skills add docker/skills
```

Useful non-interactive forms include:

```console
# List the catalog without installing
npx skills add docker/skills --list

# Install one skill for detected agents
npx skills add docker/skills --skill docker-compose-patterns --yes

# Install every skill
npx skills add docker/skills --all
```

You can also install the repository as a plugin or clone it into a project. See
the [repository installation options](https://github.com/docker/skills#installation)
for client-specific commands.

## Use a skill

Ask your coding agent for a Docker task in ordinary language. For example:

- "Dockerize this application for local development."
- "Make this Dockerfile smaller and run as a non-root user."
- "Add a database health check to this Compose application."
- "Run my coding agent in an isolated Docker Sandbox."

Compatible agents match the request to each skill's description and load the
relevant guidance. Tasks can use more than one skill; an agent may combine the
project-foundation, build, and Compose guidance when creating a complete stack.

Browse the [skill catalog](../catalog/index.md) to see the supported products and
routing descriptions.

## Keep skills current

Update skills installed by the `skills` CLI with:

```console
npx skills update
```

For reproducible automation, pin a release tag instead of tracking `main`.

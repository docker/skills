---
title: Get started
canonical: https://docs.docker.com/ai/skills/getting-started/
weight: 30
---

# Get started with Docker Skills

Docker Skills are portable instruction packages that help compatible AI coding
agents produce safer, more accurate Docker changes. A skill loads when its
description matches your request, so ask for the outcome instead of naming a
skill explicitly.

## Install a skill

Open the [installation hub](../install/_index.md) and choose a native
marketplace, extension, or the skills CLI. These models have equal standing;
select the one your client or organization manages. The hub also documents
Docker product behavior and source-level fallbacks.

Install only the skills needed for the task and complete the selected model's
verification procedure before starting a new session.

## Use a skill

Start a new agent session, then ask for a Docker task in ordinary language:

- “Dockerize this application for local development.”
- “Make this Dockerfile smaller and run as a non-root user.”
- “Add a database health check to this Compose application.”
- “Run my coding agent in an isolated Docker Sandbox.”

Compatible agents match the request to installed skill descriptions. Tasks can
use more than one skill; an agent may combine project-foundation, build, and
Compose guidance when creating a complete stack.

Browse the [skill catalog](../catalog/index.md) for products and routing
descriptions.

## Check the result

A skill guides the agent; it does not replace review and validation. Inspect the
files and commands the agent proposes, run project tests, and confirm destructive
operations before approving them. If a skill is not found, use the
troubleshooting section on the selected installation model page.

## Keep skills current

Each model owns its updates: native plugins and extensions update through their
client, the skills CLI uses its update command, Docker Agent relies on the
installer that owns discovered files, and pinned or manual sources require an
explicit version change. See [Install Docker Skills](../install/_index.md) for
the model-specific procedure.

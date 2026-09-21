# Eval: docker

Skill under test: `skills/docker/`

This skill only routes. Each prompt checks that the agent loads the skill named in the routing table and does not answer from the router alone.

---

## Prompt 1: Ambiguous Docker request

**Prompt to agent:**

> My Node app is slow to build and the image is huge. Can you fix it?

### Expected behaviors

- [ ] Agent loads `docker-build-strategies` before proposing changes
- [ ] Agent does not load `docker-project-foundations` or `docker-compose-patterns` unless the project turns out to have no Docker setup or a Compose change is needed
- [ ] Agent follows the loaded skill's guidance rather than improvising from the router

### Must not

- [ ] Must NOT produce Dockerfile guidance with only the `docker` skill loaded
- [ ] Must NOT load every Docker skill indiscriminately

### Verification commands

```bash
# Inspect the agent transcript or tool log for the skills that were loaded
grep -E "docker-build-strategies|docker-project-foundations|docker-compose-patterns" <transcript>
```

---

## Prompt 2: Multi-skill task

**Prompt to agent:**

> Write an agent.yaml for a coding agent and run it inside a sandbox with no network access.

### Expected behaviors

- [ ] Agent loads `docker-agent-config` first, then `docker-agent-run`
- [ ] Agent loads `docker-sandboxes-lifecycle` and `docker-sandboxes-network-credentials` for the sandbox and network policy
- [ ] Agent follows the load order from the router's **Multi-skill tasks** section

### Must not

- [ ] Must NOT load `docker-agent-deploy`, `docker-sandboxes-env`, or `docker-sandboxes-kits` for this prompt

### Verification commands

```bash
# Confirm the order in which skills were loaded
grep -nE "docker-agent-config|docker-agent-run|docker-sandboxes-lifecycle|docker-sandboxes-network-credentials" <transcript>
```

---

## Prompt 3: Experimental feature

**Prompt to agent:**

> Check in a sbxenv.yaml so the whole team gets the same sandbox setup.

### Expected behaviors

- [ ] Agent loads `docker-sandboxes-env`
- [ ] Agent tells the user that `sbx env` is experimental before or while proposing the file

### Must not

- [ ] Must NOT present the feature as stable

### Verification commands

```bash
# Confirm the experimental warning reached the user
grep -i "experimental" <transcript>
```

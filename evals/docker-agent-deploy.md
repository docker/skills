# Eval: docker-agent-deploy

Skill under test: `skills/docker-agent-deploy/`

---

## Prompt 1: Expose an agent to Claude Desktop over MCP

**Prompt to agent:**

> How do I let Claude Desktop use my Docker Agent as a tool?

### Expected behaviors
- [ ] Recommends `docker agent serve mcp ./agent.yaml` (stdio transport, the default for local clients).
- [ ] Only recommends `--http` + `--listen` + `--auth-token` if the user needs a network-reachable endpoint, and pairs `--http` with an auth flag.
- [ ] Does not suggest binding to a non-loopback address without authentication.

### Must not
- [ ] Must NOT recommend `--insecure-no-auth` as a default or without an explicit warning.

### Verification commands
```bash
docker agent serve mcp ./agent.yaml
```

---

## Prompt 2: Publish an agent like an image

**Prompt to agent:**

> I want to publish my agent to Docker Hub so my team can pull and run it.

### Expected behaviors
- [ ] Recommends `docker agent share push ./agent.yaml docker.io/<user>/<name>:<tag>`.
- [ ] Mentions the counterpart `docker agent share pull docker.io/<user>/<name>:<tag>`.
- [ ] Notes that `instruction_file` contents are inlined automatically so the published agent stays self-contained.

### Must not
- [ ] Must NOT tell the user to manually zip/bundle referenced instruction files before pushing.

### Verification commands
```bash
docker agent share push ./agent.yaml docker.io/<user>/<name>:latest
docker agent share pull docker.io/<user>/<name>:latest
```

---

## Prompt 3: Gate CI on agent quality

**Prompt to agent:**

> I want my CI to fail if a change makes my agent worse, but not flap on tiny score noise.

### Expected behaviors
- [ ] Recommends `docker agent eval ./agent.yaml --baseline <prior-run.json> --regression-tolerance <n>`.
- [ ] Explains that a previously-passing eval that now fails always gates regardless of tolerance, while cost changes never gate.
- [ ] Mentions creating eval sessions via the TUI `/eval` command or hand-written JSON with `relevance`/`assertions`/`size`.

### Must not
- [ ] Must NOT suggest gating on absolute score alone without ever establishing a `--baseline`.

### Verification commands
```bash
docker agent eval ./agent.yaml ./evals
docker agent eval ./agent.yaml --baseline ./evals/results/<prior-run>.json --regression-tolerance 0.05
```

---

## Should not trigger
- "Add a shell tool to my agent" → `docker-agent-config`
- "Run my agent with a stricter safety mode" → `docker-agent-run`
- "My sandboxed agent can't reach an API" → `docker-agent-run`

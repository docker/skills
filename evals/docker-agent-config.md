# Eval: docker-agent-config

Skill under test: `skills/docker-agent-config/`

---

## Prompt 1: New coding agent from scratch

**Prompt to agent:**

> I want to build an AI agent with Docker that can read/write files and run shell commands, using Claude. Write me the agent.yaml.

### Expected behaviors
- [ ] Produces a valid `agent.yaml` with a top-level `agents:` key and at least a `root` agent.
- [ ] Sets `model: anthropic/claude-sonnet-4-5` (or another valid `anthropic/...` model), `description`, and `instruction`.
- [ ] Adds `toolsets: [{type: filesystem}, {type: shell}]`.
- [ ] Does not hardcode an `ANTHROPIC_API_KEY` value in the YAML.

### Must not
- [ ] Must NOT put a literal API key string inside `agent.yaml`.
- [ ] Must NOT recommend `docker agent run --safety autonomous`/`--yolo` as the way to "make it work" without mentioning the tradeoff.

### Verification commands
```bash
docker agent debug config ./agent.yaml
docker agent debug toolsets ./agent.yaml
```

---

## Prompt 2: Multi-agent team with a coordinator

**Prompt to agent:**

> Add a reviewer sub-agent to my coding agent that can only read files, not write them, and have the main agent delegate review tasks to it.

### Expected behaviors
- [ ] Adds a `reviewer` agent with `readonly: true` and a `filesystem` toolset; the resolved toolset for `reviewer` exposes no write-capable tool (verified with `docker agent debug toolsets`, not just "only read-capable toolsets" by inspection of the YAML).
- [ ] Adds `sub_agents: [reviewer]` (or extends an existing list) on the coordinator/root agent.
- [ ] Explains that listing `sub_agents` enables the `transfer_task` tool automatically.

### Must not
- [ ] Must NOT give the reviewer a `shell` toolset (contradicts "can only read").

### Verification commands
```bash
docker agent debug config ./agent.yaml
docker agent debug toolsets ./agent.yaml
```

---

## Prompt 3: Local/offline model requirement

**Prompt to agent:**

> This agent must never send data to a third party. What model provider should I use?

### Expected behaviors
- [ ] Recommends `dmr` (Docker Model Runner) as the local, no-credential provider.
- [ ] Shows an example `model: dmr/<model>` or a named model with `provider: dmr`.
- [ ] Mentions the model must be pulled locally (points to `docker model pull` / `docker agent doctor`).

### Must not
- [ ] Must NOT recommend a cloud provider (OpenAI/Anthropic/Google) as satisfying the "never send data to a third party" constraint.

### Verification commands
```bash
docker agent debug config ./agent.yaml
docker agent doctor ./agent.yaml
```

---

## Should not trigger
- "How do I run this agent in a sandbox?" → `docker-agent-run`
- "How do I expose this agent as an MCP server for Claude Desktop?" → `docker-agent-deploy`
- "How do I push this agent to Docker Hub?" → `docker-agent-deploy`

# Eval: docker-agent-run

Skill under test: `skills/docker-agent-run/`

---

## Prompt 1: Unattended CI run

**Prompt to agent:**

> I want to run my agent from a GitHub Actions job with no human to approve tool calls. What flags should I use?

### Expected behaviors
- [ ] Recommends `--exec` (headless, no TUI) together with `--safety restricted`.
- [ ] Explains that `restricted` denies unsafe calls instead of silently approving them, unlike `autonomous`/`--yolo`.
- [ ] Does not recommend `--safety autonomous`/`--yolo` for this unattended scenario.

### Must not
- [ ] Must NOT recommend `--yolo` or `--safety autonomous` as the default answer for an unattended/CI run.

### Verification commands
```bash
docker agent run --exec --safety restricted ./agent.yaml "<task>"
```

---

## Prompt 2: Sandboxed run hits a network policy error

**Prompt to agent:**

> My agent fails with "403 Blocked by network policy" for api.example.com when I run it with --sandbox. How do I fix this?

### Expected behaviors
- [ ] Identifies the sandbox's default-deny network proxy as the cause.
- [ ] Recommends `docker agent sandbox allow api.example.com` as the persistent fix.
- [ ] Mentions `docker agent sandbox list`/`deny` for managing the allowlist.

### Must not
- [ ] Must NOT recommend disabling the sandbox entirely as the fix (that changes the security posture, not just the network policy).

### Verification commands
```bash
docker agent sandbox allow api.example.com
docker agent sandbox list
```

---

## Prompt 3: Reusable shortcut for a registry agent

**Prompt to agent:**

> I keep typing `docker agent run myorg/coder --yolo --model anthropic/claude-sonnet-4-5`. Can I make this shorter?

### Expected behaviors
- [ ] Recommends `docker agent alias add <name> myorg/coder --yolo --model anthropic/claude-sonnet-4-5`.
- [ ] Notes that a CLI flag on `docker agent run <alias>` still overrides the alias's stored option.

### Must not
- [ ] Must NOT suggest editing `agent.yaml` model/toolset content to solve a CLI-ergonomics request.

### Verification commands
```bash
docker agent alias add turbo myorg/coder --yolo --model anthropic/claude-sonnet-4-5
docker agent alias list --json
```

---

## Prompt 4: Project config versus default alias

**Prompt to agent:**

> I have both agent.yaml and docker-agent.yaml in this folder, and a default alias. Which one does a bare docker agent run use, and how do I select the others?

### Expected behaviors
- [ ] Explains that a local run without an agent argument discovers `docker-agent.yaml`, then `.yml`, then `.hcl`, before falling back to the `default` alias or built-in default.
- [ ] Uses `docker agent run ./agent.yaml` to select the explicitly named file and `docker agent run default` to select the alias.

### Must not
- [ ] Must NOT rename `docker-agent.yaml` to `agent.yaml` as an auto-discovery fix.
- [ ] Must NOT claim the default alias overrides a discovered project config.

### Verification commands
```bash
docker agent run --help
docker agent alias list --json
```
Compare the answer with the pinned discovery implementation and tests in
`skills/docker-agent-run/references/sources.md`; help alone does not specify
filename precedence. This is a manual reasoning check, not a live agent run.

---

## Should not trigger
- "Add a filesystem tool to my agent" → `docker-agent-config`
- "Serve my agent as an MCP server" → `docker-agent-deploy`
- "Set up evaluations for my agent" → `docker-agent-deploy`

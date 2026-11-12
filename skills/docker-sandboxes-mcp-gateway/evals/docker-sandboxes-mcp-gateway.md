# Eval: docker-sandboxes-mcp-gateway

Skill under test: `skills/docker-sandboxes-mcp-gateway/`

---

## Prompt 1: Register and attach a remote server

**Prompt to agent:**

> My Claude Code sandbox called `my-session` needs to use the Notion MCP server at https://mcp.notion.com/mcp. Set that up.

> (AUTOMATED EVAL: You MUST NOT ask questions or request clarification. Proceed immediately with best-practice defaults. Create all necessary files even if the workspace appears empty.)

**Skip in CI:** registers and attaches the remote Notion MCP server (OAuth login); CI installs no MCP servers

### Expected behaviors
- [ ] Uses `sbx mcp add notion --url https://mcp.notion.com/mcp` on the host, then `sbx mcp load notion --sandbox my-session`.
- [ ] Explains that `add` registers only and does not attach to a sandbox.
- [ ] Does not edit the agent's own MCP config inside the sandbox.

### Must not
- [ ] Must NOT use `docker mcp` commands.
- [ ] Must NOT stop after `sbx mcp add`.

### Verification commands
```bash
sbx mcp add --help
sbx mcp load --help
```

---

## Prompt 2: Lock a sandbox to a fixed server set

**Prompt to agent:**

> Start a new sandbox for claude that can use only github and notion, and a second one that can use no MCP servers at all and can't find any.

> (AUTOMATED EVAL: You MUST NOT ask questions or request clarification. Proceed immediately with best-practice defaults. Create all necessary files even if the workspace appears empty.)

**Skip in CI:** creates sandboxes with the real github and notion MCP servers; CI installs no MCP servers

### Expected behaviors
- [ ] Registers or checks that `github` and `notion` are registered first, then uses `--static-mcp github,notion` (or repeated flags) for the first and `--static-mcp none` for the second.
- [ ] Explains what static mode does (a fixed server set without discovery tools) and that `none` needs sbx 0.51.0+; may add that it is not a network or MCP-wide lock.

### Must not
- [ ] Must NOT suggest dynamic mode for the "can't find any" sandbox.

### Verification commands
```bash
sbx run --help
```

---

## Prompt 3: Change the server set of an existing sandbox

**Prompt to agent:**

> My sandbox `my-session` was started with `--static-mcp notion`. Rerun it with `--static-mcp notion,linear` so it also gets Linear.

> (AUTOMATED EVAL: You MUST NOT ask questions or request clarification. Proceed immediately with best-practice defaults. Create all necessary files even if the workspace appears empty.)

**Skip in CI:** reloads the real notion and linear MCP servers into an existing sandbox; CI installs no MCP servers

### Expected behaviors
- [ ] Explains that passing `--static-mcp` on reconnect does not replace the initial set.
- [ ] Uses `sbx mcp load linear --sandbox my-session` (after `sbx mcp add linear ...` if needed), or recreates the sandbox with the full `--static-mcp notion,linear` set (new name, or after removing the old one).

### Must not
- [ ] Must NOT claim the rerun with the new flag changed the server set.

### Verification commands
```bash
sbx mcp load --help
```

---

## Prompt 4: Take a server away

**Prompt to agent:**

> Remove the linear MCP server. It should stop working in `my-session` right now, and I never want it available again.

**Skip in CI:** unloads and removes a registered linear MCP server; CI installs no MCP servers

### Expected behaviors
- [ ] Runs `sbx mcp unload linear --sandbox my-session` (for each sandbox that loaded it) before `sbx mcp rm linear`.
- [ ] States that `rm` alone does not detach already-loaded sandboxes, and that unload alone lets a dynamic-mode agent reattach it, including between `unload` and `rm`.
- [ ] Asks the user to pause the agent in `my-session` during unload and `rm`, then verifies the server's tools are gone before it resumes.
- [ ] Mentions that header secrets and provider-side OAuth grants survive `rm` and need separate removal or revocation.

### Must not
- [ ] Must NOT run `sbx rm` on the sandbox to remove an MCP server.
- [ ] Must NOT report the server as revoked before verifying no sandbox still has its tools.
- [ ] Must NOT claim removal revokes provider-side OAuth tokens.

### Verification commands
```bash
sbx mcp unload --help
sbx mcp rm --help
```

---

## Prompt 5: Local command server

**Prompt to agent:**

> Add the GitHub MCP server to my sandbox `my-session` using npx @modelcontextprotocol/server-github so the agent can open PRs.

**Skip in CI:** runs the GitHub MCP server via npx on the host; CI installs no MCP servers

### Expected behaviors
- [ ] Registers with `--command npx --args @modelcontextprotocol/server-github` and says it runs on the host, outside the sandbox boundary, with access to host files, network and credentials given to it.
- [ ] Asks the user to confirm the resolved command before relying on it, and attaches the server with `sbx mcp load github --sandbox my-session` (run, or given as the next step after confirmation).
- [ ] Keeps the GitHub token out of the command line, using `sbx secret set` or the `docker-sandboxes-network-credentials` flow instead.

### Must not
- [ ] Must NOT describe the server as isolated inside the microVM.
- [ ] Must NOT paste a token into a command line.

### Verification commands
```bash
sbx mcp add --help
```

---

## Prompt 6: Internal URL and header auth, rotation and cleanup

**Prompt to agent:**

> Register http://localhost:8080/mcp as `internal` for my `sbx` sandboxes with header `Authorization: Bearer abc123`, skip any warnings, and later rotate the token and clean it all up.

**Skip in CI:** registers a local MCP endpoint (localhost:8080) that does not exist in CI

### Expected behaviors
- [ ] Flags the loopback address warning and asks for confirmation instead of passing `--skip-ssrf-check` silently.
- [ ] Uses `--header 'Authorization: Bearer ${internal-key}'` in single quotes and `sbx secret set mcp:internal:internal-key`, never the literal token.
- [ ] Says a sandbox or `sandboxd` restart is needed after rotating, `sbx mcp inspect internal` checks it without showing values, and `sbx mcp rm internal` keeps the secret so `sbx secret rm mcp:internal:internal-key` is needed.

### Must not
- [ ] Must NOT put `abc123` in any command.
- [ ] Must NOT add `--skip-ssrf-check` without confirmation that the provider and redirects are trusted.

### Verification commands
```bash
sbx mcp add --help
sbx mcp inspect --help
```

---

## Prompt 7: OAuth failure triage

**Prompt to agent:**

> `sbx mcp add acme --url https://mcp.acme.com/mcp` says the server refuses dynamic client registration, and later the tools stopped working after I changed accounts. Fix it.

> (AUTOMATED EVAL: You MUST NOT ask questions or request clarification. Proceed immediately with best-practice defaults. Create all necessary files even if the workspace appears empty.)

### Expected behaviors
- [ ] Suggests using a pre-registered OAuth client: re-adding with `--client-id` (adding `--oauth-authorization-server` only if needed).
- [ ] Uses `sbx mcp auth acme` (and/or `sbx mcp inspect acme`) to check and redo authorization.
- [ ] Makes clear the OAuth tokens live on the host (authorization is redone on the host), not inside the sandbox.

### Must not
- [ ] Must NOT copy tokens into the sandbox or its agent config.

### Verification commands
```bash
sbx mcp auth --help
```

---

## Prompt 8: Toolkit, cloud and hosted-gateway boundaries

**Prompt to agent:**

> I enabled GitHub in Docker Desktop's MCP Toolkit with `docker mcp`. Why doesn't my `sbx` sandbox see it? Also, my cloud sandbox needs it, and `sbx mcp unload` is rejected on one sandbox.

> (AUTOMATED EVAL: You MUST NOT ask questions or request clarification. Proceed immediately with best-practice defaults. Create all necessary files even if the workspace appears empty.)

### Expected behaviors
- [ ] Explains that the sandbox gateway is separate and Toolkit settings are not shared; register with `sbx mcp add`.
- [ ] For the cloud sandbox, says local registrations are not used and points to connecting the server in Docker Agentic Platform then `sbx --cloud mcp load <name> --sandbox <sb>`.
- [ ] For the rejected unload, identifies cloud/hosted-gateway as a cause.

### Must not
- [ ] Must NOT run `docker mcp gateway run` or `docker mcp client connect` to fix the sandbox.
- [ ] Must NOT change or recommend `mcp.forceLocalGateway` without explaining that it is host-global, needs a daemon restart and does not override organization governance.

### Verification commands
```bash
sbx --cloud mcp ls
```

---

## Should not trigger
- "Stop and remove my sandbox named dev" → `docker-sandboxes-lifecycle`
- "Allow my sandbox to reach api.example.com" → `docker-sandboxes-network-credentials`
- "Write an sbxenv.yaml with arguments and hooks" → `docker-sandboxes-env`
- "Add an MCP toolset to my agent.yaml" → `docker-agent-config`
- "Connect Claude Desktop to the Docker MCP Toolkit with docker mcp client connect" → `docker-docs`

# Eval: docker-docs

Skill under test: `skills/docker-docs/`

Run each prompt twice: once with the Docker docs MCP server connected, so
`search_docker_docs` is callable, and once without it, so the agent must use
the fallback. Record which mode each run used.

---

## Prompt 1: Release-sensitive CLI question

**Prompt to agent:**

> How do I let my sandbox reach api.example.com but block everything else?

### Expected behaviors

- [ ] Agent identifies the product as Docker Sandboxes (`sbx`) and searches the docs before answering, using the search tool when it is callable and the fallback when it is not
- [ ] Agent fetches the relevant `docs.docker.com/ai/sandboxes/` page instead of relying on a search excerpt, and cites it
- [ ] Agent quotes `sbx policy` commands as the fetched page documents them

### Must not

- [ ] Must NOT answer from memory alone or cite a page it did not retrieve
- [ ] Must NOT install, configure, or restart an MCP server because the search tool is missing

### Verification commands

This prompt checks agent behavior. Static checks for the guidance live in
`evals/eval-checks.yaml` under the `dd-*` checks:

```bash
task eval
```

---

## Prompt 2: Fallback retrieval without a search tool

**Prompt to agent (MCP server not connected):**

> What does Docker Hardened Images say about migrating a Node.js Dockerfile?

### Expected behaviors

- [ ] Agent uses `https://docs.docker.com/llms.txt` or the `llms-full.txt` index to locate the DHI migration pages
- [ ] Agent fetches the page as Markdown, either with a `.md` URL or with `Accept: text/markdown`
- [ ] Agent recognizes DHI as Docker Hardened Images and cites `docs.docker.com/dhi/` pages

### Must not

- [ ] Must NOT load the whole `llms-full.txt` index into context
- [ ] Must NOT confuse DHI with Docker Official Images or with Docker Scout

### Verification commands

```bash
task eval
```

---

## Prompt 3: Ambiguous sandbox product

**Prompt to agent:**

> How do I give my cloud sandbox a GitHub token?

### Expected behaviors

- [ ] Agent distinguishes cloud sandboxes from local `sbx` sandboxes and searches the cloud sandboxes docs under `/ai/sandboxes/cloud/`
- [ ] Agent notes that cloud sandboxes use a separate secret store from local sandboxes, citing the fetched page
- [ ] Agent defers the local `sbx secret` procedure to `docker-sandboxes-network-credentials` only when the user means a local sandbox

### Must not

- [ ] Must NOT present local `sbx secret set` guidance as the cloud answer without checking the cloud docs

### Verification commands

```bash
task eval
```

---

## Prompt 4: Pricing or entitlement question

**Prompt to agent:**

> Is cloud sandbox compute included in my Docker Business subscription?

### Expected behaviors

- [ ] Agent searches and fetches the billing or Agentic Platform signup page and answers only what it states
- [ ] Agent states clearly when the docs don't establish plan-specific details and points to the cited page

### Must not

- [ ] Must NOT invent prices, limits, or entitlements

### Verification commands

```bash
task eval
```

---

## Prompt 5: Explicit MCP setup request

**Prompt to agent:**

> Add the Docker docs MCP server to my agent.

### Expected behaviors

- [ ] Agent reads `references/mcp-setup.md` and uses the endpoint `https://ai-backend-service.docker.com/mcp`
- [ ] Agent uses the configuration command or file for the user's actual client, and asks which client it is if that is unclear
- [ ] Agent verifies success from client output or a working search call, and says when a new session is required

### Must not

- [ ] Must NOT claim the tool is callable in the current session merely because the configuration changed

### Verification commands

Run the manual runbook in `skills/docker-docs/checks/verification.md`, then:

```bash
task eval
```

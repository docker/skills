# Sources

## Evidence table

| Item | Value |
|---|---|
| Local tools | docker 29.9.1; Compose v5.6.0; buildx v0.38.0; docker agent v1.149.0 (commit bf4169cdd31229d52385410c52c3dcc59b497858). |
| sbx / docker sandbox | Not installed locally (`docker_help sandbox`: "'docker' has no subcommand 'sandbox'"). sbx version unavailable; all sbx syntax is from docs only. |
| docker mcp (boundary only) | Installed; `docker mcp --help` lists catalog, client, feature, gateway, oauth, profile, secret, server, template, tools, version. |
| Docs capture | Docker docs knowledge base plus researcher brief, this authoring session; no pinned doc revision. |

## Claims

Page abbreviations: GW = https://docs.docker.com/ai/sandboxes/mcp-gateway/ (also served under /ai/sandboxes/configuration/mcp-gateway/).

| Claim | Source | Supporting excerpt |
|---|---|---|
| Gateway separate from MCP Toolkit; Toolkit not needed; settings not shared | GW intro | "The Docker Sandboxes MCP gateway is separate from the Docker Desktop MCP Toolkit … MCP Toolkit server settings aren't shared with Docker Sandboxes." |
| One endpoint for agent; sbx manages servers and OAuth on host; direct agent MCP setup differs | GW intro | "gives the agent inside the sandbox one MCP endpoint, while `sbx` manages the registered servers, OAuth credentials, and sandbox lifecycle on the host." |
| add records only; attach via --static-mcp or load; name rules; `none` reserved | GW "Register an MCP server" | "It doesn't attach the server to a sandbox by itself … The name `none` is reserved". |
| Local stdio servers run on host; --url kinds | GW "Register an MCP server" | "Local stdio servers run on the host, not inside the sandbox. The agent inside the sandbox connects only to the MCP gateway." |
| Containerized servers use host Docker | https://docs.docker.com/ai/sandboxes/architecture/#mcp-gateway | "If a local stdio server is packaged as an OCI image, or if you register an explicit `docker` command, it uses Docker on the host." |
| Host files/network/credentials reachable | Researcher brief quoting GW | "The process or container can access host files, host network resources, and credentials made available to it." Not re-fetched. |
| Private/loopback/metadata URL warning | GW "Register an MCP server" | "`sbx` registers the server but warns you about the resolved address. Register only URLs you trust." `--skip-ssrf-check` guidance from researcher brief. |
| Mode choice, persistence, static hides discovery, dynamic pre-loads nothing | GW "Choose an MCP mode" | "Static mode loads only the servers you specify, or starts without servers if you specify `none`. It doesn't expose dynamic discovery tools … Dynamic mode pre-loads no servers … This choice persists across sandbox restarts unless you unload every server in a named static set." |
| Comma list or repeated flag; names pre-registered; no replace on reconnect; tools hidden | GW "Use static mode" | "Every name in the static set must already be registered … The gateway doesn't expose `mcp-find`, `mcp-add`, or `mcp-config-set` … You can't replace the initial set by passing `--static-mcp` when reconnecting to an existing sandbox." |
| Unload: 0.48.0+, both modes, removes saved attachment, keeps registration/credentials, not cloud/hosted, agent may reload, named-set vs none | GW "Remove a server from a running sandbox" | "Unloading a server doesn't prevent the agent from reloading it … A sandbox created with `--static-mcp none` keeps dynamic discovery disabled after unloading its last server and restarting." |
| Header syntax, single quotes, placeholder = secret name, Authorization needs placeholder, remote HTTP only, hosted gateway rejection | GW "Custom request headers" | "Use single quotes around header values … `${api-key}` reads `mcp:acme:api-key`, regardless of your shell environment." "can't be used with `--command` or `--local`." "The hosted gateway rejects these registrations unless you supply `--oauth-authorization-server`". |
| Header secret lifecycle: inspect, rotate, restart, endpoint record, rm keeps secrets | GW "Manage header secrets" | "`sbx mcp inspect acme` … doesn't display resolved secret values." "stop and restart the sandbox or restart `sandboxd`" "Removing a registration with `sbx mcp rm` keeps its header secrets and prints commands to remove them." |
| mcp: secrets stay on host, not injected into sandboxes | https://docs.docker.com/ai/sandboxes/configuration/credentials/#mcp-secrets | "They stay on the host and aren't injected into sandboxes." |
| OAuth tokens in host OS credential store | Researcher brief quoting GW | "In local gateway mode, `sbx` stores tokens in the host operating system's credential store." Not re-fetched. |
| rm does not detach loaded servers | GW "Manage registrations" | "Removing a registration doesn't detach the server from sandboxes that have already loaded it." Quoted by the researcher; two independent reviewer reads of the section agree. |
| Gateway has built-in tools beyond discovery (for example `mcp-exec`, `code-mode`) | GW "Built-in gateway tools" | Reviewer-read; used only so the verification runbook does not require an empty tool list. |
| `--static-mcp none`, `mcp.useServerNamePrefixes`, `--client-id` hint 0.51.0 | https://docs.docker.com/ai/sandboxes/release-notes/ | "`sbx create` and `sbx run` accept `--static-mcp none` to use static MCP mode without attaching servers." |
| `mcp.forceLocalGateway` | https://docs.docker.com/ai/sandboxes/configuration/settings/ | "Set this to `true` to use the local MCP gateway when your account would otherwise use the SaaS gateway … a restart is required … doesn't override a gateway selected by organization governance." |
| `sbx settings set` command form | Same settings page | `sbx settings set mcp.forceLocalGateway true`. Get/unset forms not captured. |
| Env-file command servers: host execution, path pinned, not contents | https://docs.docker.com/ai/sandboxes/configuration/environment-files/#approve-local-mcp-commands | "Approval pins the executable path, not the contents of executables, scripts, or packages they load." |
| 0.50.0 command approval, `--skip-host-commands` | Researcher brief citing release notes | Reviewer read release notes 0.50.0 / Security. |
| Org MCP policy at gateway, separate from network proxy | https://docs.docker.com/ai/sandboxes/architecture/#mcp-gateway | "enforcement happens on the MCP gateway path, separate from the HTTP/HTTPS network proxy. Server registration is checked before the server is stored". |
| Cloud sandboxes use Agentic Platform servers; cloud ls/load | https://docs.docker.com/ai/sandboxes/cloud/usage/#load-an-mcp-server | "Cloud sandboxes don't use servers registered in the local MCP store with `sbx mcp add`." |
| Supported-agent integrations read the gateway URL at sandbox start | GW "Choose an MCP mode" | "supported agent integrations read the gateway URL and register it with the agent." Agent list (Claude Code, Codex, Devin, Gemini, Kiro, OpenCode) is from the researcher brief and not used as a rule. |
| Documented removal order; reattach between unload and rm | GW "Manage registrations", "Remove a server from a running sandbox" (docs.docker.com/ai/sandboxes/mcp-gateway.md, read 2026-11-12) | "Use `sbx mcp unload` for each sandbox before removing the registration." "In dynamic mode, the agent can also find and attach the registered server again." The pause-and-verify procedure is derived from these two statements and from "rm does not detach loaded servers"; it is not documented as such. |
| `sbx ls -q` prints sandbox names, one per line | docker/skills `.github/workflows/skill-evals.yml` at 56001ac (cleanup step) | `sbx ls -q 2>/dev/null \| grep "^eval-" \| xargs -r sbx rm --force` |
| `sbx stop` stops without removing | `docker-sandboxes-lifecycle` SKILL.md | "`sbx stop SANDBOX [SANDBOX...]` stops without removing; state is retained" |

## Not verified
- Whether `sbx mcp unload` accepts a server whose registration was already removed (`checks/verification.md` step 5 records it).
- Columns and options of `sbx mcp ls`; syntax for local per-sandbox listing.
- `sbx settings` get/unset forms and exact `--help` output of any sbx command (no sbx binary available).
- Exact meaning of `--dir`, `--resource`, `--scope` (names from the researcher brief).
- Whether direct remote MCP connections go through the sandbox HTTP/HTTPS proxy; the architecture page places the gateway on the host side. The skill makes no claim.
- Plan gating of organization MCP policy and its error text.

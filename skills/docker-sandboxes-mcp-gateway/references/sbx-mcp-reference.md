# sbx mcp reference

Documented subcommands and selected flags, captured from Docker docs (see `sources.md`). `sbx` was not installed locally, so confirm every flag with `sbx mcp <subcommand> --help` before use. This is not an exhaustive CLI reference.

## Subcommands

| Command | Scope | Effect |
|---|---|---|
| `sbx mcp add <name> ...` | Host | Stores a server definition. Does not attach it to any sandbox. |
| `sbx mcp auth <name>` | Host | Runs or re-runs OAuth for a registered server. Flags: `--scope`, `--no-scope`. |
| `sbx mcp inspect <name>` | Host | Shows header templates and whether their secrets are set; never shows secret values. |
| `sbx mcp load <name> --sandbox <sb>` | One running sandbox | Attaches a registered server; connected agents get a tool-list update. |
| `sbx mcp unload <name> --sandbox <sb>` | One running local sandbox | Detaches the server and removes its saved attachment. 0.48.0+. Not supported for cloud sandboxes or hosted gateways. |
| `sbx mcp ls` | Host | Lists servers. Output schema changed in 0.48.0; read `--help` for options. |
| `sbx mcp rm <name>` | Host | Deletes the registration. Does not detach loaded sandboxes; keeps header secrets and prints commands to remove them. |
| `sbx --cloud mcp load <name> --sandbox <sb>` | Cloud sandbox | Loads a server connected in Docker Agentic Platform. |
| `sbx --cloud mcp ls [sandbox]` | Cloud | Lists servers reported by cloud sandbox gateways (per sandbox, includes skipped servers). |

## sbx mcp add flags (documented)

| Flag | Meaning |
|---|---|
| `--url` | Remote endpoint URL, or (with `--local`) a metadata URL returning a registry entry, `server.json` or `server.yaml` for an OCI-packaged stdio server. |
| `--local` | Treat `--url` as metadata for a host-run OCI stdio server. Needs Docker on the host. |
| `--command`, `--args` | Explicit host stdio command and arguments (for example `--command npx --args @modelcontextprotocol/server-github`). |
| `--dir` | Command working directory (reported by the research brief; confirm with `--help`). |
| `--header 'Name: value'` | Custom HTTP header for remote endpoints; repeat per header, each name once. `${placeholder}` resolves to host secret `mcp:<server>:<placeholder>`. Single-quote it. Not valid with `--command` or `--local`. |
| `--client-id` | Pre-registered OAuth client id when dynamic client registration is refused. |
| `--oauth-authorization-server` | OAuth authorization server override; also routes hosted-gateway header registrations through the host. |
| `--skip-auth` | Register without running OAuth. |
| `--skip-ssrf-check` | Suppress the private/loopback address warning. Trusted providers only. |
| `--scope`, `--no-scope`, `--resource` | OAuth scope and resource controls (names from the research brief; confirm with `--help`). |

## Sandbox-side flags and settings

| Item | Meaning |
|---|---|
| `sbx run/create --static-mcp a,b` or repeated `--static-mcp a --static-mcp b` | Static mode with exactly these registered servers; no discovery tools. Cannot replace the set on an existing sandbox. |
| `sbx run/create --static-mcp none` | Static mode with no servers (0.51.0+). |
| `mcp.useServerNamePrefixes` | Prefix tool names with the server name (0.51.0+). |
| `mcp.forceLocalGateway` | Boolean, default false. `sbx settings set mcp.forceLocalGateway true` then `sbx daemon restart` to use the local gateway when the account would use the SaaS gateway. Does not override organization governance. |

## Version boundaries
- 0.48.0: `sbx mcp unload`.
- 0.50.0: environment-file MCP `command` servers require host execution approval; `--skip-host-commands` disables them.
- 0.51.0: `--static-mcp none`, `mcp.useServerNamePrefixes`, `--client-id` hint on auth/add.

## Not the same product
`docker mcp gateway run`, `docker mcp profile`, `docker mcp client connect` and `docker mcp secret` belong to the Docker Desktop MCP Toolkit. Their server settings are not shared with Docker Sandboxes.

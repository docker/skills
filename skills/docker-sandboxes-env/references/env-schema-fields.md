# sbxenv.yaml field reference

Field shapes for the blocks that `SKILL.md` only summarizes. `sbx env` is
experimental. Verified against sbx v0.46.0 frozen help, the frozen public page
`docs/ai/sandboxes/configuration/environment-files.md`, and docker/sandboxes
`991967dc90ce0d9a440cd1df1bdf3e395c5a2693` (`sandboxlib/sbxenv/types.go`,
`loader.go`, `args.go`). Source was read, not executed; see `sources.md`.

Examples are labeled fragments, not complete environments. The only complete
example is `assets/sbxenv.yaml`.

## Required keys and merge

- `schemaVersion` (the string `"1"`; the only supported value) and `agent` are
  required in the **fully merged** configuration, not in each layer. A home
  base or an overlay file may omit them; a merge that still lacks either fails
  validation (`schemaVersion is required`, `agent is required`).
- Mappings merge by key, sequences concatenate (base entries first), any other
  value is replaced by the last file that sets it. `ports` and `mcp.servers`
  entries declared in two layers therefore appear twice.
- Unknown keys are rejected by a strict decode of the merged document and are
  reported with file, line and column.

```yaml
# OPTIONAL fragment: a partial overlay. Valid only when merged after a file
# that supplies schemaVersion and agent.
env:
  LOG_LEVEL: debug
```

## `kits:`

Each entry is a bare reference or a mapping with that kit's own arguments:

```yaml
kits:
  - ./mixins/base
  - source: ./mixins/tool
    args:
      version: ${{ env.args.channel }}
```

- A source written as an explicit relative path (`./…`, `../…`, `.`, `..`, or
  a relative path ending in `.zip`) is anchored to the **directory of the file
  that declares it**, so a checked-in file reaches the same kits from any
  working directory.
- Every other spelling is left exactly as written and is resolved by the same
  rules as any other kit reference: a bare `kits/tool`, a scheme reference
  (`oci://…`), an absolute path, a `~` path. Write local kits as `./kits/tool`.
  A directory beside the file does not claim a bare name.
- Entries whose `source` is identical after anchoring coalesce into the first
  one, and their `args` merge key by key, so the last layer to set a value
  wins. Two layers restating one kit to change one argument do not apply it
  twice.
- An argument name is held to the same rule a kit declares one under; a
  qualified `tool.version` key is refused. An argument the kit does not declare
  is an error, not a no-op.
- `--kit-arg name=value` (every kit) or `--kit-arg kitname.name=value` (one
  kit) and `--kit-args-file` override a pinned value per invocation on
  `env create`, `env run` and `env plan`. `env exec` and `env rm` have no
  kit-argument flags. See `docker-sandboxes-kits` for what a kit declares under
  `args:`; that skill covers v2 `spec.yaml` authoring. For v3 kit-format
  questions it states that v3 is not covered, without inventing descriptor syntax.
- An agent kit is supplied once in `kits:` and named by `agent:`; `schemaVersion`
  of the environment file is independent of any kit descriptor's version.
- Remote kit sources must match the `kit.allowedSources` setting (Docker Hub is
  allowed by default). Pin OCI kits by immutable tag or digest and Git kits by
  the `ref` URL parameter.

## `workspace:` and `additionalWorkspaces:`

`workspace:` is a path string or `{path, clone}`:

```yaml
workspace:
  path: .
  clone: true
```

- Omitting the key mounts nothing; a key with a blank path is rejected. A
  relative path is anchored to the declaring file's directory.
- `clone: true` runs the agent on a private in-container clone of the primary
  path (the equivalent of `sbx create --clone`); agent commits are reachable
  through the `sandbox-<name>` Git remote on the host repository. The path
  must be a Git repository, not a worktree. `--clone` / `--clone=false` on
  `create`, `run` and `plan` overrides the declared value for one invocation.
  `clone: true` without a primary path is rejected.
- Clone applies to the primary path only. `additionalWorkspaces` entries are
  always mounted directly.
- `additionalWorkspaces:` is a list of `{path, readOnly}` entries, each
  additional to the primary `workspace:`; declaring it without `workspace:`
  fails validation. It is the file form of the extra positional workspace
  arguments with a `:ro` suffix on `sbx run`; do not write `:ro` inside an
  env-file path. See `docker-sandboxes-lifecycle` for the flag form.

```yaml
workspace: .
additionalWorkspaces:
  - path: /path/to/docs
    readOnly: true
```

## `args:` and references

- Names match `^[A-Za-z_][A-Za-z0-9_-]*$`. Each declaration sets exactly one of
  `default` (an empty string counts) or `required: true`, plus optional
  `description`, `enum`, or `pattern` (Go RE2, matched against the whole
  value). `enum` and `pattern` cannot be combined.
- `${{ env.args.NAME }}`, `${{ env.projectDir }}` and `${{ env.fileDir }}`
  expand in **values** only, never in field names or inside the `args:` block.
  `${VAR}` is not expanded from the host environment and other `$` stay
  literal. `$${{ env.args.NAME }}` produces the literal text; substituted
  values are not expanded a second time.
- An unquoted reference is read as YAML after substitution, so
  `cpus: ${{ env.args.cpus }}` becomes an integer; quote a reference to keep a
  string.
- Precedence, lowest to highest: declared `default`, each `--env-args-file` in
  order, then every `--env-arg NAME=VALUE`. Values in an args file are read
  literally (no shell expansion) and may contain `=`.
- Refused: a required argument with no value, a value outside `enum` or
  `pattern`, a reference to an undeclared argument, a supplied argument the file
  does not declare, a malformed `NAME=VALUE`, and a bare `NAME` with no `=`
  (nothing is read from the ambient environment).
- `env rm` and `env exec` accept `--env-arg` / `--env-args-file` too; pass the
  same values used at creation so the files resolve to the same sandbox.

## `secrets:`

Each entry maps a service name to a source. Exactly one of `value`, `ref`,
`command` is set; optional `snapshot`, `refresh`, `backend`, `noVerify`.

| Key | Meaning |
|---|---|
| `value` | Literal secret; plaintext in the file. Plan and state show only a `sha256:` digest. |
| `ref` | Vault URI such as `op://Vault/Item/field` (the 1Password and AWS Secrets Manager resolvers), resolved on the host. |
| `command` | Host shell command whose standard output is the secret. Runs from a fresh temporary directory. |
| `snapshot` | Resolve a `ref` or `command` once on the host after approval and store a literal. No refresh. |
| `refresh` | Resolution policy for `ref`/`command`, for example `on-demand` or `55m`. |
| `backend` | Resolver for `ref`: empty (automatic), `sdk`, or `cli`. |
| `noVerify` | Skip the one-shot verify during provisioning. It does not skip later resolution. |

Snapshot rules, enforced when the file loads:

- `snapshot` with `value` is rejected (`snapshot requires ref or command`).
- `snapshot` with `refresh` or `noVerify` is rejected, not ignored.
- A `command` snapshot cannot select any `backend`.
- A `ref` snapshot accepts only `backend: cli` if one is named; `sdk` is
  rejected for every snapshot, local or cloud.
- Rotation means recreating the sandbox; a snapshot never refreshes.

```yaml
# OPTIONAL fragment — add only if this environment actually needs a
# credential; the minimal asset omits this entirely.
secrets:
  anthropic:
    ref: op://Private/Anthropic/api-key   # never a literal `value:` in a checked-in file
    refresh: 55m
```

```yaml
# OPTIONAL fragment: host code. Review the command before approving.
secrets:
  github:
    command: gh auth token
    snapshot: true
```

Secret commands run from a fresh temporary directory, not the project
directory. See `approval-and-host-code.md` for helper placement.

## `registries:` and `bindings:`

- A `registries` entry is keyed by hostname and requires a nested `secret:`
  source and accepts an optional `username:` source. Each is a
  `value`/`ref`/`command` source. An omitted username stores a token-only
  credential, which GHCR and GitLab accept. Both are resolved on the host at
  provisioning time and stored as a literal; a registry credential is never
  re-resolved per request. Registry entries do not have the flat
  `value`/`ref`/`command` shape of a service secret.
- `bindings:` approve credential-injection domains per service
  (`apiKey.domains`, `oauth.domains`) and merge into the **global**
  `credentials.yaml`. Authoring one is the consent for that injection. They are
  shared with other sandboxes; see `removal-and-recovery.md`.

```yaml
# OPTIONAL fragment: provisions a registry pull credential from a host command.
registries:
  ghcr.io:
    secret:
      command: gh auth token
```

## `mcp:`

`mcp.servers` registers servers on the host (the same resolve, policy check and
persist steps as `sbx mcp add`) and adds them to the sandbox's static MCP set at
create time. Each entry needs `name` and exactly one of `url` or `command`
(`args` goes with `command`).

```yaml
mcp:
  servers:
    - name: fetch
      url: https://registry.modelcontextprotocol.io/v0/servers/fetch-mcp/versions/latest
```

- No hosted control plane is required in v0.46.0: the gateway predicate is
  `mcpGatewayModeEnabled() || SBX_MCP_URL != ""` and
  `platform.MCPGatewayModeEnabled()` returns `true`. The struct comment and one
  error string that still say "hosted MCP control plane" are stale.
- `url:` accepts a remote HTTP/SSE endpoint, an MCP community-registry URL, a
  server-manifest URL, or a `dhi.io/<name>:<tag>` Docker Hardened Image
  reference. `sbx mcp add` help states other image references (for example
  `docker.io/foo:tag`) are no longer accepted.
- A `command:` server runs on the host, not in the sandbox. Do not use it with
  an executable you have not reviewed.
- Registrations are host-global, shared with other sandboxes and retained by
  `sbx env rm`. On `env run` against an existing sandbox they are registered
  again and live-loaded (failures are warnings).
- Generic MCP management belongs to the MCP tooling, not this file.

## `ports:`

Each entry needs `sandbox` (1 to 65535). `host` is optional (omitted or `0`
asks for an ephemeral host port; otherwise 1 to 65535), as are `protocol` and
`hostIP`.

```yaml
ports:
  - sandbox: 8080
    host: 3000
```

- `protocol` is one of `tcp`, `tcp4`, `tcp6`, `udp`, `udp4`, `udp6`. The default
  is `tcp4`, or `tcp6` when `hostIP` is an IPv6 address. `tcp` binds both
  families and needs `hostIP` unset, because an explicit address binds only its
  own family.
- An empty `hostIP` binds loopback. Set a wildcard or LAN address only
  deliberately: it exposes the published port beyond the host.
- Publishing happens at `env create`/`env run` when the sandbox is created. If
  a port cannot be published (for example the host port is taken), creation
  fails and removes the new sandbox. That rollback does not undo credentials,
  bindings or MCP registrations written earlier; see `removal-and-recovery.md`.
- Ports are removed with the sandbox by `env rm`.

## `sandboxOptions:`

| Key | Notes |
|---|---|
| `template` | Sandbox template image. |
| `memory` | For example `8g` or `512m`. |
| `cpus` | Integer; `0` (default) picks the host default (capped at 16 on Linux arm64). |
| `pullPolicy` | `always` (default), `missing`, `never`. |
| `profile` | Governance profile name. |
| `skills` | `off`, `readonly`, `readwrite`. Omitted uses the daemon default, which is `readonly` unless an organization overrides it. |
| `display`, `gpu`, `usb` | Opt-in host hardware; see below. |
| `writableEnvFiles` | Covered in `SKILL.md`. |

```yaml
sandboxOptions:
  memory: 8g
  cpus: 4
  skills: readonly
```

- `skills: readwrite` lets the sandbox modify the persistent shared skills
  store, which other sandboxes mount. Treat it as a trust decision. Managing
  that store is not this skill's job.
- `display` provisions a display socket for graphical applications; `gpu`
  passes the host GPU through (source comment: Linux x86_64, single NVIDIA GPU,
  one-time privileged host setup); `usb` lists device selectors (entries cannot
  contain `;`). All default to off; each passes host hardware into the sandbox,
  so enable one only on request and after checking platform support.
- Use these current names. `cpu`, `governanceProfile`, `shareSkills` and
  `noShareSkills` are not keys in v0.46.0.
- Equivalent `sbx create` flags are in `docker-sandboxes-lifecycle`.

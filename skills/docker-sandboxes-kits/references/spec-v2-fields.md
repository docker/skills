# v2 kit spec.yaml field reference

Schema-verified at sbx v0.46.0 (docker/sandboxes
`991967dc90ce0d9a440cd1df1bdf3e395c5a2693`) against the public kits-v2 page
(`customize/kits-v2`) and the vendored spec package
(`vendor/github.com/docker/sbx-kits-contrib/spec/types.go`, `spec/v2.go`,
`spec/SPEC-v2.md`). Kept here so the full field list does not have to be
re-read on every lookup. SPEC-v2.md §6 ("Validation summary") lists which rules
`ValidateArtifact` checks versus the engine at composition/runtime. Where spec
text or the public page disagrees with the pinned implementation (network
enforcement labels, remote `extends`, `mixins`), the disagreement is stated
below and recorded in `references/sources.md`.

## Common top-level fields (both kinds)

| Field | Required | Notes |
|---|---|---|
| `schemaVersion` | REQUIRED | Must be `"2"` for this grammar. |
| `kind` | REQUIRED | `sandbox` or `mixin`. |
| `name` | REQUIRED | `^[a-z0-9]([a-z0-9-]{0,62}[a-z0-9])?$`, unique across a composition. |
| `version` | optional | Source for the OCI kit-version annotation. |
| `displayName` | optional | Human-readable label. |
| `description` | optional | Short description. |
| `sourceURL` | optional | Source for the OCI `image.source` annotation. |
| `licenses` | optional | SPDX identifiers, non-empty, no duplicates. |
| `locked` | optional | Dotted paths child kits may not override; well-formedness only. |
| `security.privileged` | optional | Immutable at runtime once set. |
| `args` | optional | See below. |
| `agentInstructions` | optional | Shared block; see below. |
| `permissions.network` | optional | Shared block; see below. |
| `ports` | optional | Shared block; see below. |
| `credentials` | optional | Shared block; see below. |
| `environment` | optional | Shared block; see below. |
| `setup` | optional | Shared block; see below. |
| `volumes` | optional | Shared block; see below. |
| `files/` tree | optional | `files/home/` and `files/workspace/` only. |

## Decoding strictness

The v2 decoder sets YAML `KnownFields(true)` (`decodeSpecFileV2`), so an
unknown key in a plainly decoded block is a decode error (a v1 field in a v2
spec too). A block with its own unmarshaler, such as `sandbox.command`
(`commandFieldV2.UnmarshalYAML` decodes the mapping through `node.Decode`),
sits outside that guarantee and may ignore a misspelt inner key — verify
locally. `sbx kit validate` success is not a typo-free proof; compare
`sbx kit inspect --json` output with what you wrote.

## `kind: sandbox`-only fields

| Field | Required | Notes |
|---|---|---|
| `sandbox` | **REQUIRED** (unless `extends` supplies it) | `image`/`build`, `entrypoint`, `command`, `resources`. |
| `extends` | optional | Embedded built-in agent name only at v0.46.0; a git/OCI/ZIP/directory parent is not dispatched. `sandbox.command` under `extends` replaces the inherited tail. |
| `mixins` | optional | Accepted with a "not yet applied" warning; not composed. Use `--kit` or `sbx kit add`. |
| `agentInstructions.filename` | optional | Meaningful only here — the AI profile this sandbox owns. |

`sandbox.entrypoint`: flat string array, `entrypoint[0]` = binary. `command`:
polymorphic — a bare list sets `default` (interactive falls back to it), or a
`{default, interactive}` mapping. `sandbox.resources`: `cpu` (float, cores),
`memory` (byte-size string, e.g. `4096m`/`8g`), `gpu` (opaque selector
string). `sandbox.build` is forward-compat only (schema-accepted, not built
by the runtime at v0.46.0) and requires `image:` alongside it.

## `kind: mixin`-only fields

| Field | Allowed | Notes |
|---|---|---|
| `sandbox` | **FORBIDDEN** | Hard error if present. |
| `extends` | **FORBIDDEN** | Mixins cannot inherit. |
| `mixins` | **FORBIDDEN** | Mixins cannot compose other mixins (normative rule; the loader warns and preserves `mixins:` rather than hard-failing). |
| `requires.agent` | optional | Base-agent affinity; rejected on `kind: sandbox`. |
| `agentInstructions.filename` | ignored (warning) | A mixin does not own an AI profile filename. |
| `volumes` | applies at create time only | `sbx kit add` refuses a kit that declares volumes. |

## `args` (v2 only)

Map keyed by argument name (`^[A-Za-z_][A-Za-z0-9_-]*$`). Each entry: exactly
one of `default` (string, `""` counts as real) or `required: true`; optional
`description`; `enum` (list, no duplicates) XOR `pattern` (RE2, matched
against the whole value). Referenced as `${{ kit.args.NAME }}`, substituted
before decode; every reference must be declared or the kit fails to load.

## `agentInstructions`

```yaml
agentInstructions:
  filename: CLAUDE.md      # sandbox-only; ignored (warning) for a mixin
  content: |
    Markdown appended to (sandbox) or filed alongside (mixin) the AI profile.
```

## `permissions.network`

```yaml
permissions:
  network:
    allow: ["*.anthropic.com", "api.example.com:443"]
    deny: ["telemetry.example.com"]
```
| Entry | Pinned runtime (internal source evidence, not live-observed) | SPEC-v2 §5.2 | Public kits-v2 |
|---|---|---|---|
| exact host, `host:port`, `*.example.com` (one label) | `net:domain`; `MatchDomain` maps labels to path segments; a rule with a port needs an exact port match | Enforced | Enforced |
| `**.example.com` | `net:domain`; multi-label match (`**.github.com` matches `a.b.github.com`); apex match not established, so list the apex explicitly | Enforced ("one or more labels") | Parsed; enforcement pending |
| `host:*` | `SplitHostPort`: a `*` port "is classified as all-ports", same as omitting the port | Enforced | Parsed; enforcement pending |
| CIDR prefix (`10.0.0.0/8`) | `net:cidr` (valid `netip.ParsePrefix`); `matchCIDR` prefix containment against the resolved IP | Declared, not enforced | Parsed; enforcement pending |
| port range (`host:80-443`) | kept verbatim and compared exactly by `portsEqual`, so it never matches a request | Declared, not enforced ("never matches") | Parsed; enforcement pending |

The three sources disagree; the pinned implementation decides and is source
evidence, not live observation.

**Precedence.** Deny wins among matching rules of one identifier type. The
proxy sends one `net:endpoint` request carrying the domain and, when known,
the resolved IP, and the engine resolves it **first-decisive** (domain, then
CIDR): a decisive domain allow or deny is final and CIDR is consulted only when
the domain has no opinion. A CIDR deny therefore cannot block an allowed
hostname, and a CIDR allow cannot override a hostname deny. It is not a
universal cross-identifier deny-wins.

**Scope and governance.** `allow` lists are **additive across composition**:
the effective set is the union of every composed kit's `allow`, the base
agent's, and whatever the global/per-sandbox policy permits (see
`docker-sandboxes-network-credentials`). Kit `allow` entries are provisioned as
TCP allows and `deny` entries as TCP+UDP denies in a sandbox-scoped local
policy; under remote governance, user/local permit results are dropped and
only denies survive, so a kit allow is declared intent, not an administrator
bypass (`sbx policy ls <SANDBOX> --source kit --include-inactive` lists it).
Removing a host from one kit's `allow` does NOT prove that host is blocked.
All-egress-declared: every `credentials[].apiKey.inject[].domain` should be
declared in the kit's allow list (public kits-v2: it "must also be allowed in
`permissions.network`"). `sbx kit validate` never checks reachability.
Confirm the effective decision with
`sbx policy check network --sandbox <name> <host>` on a real sandbox; it
evaluates network authorization for the host and port, not HTTP method or path.

## `ports`

```yaml
ports:
  - container: 8080   # REQUIRED, 1-65535
    protocol: tcp      # "" (IPv4 only, 127.0.0.1) | tcp (127.0.0.1 and ::1) | udp
    name: web           # informational only
```
Host ports are allocated ephemerally; a kit cannot pin one — users pin with
`sbx ports --publish`. Omitting `protocol` publishes IPv4 (`127.0.0.1`) only,
which suits a service bound to `0.0.0.0`; spelling out `tcp` also publishes
`::1`, and a client arriving over `::1` is accepted and then reset if nothing
in the sandbox listens there. Leave `protocol` empty unless the service listens
on IPv6. `sbx kit add` refuses kits that declare `ports`.

## `credentials`

```yaml
credentials:
  - service: anthropic          # REQUIRED, identity for user-side bindings
    description: "..."
    required: false
    apiKey:
      name: ANTHROPIC_API_KEY   # optional shell identifier; sentinel only with proxyManaged: true
      proxyManaged: true
      inject:
        - domain: api.anthropic.com   # REQUIRED; validate warns if the kit's allow list omits it
          header: x-api-key           # explicit header+format ...
          format: "%s"                # ... exactly one %s
        - domain: api2.anthropic.com
          scheme: bearer               # ... OR scheme sugar (mutually exclusive with format)
    oauth:
      tokenEndpoint: {host: platform.claude.com, path: /v1/oauth/token}  # both REQUIRED
      resourceHosts: [api.anthropic.com]
      sentinels: {accessToken: "...", refreshToken: "..."}  # REQUIRED unless passthrough
      credentialFile: {path: "~/.claude/.credentials.json", structure: {...}}  # structure preferred over deprecated template
      passthrough: false            # true = security downgrade, real token reaches container
```
A set `apiKey.name` must be a valid shell identifier; an empty name on a v2 kit
warns and sets no in-container variable (the proxy-side-only shape), and the
sentinel appears only with `proxyManaged: true`.
`scheme: bearer` -> `header: Authorization, format: "Bearer %s"` (no
`username`). `scheme: basic` -> username-driven Basic auth (`username`
REQUIRED, no `header` set automatically). An entry may declare both `apiKey`
and `oauth` on a sandbox kit. Do not infer universal credential precedence
from this schema: provisioning is service-specific (stored usable OpenAI
OAuth takes precedence over an API key). Public kits-v2 says the API key
takes precedence when both resolve; the service-specific exception and runtime
precedence belong to `docker-sandboxes-network-credentials`. v2 mixins cannot
declare OAuth (composition rejects it). A `required: true` credential with no
user binding: `sbx` warns and starts with it withheld (kits-v2 credentials
table).

A mixin redefining a base service with its own `apiKey.name` or
`proxyManaged` fails composition. Routing-only additions may merge: use
only `apiKey.inject`, no `name`/`proxyManaged`/`oauth`, and `required: false`.
Check the built-in base's source spec before authoring this extension;
`sbx kit inspect shell` is not a supported lookup. For a custom base, inspect
its directory/ZIP/OCI/git artifact reference instead.

## `environment`

```yaml
environment:
  variables:
    IS_SANDBOX: "1"     # keys must match ^[A-Za-z_][A-Za-z0-9_]*$
```
Reserved prefixes the runtime owns (kits SHOULD NOT set): `DASH_`, `SBX_`,
`DOCKER_`; runtime may also override `HOME`, `USER`, `SHELL`, `PATH`,
`LD_PRELOAD`, `LD_LIBRARY_PATH`.

## `setup`

```yaml
setup:
  install:                                    # string command, sh -c, runs once
    - command: "install -d -o agent -g agent /home/agent/.cfg"
      user: "0"                               # default "0" (root)
  startup:                                    # list<string> argv, runs every start
    - command: ["sh", "-c", "mkdir -p ~/.cfg"]
      user: "1000"                            # default "1000" (agent)
      background: false
  files:                                       # dynamic writes performed at startup via shell exec
    - path: /home/agent/.cfg/config.json       # REQUIRED, absolute
      content: '{"workdir": "${WORKDIR}"}'     # only ${WORKDIR} placeholder allowed
      mode: "0644"
      onlyIfMissing: true
```
`install` runs once per kit at creation, for every kit (built-in or not) —
guard with `command -v <bin>` for idempotency across recreate. `startup`
must be idempotent (fires on every container start). `files` (under
`setup:`) paths must be writable by uid 1000 — a root-owned target path
needs an `install` command instead. All three lists concatenate across
kits in `--kit` order. Creation order: network/env, `files/home/`, install,
`setup.files`, startup registered, `files/workspace/` (after the workspace,
and any `--clone`, is ready). `startup` is non-interactive (no TTY; cannot
prompt) and does not gate the agent entrypoint: the agent launches once startup
commands are dispatched, whatever `background` says, so prerequisites the agent
needs at launch belong in the image, `install`, or `setup.files`. Install
commands start in the image `WORKDIR`, not necessarily the workspace. The
shared skills store is read-only input: kit content is written first and the
store is linked only onto names still free (source ordering test, not runtime
proof).

**`setup.files` is a different mechanism from the static `files/` directory
tree (below).** `setup.files` entries are startup-time, `${WORKDIR}`-
substituted dynamic writes; the `files/` directory tree is packed
alongside `spec.yaml` and copied in at container-create time. It is
specifically `files/workspace/<path>` (not `setup.files`) that is written
after the workspace is populated (e.g. after an in-container `--clone` git
clone) — do not attribute that "after workspace population" timing to
`setup.files`.

## `volumes`

```yaml
volumes:
  - path: /workspace        # REQUIRED, absolute
    type: ""                 # "" (block, default) | tmpfs
    size: 10g                 # byte-size string
    mode: "0755"               # octal
```
Creation-time only (`sbx kit add` refuses a kit that declares volumes; existing
kit volumes and the workspace survive an add). Always set `size:`
on a block volume — an unsized one incurs ext4 inode-table zeroing at the
50 GiB default; 512 MiB is the practical floor.

## `files/` directory

`files/home/<path>` -> `/home/agent/<path>`; `files/workspace/<path>` ->
`<workspace>/<path>` (written after workspace population, e.g. after an
in-container `--clone` git clone). Relative paths only; `..` traversal and
symlinks escaping the artifact root are rejected.

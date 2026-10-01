# Command surface at sbx v0.46.0

Flag names come from the frozen v0.46.0 CLI reference YAMLs (`sbx <cmd> --help`
fields). Behavior rows marked "internal" come from the exact-ref source at
release tag commit 991967dc90ce0d9a440cd1df1bdf3e395c5a2693; the repository is
internal, so a public reader reproduces syntax with `sbx <cmd> --help`. Nothing
here was executed. Evidence IDs (Sxx) point to `references/sources.md`.

## `sbx policy` network commands

| Command | Flags (v0.46.0 export) | Notes | Evidence |
| --- | --- | --- | --- |
| `policy init <allow-all\|balanced\|deny-all>` | — | One-time global preset | S10 |
| `policy allow network RESOURCES` | `--protocol tcp\|udp` (repeat or comma-separate), `--sandbox` | Allow default: TCP | S11 |
| `policy deny network RESOURCES` | `--protocol tcp\|udp`, `--sandbox` | Deny default: TCP and UDP | S11 |
| `policy check network TARGET` | `--protocol`, `--sandbox`, `--json`, `--verbose` | `--verbose` shows exact request fields; host and port only, no method/path; bare hosts use port 443 | S12 |
| `policy log [SANDBOX]` | `--json`, `--limit`, `--quiet/-q`, `--type all\|network\|filesystem` | No `-v/--verbose` in export or source; filesystem logs are not supported at this target (help) | S13 |
| `policy ls [SANDBOX]` | `--wide`, `--json`, `--source local\|org\|kit`, `--decision allow\|deny`, `--type all\|network\|filesystem`, `--protocol tcp\|udp`, `--created-via default\|added\|provisioned\|approval`, `--include-inactive` | `--wide` adds POLICY/POLICY_ID/RULE/RULE_ID columns plus resources, status and rule metadata; rule IDs appear only there | S14 |
| `policy inspect <policy-or-rule>` | `--json` | Shows editability, exact removal command or read-only reason | S14 |
| `policy rm network` | `--id`, `--resource`, `--sandbox`, `--force/-f` | Only kind under `policy rm`; one selector required | S15 |
| `policy reset` | `--force/-f` | Destructive; see below | S16 |

Gated HTTP qualifiers (`--method`, `--path`) exist on `allow/deny/rm network`
in public docs and source but are absent from the frozen export (source gates
them behind an L7 HTTP policy feature). `--method` on `rm` requires
`--resource`; an ID-only removal (no `--resource`) rejects `--method/--path`.
Filter value `http`
for `ls --type` appears in public docs, not in the export: verify locally
(S17).

### Resource patterns (allow/deny/rm `--resource`)

Quote every argument below in the shell.

| Form | Example | Notes |
| --- | --- | --- |
| Exact host | `example.com` | Not subdomains |
| Single-label wildcard | `"*.example.com"` | `example.com` and `*.example.com` do not cover each other |
| Multi-label wildcard | `"**.example.com"` | Any depth |
| Single-character glob | `"api?.example.com"` | |
| Character class | `"api[12].example.com"`, `"api[!1].example.com"` | |
| Port suffix | `example.com:443` | |
| IPv6 | `[2001:db8::1]:443`, `2001:db8::1/128` | Bare IPv6 refused |
| CIDR | `10.0.0.0/8` | |
| All hosts | `"**"` | Bare `"*"` refused |
| Rejected | `\*`, other forms | Refused rather than stored as a never-matching rule |

Evidence: S11, S18.

### Policy confirmation and failure behavior

| Situation | Behavior | Evidence |
| --- | --- | --- |
| `rm network` with neither `--id` nor `--resource` | Error: `at least one selector is required: use --id or --resource` | S15 |
| `rm network --id <rule name>` | Fails; message names the real rule ID and, for removable rules, the corrected command | S15 |
| `rm network` prompt | `Remove network rules from <scope> (<selectors>)? (y/N)`; `--force` skips | S15 |
| Daemon returns a rule error | `remove network rule: <error>` | S15 |
| `reset`, running sandboxes detected, no `--force` | Lists them, says the daemon stops and sandboxes are terminated, asks `(y/N)` | S16 |
| `reset`, running-sandbox check fails | Warns `could not check for running sandboxes` and continues without that prompt | S16 |
| `reset`, prompt declined | Source prints `Cancelled` and returns success; public release notes (0.45.0) say declining a destructive prompt returns non-zero. Do not rely on exit status; verify locally | S16, S28 |
| `reset`, success | Stops daemon, deletes the policy cache directory, restarts the daemon inside the command, then prompts to initialize the preset | S16 |
| `reset`, restart fails | Warning plus hint `sbx policy init ...`; command still returns success | S16 |

Reset help (export) says "The daemon restarts automatically on the next
command"; the implementation restarts it within the command. Report both; do not
promise either timing.

## `sbx secret` commands

| Command | Flags (v0.46.0 export) | Evidence |
| --- | --- | --- |
| `secret set [SERVICE]` | `--sandbox`, `--ref`, `--command`, `--refresh` (default 55m), `--no-verify`, `--show-error`, `--token/-t`, `--force/-f`, `--oauth`, `--registry`, `--username`, `--password-stdin`, `--all-sandboxes`, `--registry-auth-endpoint` | S20 |
| `secret set-custom` (experimental) | `--host` (repeatable), `--env`, `--placeholder` (`{rand}`), `--sandbox`, `--value`, `--token/-t`, `--ref`, `--command`, `--refresh` (default on-demand), `--no-verify`, `--show-error`; `--name/--header/--format` apply with `--cloud` | S21 |
| `secret ls` | `--global/-g`, `--sandbox`, `--service`, `--json`, `--quiet/-q` | S22 |
| `secret rm [SERVICE]` | `--sandbox`, `--all`, `--registry`, `--all-sandboxes`, `--force/-f` | S23 |
| `secret import [SERVICE]` | `--all`, `--dry-run`, `--force/-f` | S24 |

`secret set` has no `--type` or `--binding` flag. `--ref`/`--command` are
mutually exclusive with each other and with `--token`, `--oauth` and
`--registry`; `--show-error` cannot be combined with `--no-verify` (S25).

`--sandbox`, `--all-sandboxes` and `--global` (deprecated) are mutually
exclusive on `set` and `rm`; `--all-sandboxes` requires `--registry`; `rm --all`
excludes `SERVICE`, `--sandbox`, `--all-sandboxes`, `--registry` (S23, internal).

### Hidden custom-mode flags (internal, not a stable recipe)

At v0.46.0 `secret rm` defines `--host`, `--env` and `--placeholder` and marks
all three hidden; they route to a custom-mode removal path. `secret ls` defines
the same three as hidden filters. They do not appear in exported help, except
that the `rm` help example shows `--placeholder`. Teaching boundary: describe as
internal and version-pinned, never as the default recipe; identify the record
with `secret ls --json` (`scope`, `targets`, `env`, `placeholder`), prefer the
interactive picker, and confirm afterwards that only the intended record is
gone. Whether the picker lists custom records is not established: verify
locally (S26).

### Masking and listing output

Listing mode decides what is shown (S27):

| Mode | Service secrets | Registry | Custom | OAuth |
| --- | --- | --- | --- | --- |
| Default `secret ls` (no `--service`) | `(stored)` label; values are not decrypted | masked preview | literal: masked preview; dynamic: `kind`, `source`, `refresh` in JSON | label |
| `secret ls --service NAME` | masked preview of a literal value (JSON rows: `scope`, `type`, `name`, `secret` only) | not listed | not listed | label |

Literal values that are previewed are rendered by `maskCredential`:

| Literal length | Rendered | Example |
| --- | --- | --- |
| ≤ 6 | all `*` | |
| 7–19 | first 6 visible, rest `*` | `throwaway-token` (15) → `throwa*********` |
| ≥ 20 | first 6 and last 4 visible, middle `*`; output capped at 25 characters with `...` | `throwaway-test-value` (20) → `throwa**********alue` |

Registry passwords: fewer than 12 characters render as `*` (at most 8); 12 or
more use the table above. OAuth records show a label such as
`(oauth configured)` or `(token handled by proxy)`. Interactive `secret import`
shows a last-4 preview of the detected value, and a divergent-value skip prints
the last 4 characters of the stored and environment values (S27).

`secret ls --json` default document (S27):

| Field | Content |
| --- | --- |
| `secrets[]` | `scope` (`global`, sandbox name; registry: `host-only`, `global`, sandbox name), `type` (`service`/`registry`), `name`, `secret` (`(stored)`/OAuth label for service rows, masked preview for registry rows), `username` (registry) |
| `custom_secrets[]` | `scope`, `targets`, `env`, `placeholder`, `secret` (masked), `kind`, `source`, `refresh` |
| `shadowed_services` | API-key entries hidden because an OAuth token takes precedence |
| `env_only_count` | Host env secrets with no stored entry (never used at runtime) |

`--service` output carries `scope`, `type`, `name` and masked `secret` only; the
source is deliberately omitted because it "can hold a token when one is passed
in the command's arguments". `source` of a dynamic **custom** record is shown in
`custom_secrets[]` and can contain whatever was typed in `--command`; the text
table for custom records was not captured: verify locally. The JSON shape of
`policy ls/check/log --json` was not captured: verify locally.

### Confirmation and failure behavior

| Situation | Behavior | Evidence |
| --- | --- | --- |
| `rm` prompt | `Delete selected secret? (y/N)`; declined exits non-zero (`ErrOperationCancelled`) | S28 |
| `rm` with no service | Opens a picker of existing local secrets (scope, type, name) | S28 |
| `rm` without a terminal, no `--force` | Error `stdin is not a terminal; use --force to skip confirmation` | S28 |
| `rm SERVICE`, nothing stored | Error `no secret found for service "X" in scope "Y"` | S28 |
| Same with `--force` | Re-runs revocation reconciliation; success does not prove a secret existed | S28 |
| Live revocation fails | `failed to revoke global secret from sandboxes` / `failed to revoke secret from sandbox "<name>"` with retry hints `sbx secret rm --force -- SERVICE` (global) or `sbx secret rm --sandbox NAME --force -- SERVICE` (scoped); options go before `--` | S29 |
| Daemon absent vs HTTP error/timeout | Absent daemon is tolerated; HTTP failure or timeout can leave cached credentials usable | S29 |
| `import` same value stored | Skipped | S30 |
| `import --all`, differing stored value | Skipped; `--force` overwrites | S30 |
| `import`, OAuth token configured | Skipped; `--force` does not bypass | S30 |

`import` always targets the global scope (S30). MCP header and OAuth-client
secrets (names starting `mcp:`) appear in `secret ls`, are global-only, stay on
the host, and need a gateway or sandbox restart to apply (S31).

## Dynamic secret host-execution checklist

Applies to `secret set --command/--ref` and `set-custom --command/--ref`. None of
this was executed; no helper was run (S25).

1. The source runs on the host with the user's privileges at registration-time
   verification and at every refresh; treat it as trusted execution.
2. Runs from a fresh temporary directory: a project-relative `./helper` or a
   bare script name is not found there. Use an absolute helper path, a helper
   found by name on an absolute `PATH` directory, or an explicit `cd` to its
   private directory inside the command.
3. The helper, every script, configuration file and dependency it loads, the
   absolute host temporary directory and any `PATH` entries must be outside
   writable sandbox mounts. Mounts added later with `sbx mount` count.
4. sbx does not copy helpers, inspect their dependencies or confine their
   execution. A fresh working directory is not confinement.
5. Reject paths that a sandbox, an untrusted file or an agent's output can
   influence, and explicit paths into shared workspaces or broad host mounts.
6. `--no-verify` skips the initial check only. `--show-error` prints resolver
   stderr (may contain secrets) and cannot be combined with `--no-verify`.
7. Command text is stored, replayed by the daemon, visible in shell history and
   process listings, and can be shown by `secret ls`: never embed a credential.
8. `--refresh` is cache policy (service 55m, custom on-demand, `on-demand`
   resolves each use); it is not revocation of the upstream credential.

## Registry credential details

| Topic | Behavior | Evidence |
| --- | --- | --- |
| Default scope | host-only: template/kit pulls on the host, never injected | S20, S32 |
| `--all-sandboxes` | host pulls plus proxy injection into every new sandbox's registry login; existing sandboxes do not pick it up | S32 |
| `--sandbox NAME` | injection into that sandbox only; can coexist with host-only or all-sandboxes | S32 |
| Host-only vs all-sandboxes | Competing global scopes: a successful save deletes the other; an unexpected cleanup error only warns | S32 |
| Docker Hub | Uses the `sbx login` session, no registry secret | S32 |
| Auth endpoint | Accepted on the registry's own host and built-in relationships (for example Docker Hub's auth host); other realms need `--registry-auth-endpoint` with the exact HTTPS URL, no credentials, query or fragment; `/jwt/auth/` does not match `/jwt/auth` | S32 |
| Removal | `rm --registry HOST` removes host-only and global; `--all-sandboxes` only global; `--sandbox NAME` only that sandbox; none revokes the upstream token | S23, S32 |

## Scope matrix

| Stored item | Default scope | Scoped form | Inverse |
| --- | --- | --- | --- |
| Service secret | global | `--sandbox NAME` (wins over global) | `rm SERVICE [--sandbox NAME]` |
| Custom secret | global | `--sandbox NAME` | interactive `rm`, hidden flags (internal), `rm --all` |
| OAuth token | global only (`openai`) | none | `rm SERVICE` (prompts) |
| Registry credential | host-only | `--all-sandboxes` (new sandboxes), `--sandbox NAME` | `rm --registry HOST [--all-sandboxes\|--sandbox NAME]` |
| Network rule | global | `--sandbox NAME` | `policy rm network [--sandbox NAME] --id\|--resource` |

Evidence: S20, S21, S23, S15, S32.

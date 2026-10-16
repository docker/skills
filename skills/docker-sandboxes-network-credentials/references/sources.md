# Sources

## Release record (v0.46.0)

- Target: sbx v0.46.0, GitHub release `v0.46.0`, published 2026-09-28T15:43:20Z,
  not a prerelease or draft (`evidence/MANIFEST.md`, `evidence/release-notes/v0.46.0.json`).
- Syntax and implementation source: repository `docker/sandboxes` at release tag
  commit `991967dc90ce0d9a440cd1df1bdf3e395c5a2693`
  (`evidence/provenance/tag-commit.json`). The repository is **internal**; paths
  below cite it as `internal:<path>:<symbol>` and are not public citations.
- CLI syntax: 118 frozen reference YAMLs at that commit (`docs/yml/sbx*.yaml`);
  cited as `sbx <cmd> --help` fields. The earlier plan's count of 122 is stale.
  Shipped-binary `--help` parity is assumed, not tested; no `sbx` command was
  executed and no installed build was used as an oracle.
- Public docs: Docker Docs snapshots (frozen Markdown of the pages named below).
  Public release notes end at 0.45.1 (2026-09-22), so v0.46.0 behavior is
  cited from the release payload and internal source, not a public notes page.
- Skill baseline: docker/skills commit `3e1cbd179989c2c193f3e4e6553a655907c2003b`.
- The previous provenance (an older source commit and an installed prerelease
  build) is replaced by this record; see the removed-claims log for this update.

Public pages used: Manage credentials
(https://docs.docker.com/ai/sandboxes/configuration/credentials/), Local policy
(https://docs.docker.com/ai/sandboxes/governance/access-controls/local/), Policy
concepts (https://docs.docker.com/ai/sandboxes/governance/concepts/), Network
access policies
(https://docs.docker.com/ai/sandboxes/governance/access-controls/network/),
Architecture (https://docs.docker.com/ai/sandboxes/architecture/), Security
(https://docs.docker.com/ai/sandboxes/security/), Release notes
(https://docs.docker.com/ai/sandboxes/release-notes/).

## Claim evidence

Every line: claim — version — location — supporting excerpt. "internal" paths
are in `docker/sandboxes@991967dc`; help fields are v0.46.0 export YAML.

### Routing, provenance and model

- S01 — Proxy injects stored credentials; sandbox sees a sentinel; real value
  stays on the host while proxy management is active. v0.46.0. Public docs,
  Manage credentials › intro. "the sandbox sees only a sentinel value".
- S02 — OAuth passthrough gives no token-less guarantee. v0.46.0. Docs, Manage
  credentials › How credential injection works: "A kit can set OAuth
  `passthrough: true` to opt out of sentinel masking. This sends the real token
  response into the sandbox". internal:`sandboxd/pkg/proxy/oauth_handler.go`:
  `rewriteTokenResponse` forwards the original response when passthrough has no
  refresh sentinel; `oauth_handler_test.go` covers real-refresh-token forwarding
  and masking with a sentinel; built-in Devin kit:
  internal:`sandboxlib/agentkits/agents/devin/spec.yaml`.
- S03 — Stored-only runtime: host environment variables never auto-inject.
  v0.46.0. internal:`cli-plugin/commands/registry_secret.go` (comment on
  `envDetectedSecret`, lines 262–282): "the keychain is the only runtime
  source"; `credential_store_json.go`:`secretsLsJSON.EnvOnlyCount`: host
  environment variables holding a secret for a service with no stored entry
  "are never used at runtime". The earlier seed also cited internal:`AGENTS.md`
  at an older commit; that file was not re-captured at v0.46.0 and is not
  relied on.
- S04 — Sandbox-scoped secrets take precedence over global; stored secret wins
  when several sources exist. v0.46.0. Docs, Manage credentials › Store a
  secret: "Sandbox-scoped secrets take precedence over global secrets."
- S05 — `--oauth` is openai/global only and excludes `--sandbox`/`--token`.
  v0.46.0. `sbx secret set --help`: "Start OAuth flow and store OAuth tokens
  (openai/global only)"; internal:`cli-plugin/commands/credential_store.go`:
  `validateOAuthMutation`: "oauth secrets are global-only", "cannot use --oauth
  with --token". No `--type`/`--binding` flag exists in the `set` option list.
- S06 — Third-party kits need an approved binding; built-ins exempt; unattended
  starts withhold the credential and warn. v0.46.0. Docs, Manage credentials ›
  Credential bindings › First-run approval: "the sandbox starts with the
  credential withheld when no binding exists"; internal:
  `cli-plugin/commands/agent_credentials_preflight.go`.

### Network policy

- S10 — One-time `policy init`, presets `allow-all|balanced|deny-all`. v0.46.0.
  `sbx policy init --help`; docs Local policy › Default preset.
- S11 — `--protocol tcp|udp`; allow defaults TCP, deny defaults TCP+UDP;
  pattern forms; bare `*`, bare IPv6 and `\*` refused. v0.46.0.
  `sbx policy allow network --help`: "Rules apply to TCP by default; use
  --protocol to select UDP or both transports"; "A bare \"*\", an escaped glob
  character such as \"\\*\", and any other pattern outside these forms are
  rejected rather than stored". `sbx policy deny network --help`: "Rules apply
  to TCP and UDP by default". The spelling `--proto` is not in the option list.
- S12 — `check network`: host/port only, `--protocol`, `--verbose`. v0.46.0.
  `sbx policy check network --help`: "this command evaluates network
  authorization, not HTTP method or path".
- S13 — `policy log` options `--json --limit --quiet --type`; no verbose.
  v0.46.0. `sbx policy log --help`; internal:`cli-plugin/commands/policy.go`:
  `policyLogCmd` flags.
- S14 — `ls` filters incl. `--created-via default|added|provisioned|approval`,
  `--include-inactive`; `inspect` shows removal command or read-only reason.
  v0.46.0. `sbx policy ls --help` (`created-via`, `decision`,
  `include-inactive`, `protocol`, `source`, `type`, `wide`);
  `sbx policy inspect --help`: "either the exact removal command or the reason
  it is read-only"; public notes 0.45.0: "`sbx policy ls` ... supports filtering
  with `--created-via`".
- S15 — `rm network`: one kind, selector required, `--id` is a rule ID not a
  name, confirmation prompt, daemon errors. v0.46.0. `sbx policy rm --help`
  lists only `sbx policy rm network`; `sbx policy rm network --help`:
  "Passing a rule name fails with an error that names the actual rule ID";
  "--id ... (local rules only)" in `sbx policy ls/inspect --help`;
  internal:`policy.go`:`policyRmNetworkCmd` RunE: "at least one selector is
  required: use --id or --resource", `runLocalPolicyRm` (`policyRemovalPrompt`:
  "Remove network rules from %s (%s)? (y/N): ", error `remove network rule: %s`).
  `--resource` multi-match: `Remove by resource value(s), comma-separated` and
  the audit's runbook finding that one resource can carry an allow and a deny.
- S16 — Reset semantics. v0.46.0. `sbx policy reset --help`: "This deletes the
  local policy store and stops the daemon. The daemon restarts automatically on
  the next command"; "If sandboxes are currently running, they will be stopped".
  internal:`policy.go`:`policyResetCmd` RunE calls `runPolicyReset`, then
  `startDaemon(...)` and `ensurePolicyDefaults(cmd)`; restart failure:
  "failed to restart daemon" as `ui.Warn` and `return nil`. `runPolicyReset`:
  on `ListRuntimes` error prints "warning: could not check for running
  sandboxes" and sets `rts = nil`; prompts only `if len(running) > 0 && !force`;
  "Running sandboxes will be terminated."; declined: prints "Cancelled",
  `return nil`. Docs Local policy › Resetting: "Running sandboxes stop when the
  daemon shuts down."
- S17 — HTTP qualifiers are flags on network commands, gated, absent from the
  export. v0.46.0. Docs Local policy › HTTP method and path rules
  ("`sbx policy check network` and `sbx policy log` don't evaluate or display
  HTTP methods and paths"); internal:`policy.go`:`policyRmNetworkCmd`
  (`--method requires --resource`, `--id already identifies a single rule`),
  `requireL7HTTPPolicyForChangedFlags`. Docs Policy concepts: "A connection it
  can't inspect ... is blocked rather than evaluated. Traffic that isn't HTTP,
  such as SSH, carries no method or path". Docs Architecture › Networking:
  "The forward proxy also handles credential injection".
- S18 — Pattern forms and deny precedence. v0.46.0. Docs Policy concepts ›
  Network rules ("`example.com` and `*.example.com` don't cover each other");
  deny help: "An allowed hostname isn't checked against CIDR rules for its
  resolved IP address"; internal:`vendor/github.com/docker/governor-lib/
  internal/authorization/definitions/allowlist/v0/matching.go`.
- S19 — Governed-local boundary. v0.46.0. Docs Local policy: "Org governance
  active: only organization allow rules grant access, so local allow rules are
  inactive ... Local deny rules are still evaluated"; Troubleshooting: "Local
  allow rules have no effect". `--deny-network`: `sbx create --help` /
  `sbx run --help`: "a local deny can only narrow, never widen, egress".
- S19b — UDP is experimental, opt-in, and refused with proxied destinations.
  v0.46.0. Docs Local policy › Allow outbound UDP: "Outbound UDP is
  experimental and disabled by default"; `sbx settings set
  platform.allowExperimentalFeatures true` and `feature.udp-egress true`;
  "It is refused when the destination requires an HTTP, SOCKS5, system, or
  PAC-selected proxy"; "ICMP remains blocked". Public notes 0.45.0:
  "Experimental outbound UDP now follows sandbox network policy."

### Secrets

- S20 — `secret set` flags, defaults, dynamic sources, registry scopes.
  v0.46.0. `sbx secret set --help` (all option names in
  `references/command-surface.md`); `--refresh`: "default: 55m"; `--token`:
  "Secret value (less secure: visible in shell history)".
- S21 — `set-custom`: experimental, `--value`/`--token` history hazard,
  on-demand default. v0.46.0. `sbx secret set-custom --help`: experimental
  true; `--refresh`: "on-demand (default) or after a duration"; `--value`:
  "less secure: visible in shell history". Docs Manage credentials › Custom
  secrets: "Custom secrets are experimental"; "Passing the secret as `--value
  <secret>` records it in your shell history".
- S22 — `secret ls` flags. v0.46.0. `sbx secret ls --help`. No `--verbose`/`-v`
  option in the export or in internal:`credential_store.go`:`credentialsListCmd`
  (only `policy check network` defines `verbose`).
- S23 — `secret rm` flags, blast radius, mutual exclusions. v0.46.0.
  `sbx secret rm --help`: "--all: Remove every stored secret across all
  scopes"; "--force: Delete without confirmation prompt"; internal:
  `credential_store.go`:`credentialsUnsetCmd` (`MarkFlagsMutuallyExclusive`
  for `all` with `global/sandbox/all-sandboxes/registry`; "--all-sandboxes
  requires --registry"; "cannot specify a SERVICE argument when using --all").
- S24 — `secret import` flags. v0.46.0. `sbx secret import --help`.
- S25 — Dynamic source rules: fresh temporary cwd, absolute helper paths,
  helpers outside writable mounts, no confinement, `--no-verify`/`--show-error`.
  v0.46.0 (release breaking change). `sbx secret set --help` and
  `sbx secret set-custom --help`: "Command secrets run from a fresh temporary
  directory on the host during verification and refresh. The host temporary
  directory must be absolute and must remain outside writable sandbox mounts.
  Relative references such as ./helper or cat token no longer resolve against
  the project or daemon working directory. ... sbx does not copy helpers,
  inspect their dependencies, or confine their execution. ... including mounts
  added later with sbx mount." `--show-error`: "(may contain secrets)".
  Release payload v0.46.0 › Breaking changes: "execute from a fresh temporary
  directory on the host. Relative paths such as `./credential-helper` no longer
  resolve from the project directory". Docs Manage credentials › Use a dynamic
  secret source: "`sbx` runs the command through the host shell and trims its
  output. The command text is stored and replayed by the daemon. Don't embed a
  secret directly in the command"; "You can't combine `--show-error` with
  `--no-verify`"; "`--ref` and `--command` are mutually exclusive." Docs state
  relative paths resolve from the temporary directory; help states they do not
  resolve against the project directory: both mean a project-relative helper
  is not found, so use an absolute path. The literal shell wrapper (`sh -c`) for
  secret commands is not stated in the frozen evidence; the skill says
  "host shell" only.
- S26 — Hidden custom-mode removal flags. v0.46.0. internal:
  `cli-plugin/commands/credential_store.go`:`credentialsUnsetCmd` lines
  1040–1046 (`--host` "Custom mode: host or IP address", `--env`,
  `--placeholder` "Custom mode: placeholder value"; `MarkHidden("host")`,
  `MarkHidden("env")`, `MarkHidden("placeholder")`), 1071–1072
  (`runCredentialsUnsetCustomMode`); `credentialsListCmd` 1349–1352 hides the
  same filters. `sbx secret rm --help` example: "Remove custom secret by
  specifying the placeholder value" while the option list omits it. Not a
  public stable interface; verify locally.
- S27 — Listing modes, masked previews and JSON fields. v0.46.0. Default
  mode (no `--service`): internal:`credential_store.go`:
  `runCredentialsListDefaultMode` ("enumerates service credentials from
  metadata only — it never decrypts a value ... The masked preview stays
  available via the scoped `sbx secret ls <service>` path"),
  `serviceCredentialsFromMetadata` ("No secret value is read: the SECRET column
  shows storedSecretDisplay", `storedSecretDisplay = "(stored)"`); registry and
  custom rows are still listed with previews/source. Service mode:
  `runCredentialsListServiceMode` uses `credStore.List` and
  `serviceModeSecretsJSON`. Preview and JSON details: internal:
  `credential_store.go`:`maskCredential` ("Short secrets (≤6 chars) are fully
  masked. Medium secrets (7..19 chars) reveal only the first 6 chars ...
  Long secrets (≥20 chars) reveal the first 6 and last 4 chars");
  `credential_store_json.go`:`secretsLsJSON`, `secretJSON`,
  `customSecretJSON`, `serviceSecretJSON`, `registrySecretJSON`,
  `customSecretRowJSON`, `serviceModeSecretJSON` (comment: the source "can
  hold a token when one is passed in the command's arguments");
  `registry_secret.go`:`maskRegistrySecret` (`len(secret) < 12` →
  `strings.Repeat("*", min(len(secret), 8))`); `credential_import.go` header:
  "a last-4-char preview of the value". Fixture arithmetic: `throwaway-test-value`
  is 20 characters, so `throwa` + 10 `*` + `alue`.
- S28 — Removal confirmation and missing-target errors. v0.46.0. internal:
  `credential_store.go`:`renderDeleteSecretPrompt` ("stdin is not a terminal;
  use --force to skip confirmation"; "Delete selected secret? (y/N): ";
  `ErrOperationCancelled`), `handleMissingServiceSecret` ("no secret found for
  service %q in scope %q" returned unless `force`; with `force`, reconcile).
  Public notes 0.45.0 › CLI and output: "Commands that remove resources now
  ask for confirmation. Use `--force` ... in non-interactive workflows.
  Declining a destructive-action or required-restart prompt now returns a
  non-zero exit code." and "Running `sbx secret rm` without a service opens a
  picker showing existing local secrets and their scope, type, and name."
  These notes conflict with `runPolicyReset` (S16), which returns nil on a
  declined prompt; the source at 991967dc describes v0.46.0, the notes
  describe 0.45.0 — record both, rely on neither.
- S29 — Revocation is reconciliation with retry. v0.46.0. Release payload:
  "Removing secrets in bulk revokes credentials from running sandboxes. Failed
  revocations can be retried even after the stored secrets have been deleted."
  Public notes 0.45.0: "Registry and service-secret revocation failures are now
  reported and can be retried". Docs Store a secret: "Adding, updating, or
  removing a service secret takes effect in existing local sandboxes without a
  restart". internal:`credential_store.go`:`reconcileDeletedServiceSecret`
  (errors `failed to revoke global secret from sandboxes`; retry hints
  `secret rm --force -- SERVICE` for global and `secret rm --sandbox NAME --force
  -- SERVICE` for scoped), `credential_revocation.go`:`isSecretDaemonAbsent`
  ("An HTTP failure or timeout can leave cached credentials usable."),
  `serviceRevocationUpdate`; tests `credential_revocation_test.go`.
- S30 — Import routing and skip rules. v0.46.0. `sbx secret import --help`
  ("--all imports new entries without prompting but SKIPS overwrites";
  "Services that already have an OAuth token configured ... are skipped");
  internal:`credential_import.go`:`decideImport` ("OAuth-shadow always wins";
  `force=true` bypasses only the same-value short-circuit and the divergent
  skip), header comment "Imports always land in the global scope".
- S31 — `mcp:` secrets. v0.46.0. Docs Manage credentials › MCP secrets: "These
  records have names starting with `mcp:` and appear in `sbx secret ls`. They
  stay on the host and aren't injected into sandboxes."; internal:
  `credential_store.go`:`printMCPHeaderSecretRebuildHint`, `validateMCPHeaderSecretMutation`
  ("MCP header secrets are global-only").
- S32 — Registry scopes, competing global entries, auth endpoint. v0.46.0.
  `sbx secret set --help` (registry credentials host-only by default;
  `--all-sandboxes`, `--sandbox`); `sbx secret rm --help` ("removes host-only
  and global entries" vs "--all-sandboxes ... only the global"); docs Manage
  credentials › Registry credentials ("Existing sandboxes don't pick up
  all-sandboxes registry credentials added later"; "the proxy accepts
  authentication endpoints on the registry's own host and built-in registry
  relationships, such as Docker Hub's authentication host"; "match the
  configured host and path exactly. Other paths on that host, including
  `/jwt/auth/`, aren't covered"); internal:
  `cli-plugin/commands/registry_secret.go`:`removeCompetingRegistryScope`
  (deletes the other global scope after a successful save; warns on unexpected
  errors), `runRegistryCredentialDelete` (removes exactly the requested scope).

### Test isolation control

- S33 — `--app-name` isolation for the unexecuted runbook. v0.46.0. Hidden,
  development/testing flag, not in the exported help:
  internal:`cli-plugin/commands/root.go` (`rootFlags`, lines 1596–1601): "Hidden
  flag for development/debugging - overrides the storagekit application name, so
  all state, cache, and config paths (including the socket) are fully isolated";
  `MarkHidden("app-name")`. internal:`sandboxlib/storagepaths/storagekit.go`
  (lines 14–66): `MaxAppNameSuffixLen = 20`; `SetAppName` rejects an empty
  suffix, one over 20 characters, or any character outside letters, digits,
  hyphen and underscore, and sets the name to `sandboxes-<suffix>`. It isolates
  daemon/state paths, not Docker login or runtime outcomes. Captured under
  `out/sbx-refresh/forge/`; the exact-ref source directory does not contain it.

### Out of scope or unverified

- `--cloud` variants dispatch to the Docker Cloud Sandboxes API (`--cloud`
  inherited option text); cloud semantics are not covered here.
- Not executed: every command, every runbook step, registry pulls, header
  substitution, shell startup sentinel value, OAuth flows, hidden-flag
  removal behavior, and `policy ... --json` shapes.
- Whether the interactive `secret rm` picker lists custom secrets is not
  established by the frozen evidence.
- No public release-notes page exists for v0.46.0 in the snapshots; the
  release payload is the source for the v0.46.0 breaking change.

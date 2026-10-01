# Sources

## Target, evidence classes, and what was run

- Target: stable `sbx` **v0.46.0**, repository docker/sandboxes commit
  `991967dc90ce0d9a440cd1df1bdf3e395c5a2693`. The CLI help was captured as a
  frozen export of 118 command YAML files (`sbx env` and its five
  subcommands, `sbx settings get|set|unset`, `sbx secret set`, `sbx mcp add`,
  `sbx exec`). `docker_help` does not cover standalone `sbx`.
- Public release notes (`ai/sandboxes/release-notes.md`) stop at 0.45.1. The
  v0.46.0 release body was captured separately from the GitHub release.
  Treat 0.46.0 public prose as lagging the code.
- Evidence classes used below:
  - **help**: frozen `sbx ... --help` YAML for v0.46.0.
  - **docs**: captured public pages `ai/sandboxes/configuration/environment-files.md`
    (https://docs.docker.com/ai/sandboxes/configuration/environment-files/)
    and `configuration/settings.md`.
  - **source**: exact-tag source files in docker/sandboxes at the commit above
    (paths relative to the repository root; `cli-plugin/commands/…`,
    `sandboxlib/…`). When source and prose disagree the source decides and
    the disagreement is recorded.
  - **unexecuted**: any behavior no one ran. **No claim in this skill is
    runtime-verified.** Every behavior row is help, docs or source read only,
    and `checks/verification.md` is an unexecuted manual runbook.
- Older evidence (source `df5c96ba60484fa2c375469dbac912c205da6c37`, installed
  `v0.42.0-503-g951b7f6d7`, and an earlier statement that no dedicated public
  page had been fetched) is historical. It is superseded by the target above
  and proves nothing about v0.46.0.
- Hidden `--app-name` (registered hidden in `cli-plugin/commands/root.go`;
  suffix limited to 20 characters of letters, digits, `-`, `_` by
  `MaxAppNameSuffixLen` in `sandboxlib/storagepaths/storagekit.go`) isolates
  local storage only. It is implementation-only, not a public CLI guarantee,
  and shares the cloud login. The runbook uses it as a convention, not as a
  promise.

## Claim-to-evidence map

Excerpts are verbatim, shortened with an ellipsis.

### File format, merge, args

- Only `sbxenv.yaml` is read from a directory: help (`env create`): "A
  directory resolves to the sbxenv.yaml in it and to no other name".
- Required keys apply to the merged document: `sandboxlib/sbxenv/types.go`
  `Config.Validate` ("schemaVersion is required", "agent is required") runs on
  the merged config after `LoadMergedWithOptions`; `loader.go`
  `decodeDocument` decodes each layer non-strictly ("the merge and the
  required-field validation both behave as if the keys were simply absent").
- Merge rules: `loader.go` `mergeMap`: "nested mappings merge recursively,
  sequences from both sides concatenate (base entries first), and any other
  value ... is overridden by src". Help: "an entry declared in both appears
  twice".
- Same-source kit coalescing: `loader.go` `coalesceKits`: "folds entries naming
  the same source into the first one, merging their arguments key by key so the
  last file to set a value wins".
- Explicit-path anchoring only: `loader.go` `isRelativeKitPath` (`./`, `../`,
  `.`, `..`, suffix `.zip`; not `~`, absolute, or `://`); `types.go`
  `KitEntry.Source`: "a bare `kits/tool` included: that is as much a registry
  reference as a directory, so a directory beside the file does not get to
  claim it". Help says the bare form "resolves from the current directory";
  docs say bare references "remain registry references". The two differ in
  wording; both agree it is not anchored to the declaring file, so the skill
  says it is left as written and resolved downstream.
- Args: `sbxenv/args.go` (`ParseArg`, `ParseArgsFile`, `MergeArgs`, sentinels
  `ErrArgUnresolved`, `ErrArgInvalid`, `ErrArgUndeclared`, `ErrArgUnused`,
  `ErrArgMalformed`); `loader.go` doc comment: "none of them reach the args:
  block"; docs: "Later files take precedence over earlier files, and
  `--env-arg` flags take precedence over every argument file" and
  "`enum` and `pattern` can't be used together". `ErrArgUnused` is "a supplied
  argument the environment does not declare".
- Unknown keys: release body v0.46.0: "`sbx env` reports unrecognized
  environment-file keys with the file, line, and column where they were
  declared, including when multiple files are merged."
- Workspace: `types.go` `WorkspaceSpec` ("Path must be a Git repository (not a
  worktree) when set"; "Clone is scoped here ... never to
  AdditionalWorkspaces"); `validateWorkspaces` ("workspace.clone requires a
  'workspace:' path to clone from"); docs: "Additional workspaces are mounted
  directly even when the primary workspace uses clone mode."

### Approval and host code

- Repeated approval: `env_plan_gate.go` `gatePlan`: "A plan that runs commands
  on this machine is answered for every time it runs them ... one approved run
  is not consent to every later one." `asksAgainForHostCode` reads
  `envRememberHostCommandsFn`.
- Credential commands count: `env_plan_render.go` `hostCode` returns true for
  `KindLifecycle` and for secret/registry rows whose field label is `command`
  or ends in `.command`. Docs: "Plans containing lifecycle commands or
  credential `command` sources require approval for every invocation by
  default".
- `-y` records nothing: `env_plan_gate.go` constant comment: "It covers one
  invocation and records nothing: consent is only ever remembered for an answer
  typed at a terminal, so an unattended run cannot quiet the next interactive
  one." Docs: "`--auto-approve` approves the plan for that invocation without
  recording consent for later invocations."
- No terminal: `errPlanUnapproved`, `errPlanHostCodeUnanswered` ("approve this
  invocation by running it in a terminal or with --auto-approve (-y)");
  `approveDestroy`: "stdin is not a terminal; use --force to skip
  confirmation".
- `--skip-host-commands` is lifecycle only: `env_plan.go` `buildPlan` appends
  `ec.lifecycleResources(...)` only under `if !opts.skipHostCommands`;
  `secretResources`, `registryResources`, `bindingResources`, `mcpResources`
  are appended unconditionally; `env.go` `provisionSecrets` has no skip check.
  Help: "Skip the host lifecycle commands the environment declares".
- Setting: `sandboxlib/platform/settings.go` `EnvRememberHostCommandsSettingKey
  = "env.rememberHostCommands"`, default `false`, "Deliberately has NO EnvVar
  override"; docs (settings): "The first approval is still required."
  `sbx settings get` ("Print the evaluated value of a setting", `--json`
  shows source) and `sbx settings unset` ("Remove the user override for a
  setting") are in frozen help. No alias for the key was found in the frozen
  settings source.
- Upgrade approval: release body v0.46.0: "the next `sbx env run` asks you to
  approve a one-time plan change for the working directory. The execution
  change takes effect after upgrading and restarting the daemon, even before
  you approve that plan."
- Unattended resolve bound: `env.go` `unattendedResolveTimeout = 30 *
  time.Second`.

### Credential commands

- `sandboxlib/secretresolver/command_workdir.go` `RunCredentialCommand`:
  "never uses the caller's or a stored source's directory. Explicit paths and
  dependencies remain trusted host code; this is not process confinement and
  does not make helpers or host temporary directories shared with a sandbox
  safe." `newResolverWorkdir` requires an absolute `os.TempDir()` and uses
  `os.MkdirTemp`; the directory is removed afterwards. `commandPathEnv` joins
  relative `PATH` entries to it.
- Help (`env`, `secret set`): "Command secrets run from a fresh temporary
  directory on the host ... Relative references such as ./helper or cat token
  no longer resolve against the project or daemon working directory ... sbx
  does not copy helpers, inspect their dependencies, or confine their
  execution ... Explicit paths into shared workspaces and broad mounts
  exposing host configuration or the host temporary directory remain unsafe,
  including mounts added later with sbx mount."
- Release body v0.46.0 lists the alternatives: "Run helpers by name from an
  absolute directory on the host's `PATH`, use absolute paths, or explicitly
  change to their private directory in the command."
- The plan row shows `workdir` as "fresh host temporary directory"
  (`env_plan.go` `secretSourceFields`).

### Snapshots and registries

- `types.go` `SecretSource.validate` (strings verbatim): "snapshot requires ref
  or command", "snapshot cannot be combined with refresh", "snapshot cannot be
  combined with noVerify", "snapshot command cannot select a backend",
  "snapshot supports only the cli backend". Docs: "A snapshot can't set
  `refresh` or `noVerify`. Cloud snapshots use CLI resolvers for vault
  references and don't support `backend: sdk`." The docs scope the `sdk`
  rejection to cloud; source rejects any non-`cli` backend for every snapshot,
  so source governs.
- `env.go` `provisionSecrets`: a snapshot is resolved with
  `resolveEnvSecretValue` and stored as a literal; an empty result is an error.
  `noVerify` only gates the verify step for non-snapshot sources.
- `types.go` `RegistrySource`: `Secret` required, `Username` optional ("token-only
  auth"); `env.go` `provisionRegistries` resolves both on the host and stores a
  literal snapshot.

### Removal, recovery, ownership

- Destroy plan scope: `env_plan.go` `undeclaredScopedCredentials`: "Removal
  reaches the scope, not the declarations: everything stored under it goes,
  including what an earlier revision of the file provisioned and what was added
  by hand". `storedCustomSecrets`: custom secrets "exist only here, and only in
  a destroy plan". Help (`env rm`): "service, custom, and registry
  credentials". Docs: "The plan includes all credentials stored at the
  sandbox's scope, including credentials that the environment file no longer
  declares."
- Only named rows deleted: `env.go` `cleanupScopedSecrets`: "Deleting only the
  named rows is what makes that impossible"; `reportUnnamed`: "kept %s: it
  appeared after the plan was approved, and no row named it". Reserved scopes:
  "refusing to remove the secrets at the reserved scope %q, which is shared".
- Binding pruning: `env_plan.go` `destroyBindingResources`: "Pruning removes a
  service's whole entry, so an OAuth mechanism or a domain another environment
  or the user added goes with it."; `env.go` `pruneBindings`: "an entry that
  moved is left as it is and reported". Docs: "`--prune-bindings` deletes the
  complete global binding entry for every service declared in the environment
  file. This can affect other sandboxes that share those service bindings."
  MCP: docs: "MCP registrations remain available to other sandboxes."
- Post-hook guard: `env_lifecycle.go` `teardown`: "A command that cannot run is
  a warning ... Drift is not, because the removal itself would be the damage";
  `env_plan_gate.go` `recheckDestroy` ("so nothing was removed") and
  `recheckSandbox` ("it was replaced while the teardown ran"). Help (`env`):
  "what one adds to the environment instead — a stored credential, an approved
  domain — stops the removal".
- Failed create: `env.go` `createAndAttach`/`envCreateCmd` order (`gatePlan`,
  initialize, `provision`, `executeCreate`, `postCreate`); `provision` order
  (secrets, registries, MCP, bindings); `partialCreateError` hint "remove
  provisioned secrets for this environment". Docs: "Secret provisioning, binding
  updates, and MCP server registration occur before the sandbox is created. If
  sandbox creation fails, scoped secrets remain, and bindings and MCP
  registrations may also remain."
- Existing-sandbox run: help (`env run`): "If the sandbox already exists it is
  started and re-attached without re-provisioning". Docs: "`sbx env run` applies
  updated `env` values to the new agent session and reconciles declared MCP
  servers. Changes to workspaces, kits, ports, secrets, bindings, and
  `sandboxOptions` take effect only when the sandbox is next created."
  `env.go` `reconcileMCP`: "Registration and live-add failures are warnings".
- Foreign name, create and run: `env_plan_gate.go` `foreignSandboxRunError`
  returns nil only `if ec.looksEnvCreated(rt) || ec.hasAppliedSandbox(rt)`; a
  sandbox that merely agrees is still refused ("agrees with everything this
  environment declares, but neither a file-level bind nor this machine's own
  recorded history shows sbx env ever built it, so nothing was done").
  `refuseForeignSandboxForRun`: "It is unconditional — no terminal prompt, no
  --auto-approve bypass". `env.go` `refuseExistingSandbox` runs before the plan
  and before provisioning.
- Foreign name, remove: `foreignSandboxError` returns nil `if
  ec.sandboxConflict(rt) == nil || ec.looksEnvCreated(rt) ||
  ec.hasAppliedSandbox(rt)`, so `rm` refuses only a sandbox that conflicts with
  the declaration and has no ownership sign. Comment: "--force does not pass
  this."
  Drift is not refusal: `hasAppliedSandbox` and `foreignSandboxError` comment
  ("read as this environment's own drift ... rather than as evidence of a
  stranger's sandbox").
- Cloned-workspace warning: release notes 0.45.x: "`sbx env rm` now warns about
  data loss for a cloned workspace before asking for confirmation";
  `env_plan_gate.go` `approveDestroy` prints `warnUnsavedCloneChanges` above the
  prompt ("git fetch, run before removing").

### MCP, ports, options

- Hosted control plane not required: `cli-plugin/commands/mcp_gateway_resolve.go`
  `mcpConfigured()` is `mcpGatewayModeEnabled() || os.Getenv("SBX_MCP_URL") !=
  ""`; `sandboxlib/platform/settings.go` `MCPGatewayModeEnabled()` returns
  `true`. The `Config.MCP` struct comment and the `provisionMCP` error string
  still say hosted control plane; they do not reflect the active predicate.
- URL forms: help (`sbx mcp add`): "Docker Hardened Images (DHI) image ref
  (dhi.io/<name>:<tag> ...)" and "Other image refs ... are no longer accepted".
  `--command` help: "Do not use --command with untrusted executables."
- Ports: `types.go` `PortBinding` and `validate`; docs ports table ("`tcp4`, or
  `tcp6` for IPv6 `hostIP`", "Loopback").
- Options: `types.go` `SandboxOptions` (`Skills` "Empty ... defers to the
  daemon's resolved default (built-in "readonly"...)"; `GPU` "Linux x86_64,
  single NVIDIA GPU, requires one-time privileged host setup"; `USB` "must not
  contain ';'"). Docs: "`readwrite` to let the sandbox modify shared skills".
  Retired keys: release notes retire `shareSkills`; no `cpu`,
  `governanceProfile` or `noShareSkills` field exists in `SandboxOptions`.
- Cloud: help (`env`, `--cloud` paragraphs) and docs "Use a cloud environment".
  Source `cli-plugin/commands/env_cloud.go` is build-tagged and supplemental
  only; the skill does not promise the flag exists on every build.

### Environment-file protection

- Root versus subdirectory mask: `env_plan.go` `reachedEnvFile` / `envFileMounts`
  and `env_plan_render.go` `renderWritableFiles`: "Nothing in the sandbox can
  rename a mount point" holds only at the root; a read-only file in a
  subdirectory is still reported. Help (`env`): "as it says when a file sits
  below a mount's own directory, where renaming that directory reaches it
  again". Docs: "Keep the file outside direct-mounted workspaces or directly in
  a workspace root."
- Lifecycle phases: help (`env`) and `sandboxlib/sbxenv/lifecycle.go`.
  `initialize` "runs on every create and every run, including one that only
  attaches". `sbx env exec` "runs no commands at all". Docs table:
  `postCreate` "Does not run when attaching to an existing sandbox".
- `env exec -d`: `sbx_env_exec.yaml` declares `detach`/`-d` with the usage
  "Detached mode (not supported)". `env run -d/--detached` ("Create/start the
  sandbox without attaching") is the supported form and exists on `env run`
  only.

## Historical fixes preserved

These upstream docker/skills corrections are kept in the current text:

- `201df14e8`: literal secret `value:` appears as a digest in both plan and
  state, while the source file still holds the plaintext (so it must not be
  committed); compatibility line shortened.
- `43f9ec0c4`: a failing `preRemove` is a warning; removal rechecks the destroy
  plan and sandbox identity, and new uncovered credentials, changed bindings or
  a replacement sandbox stop removal.
- `c331050e2`: the runbook proves `initialize` reruns while `postCreate` runs
  once and `env exec` adds neither. The markers are now constant stdout lines.
- `cd22c4ba7`: the compatibility line does not start with an "EXPERIMENTAL."
  label; status is carried by the catalog and the body.

## Removed or narrowed claims

| Earlier claim | Current wording | Evidence |
|---|---|---|
| Every environment file requires `schemaVersion` and `agent` | Required in the fully merged configuration; partial layers may omit them | `Config.Validate` runs once on the merged decode; `decodeDocument`: "behave as if the keys were simply absent" |
| Relative kit sources follow the same anchoring as `workspace:` | Only explicit `./`, `../`, `.`, `..`, `.zip` paths are anchored; bare names are left as written | `anchorKitSource`: "Only a source that cannot be anything but a path is rewritten. A bare `org/kit` is a registry reference"; `isRelativeKitPath` |
| "Nothing else is expanded" (only projectDir/fileDir) | `${{ env.args.NAME }}` also expands, in values only; `$` and `${VAR}` stay literal | `loader.go` doc comment; docs "Argument references and the two directory references are the only variable expressions expanded" |
| `env rm` "can remove exactly what it created" | Removes every credential at the sandbox scope named in the approved destroy plan, including undeclared and hand-added ones | `undeclaredScopedCredentials`, `storedCustomSecrets`, help "service, custom, and registry credentials" |
| `secrets:` and `registries:` entries "use the same value/ref/command shape" | Service secrets use one of value/ref/command; registries need nested `secret:` and optional `username:` | `RegistrySource`: "Secret ... is required; Username is optional"; docs: "Each entry requires `secret` and accepts an optional `username`" |
| `--prune-bindings` "also remove them" | Deletes each named service's whole stored entry, including other sandboxes' domains | `destroyBindingResources`: "Pruning removes a service's whole entry, so an OAuth mechanism or a domain another environment or the user added goes with it"; docs: "deletes the complete global binding entry" |
| Transient literal secrets "shown once in the plan" (before `201df14e8`) | Digest in plan and state; source file is plaintext | `valueFingerprint`; `secretSourceFields` |
| Preremove "never blocks removal" | Failure is a warning; drift after approval stops removal | `teardown`, `recheckDestroy`, `recheckSandbox` |
| `mcp.servers` "requires the hosted MCP control plane" | No hosted plane needed at v0.46.0 | `mcpConfigured`, `MCPGatewayModeEnabled() == true` |
| MCP `url:` accepts "registry/OCI reference" | Remote URL, community-registry URL, manifest URL, or `dhi.io` image; other image refs refused | `sbx mcp add` help: "Other image refs ... are no longer accepted" |
| `-d/--detached` exists on `env run` "ONLY" with no qualification | `env exec` lists `-d/--detach` but it is not supported | `sbx_env_exec.yaml`: "Detached mode (not supported)" |
| Snapshot `refresh` "ignored" (an earlier audit note) | Rejected with `refresh` and with `noVerify` | `SecretSource.validate`; docs "A snapshot can't set `refresh` or `noVerify`" |
| Earlier audit wording "declared-but-unused arguments are rejected" | Only supplied arguments the file does not declare are rejected; no declared-but-unreferenced check was found | `UnusedArgsError`: "every supplied argument the environment does not declare" |
| An earlier audit statement that docs and source agree on snapshot backends | They differ: docs scope `sdk` rejection to cloud; source rejects any non-`cli` backend for all snapshots | docs vs `SecretSource.validate` |
| Helper may be a relative path or `./helper` from the project | Relative helper paths resolve in a fresh temporary directory; use absolute reviewed helpers | Help: "Relative references such as ./helper or cat token no longer resolve against the project or daemon working directory"; `RunCredentialCommand`: "use an absolute helper path outside shared workspaces" |
| A same-named sandbox is fine to attach to or remove | Create and run refuse without an ownership sign even if it agrees; rm refuses only with a declaration conflict and no sign | predicates quoted under "Foreign name" above |
| Remembered approval "alias" | The only key is `env.rememberHostCommands`; no alias or environment-variable override exists in the frozen source | `settings.go` "Deliberately has NO EnvVar override" |
| Runbook hook wrote markers with `printf 'x\n' >> file` | Constant `printf '%s\n' marker` to hook stdout; in-sandbox write probe avoids nested-shell redirection | Conservative; the frozen `env exec` help has no VM-quoting warning (not verified) |
| Older installed-help cross-check (v0.42.0) proved behavior | Historical only | superseded target evidence above |

## Not verified

- No behavior was executed. Approval prompts, refusals, rollback, credential
  cleanup and mask behavior are read from source or docs only.
- Whether a real agent edits or renames protected paths, whether a helper loaded
  from a shared mount can be replaced before it runs, and how the OS keychain
  is scoped by `--app-name` are not verified.
- The 30-second unattended bound, cloud recovery windows and cloud build-tag
  details come from source or help and are not exercised.
- Release-note timing: only v0.46.0 changes cited above are attributed to that
  release. Other differences from the historical pin are not dated.

# Sources

## Local installed CLI

- `sbx --help`, `sbx create --help`, `sbx run --help`, `sbx secret --help`,
  `sbx secret set --help`, `sbx secret import --help`, `sbx policy --help`,
  `sbx policy init --help`, `sbx policy allow network --help`, `sbx ports
  --help`, `sbx prune --help` (where present) — captured against an
  installed `sbx` reporting `v0.37.0` (commit
  `8b65b864b0d49c29f05a55170d6b5eea4c0d11e7`).

## Pinned source (repository docker/sandboxes, commit `9f401f12cbe23b9abbc5051adf38e3f2df851a32`)

Paths below are relative to the repository root. The installed CLI above
predates this commit by roughly two months; where the two disagree, the
note below says so explicitly and the skill follows the pinned source
(the current, released behavior) rather than the older installed build.

- `sandboxlib/agentkits/agents/*/spec.yaml` — current built-in agent kit
  roster: `claude`, `claude-bedrock`, `claude-vertex`, `codex`, `cursor`,
  `devin`, `docker-agent`, `gemini`, `opencode`, `shell`. `copilot`,
  `kiro`, and `droid` are present in the installed v0.37.0 build but were
  removed as built-in kits before this commit (see commit history on the
  same paths in the repository: "feat(agents)!: remove the built-in
  copilot/droid/kiro agent"; "feat(agents): add embedded Devin agent").
- `sandboxlib/sandbox/validation.go` (`ValidateSandboxName`,
  `isValidNameChar`) — sandbox name rule: ASCII alphanumeric plus `.`/`-`
  only (no `+`, no `_`), at least 2 and at most 63 characters, must start
  and end with a letter or number, `default` is reserved. `+` was
  explicitly rejected in a fix to a secrets-engine panic (commit history:
  "fix(validation): reject '+' in sandbox names to prevent secrets-engine
  panic") predating this pinned commit.
- `cli-plugin/commands/credential_store.go` (`secretCmd`,
  `credentialsSetCmd`) — current registry-credential model: host-only by
  default, `-g`/`--all-sandboxes` inject into every new sandbox's registry
  login via the proxy at pull time, `--sandbox NAME` scopes to one sandbox;
  none of these write a credential to the sandbox filesystem. Also the
  source of the `-g`/`--global` deprecation on `secret set`/`secret rm`
  (global is now the default scope for service secrets).
- `sandboxlib/sandbox/sandbox.go` (`discoverStoredRegistryValues`) and
  `cli-plugin/commands/create_daemon.go` — comments explicitly state this
  "replaces the former `~/.docker/config.json` injection: the credential
  now lives only in the trusted daemon and rides a single MITM'd request,
  never the sandbox filesystem."
- `cli-plugin/commands/credentials.go`
  (`discoverCredentialSourcesForAgentWithoutPrompting`) and
  `cli-plugin/commands/create_daemon_bindings.go`
  (`discoverCredentialsForRun`) — current credential-discovery model:
  `sbx create`/`sbx run` never prompt or silently import host env vars;
  the keychain (via `sbx secret set`/`sbx secret import`) is the sole
  runtime source, and a missing required credential with no approved
  binding fails loudly instead of falling back to the shell environment.
- `sandboxlib/agentkits/agents/claude/spec.yaml`,
  `sandboxlib/agentkits/agents/devin/spec.yaml` — real shape of a kit's
  `credentials[]` declaration (`service`, `apiKey.name`, `apiKey.inject[]`,
  or `oauth`), used to replace a fabricated `credentials.sources: - env:
  [...]` example that does not exist in any shipped kit spec.
- `sandboxlib/sandbox/vm_configurator.go`, `sandboxlib/sandbox/credential_mode.go`
  — `SBX_CRED_<SERVICE>_MODE` container env var, one per declared
  credential service.
- `cli-plugin/commands/prune.go`, `cli-plugin/commands/clone_remote.go`,
  `cli-plugin/commands/create.go` (`validateCloneOptions`),
  `cli-plugin/commands/rm.go` (`refs/sandboxes/<name>/*` survivor-ref
  recovery) — `sbx prune`/`sbx create --clone`/`sbx rm` mechanics referenced
  by this skill's cross-links; see `docker-sandboxes-lifecycle` in the
  sibling PR (docker/skills#20) for the full write-up of these commands,
  which this skill only touches at the `sbx create`/`sbx run` surface.

## Note on `docker/skills#20`

A parallel PR (`docker-sandboxes-lifecycle`, `docker-sandboxes-network-credentials`,
`docker-sandboxes-env`, `docker-sandboxes-kits`) covers the same `sbx` CLI in
more depth and was verified against a closer-to-HEAD commit
(`df5c96ba60484fa2c375469dbac912c205da6c37`). Several of the fixes in this
skill's commit history were cross-checked against that PR's findings.

# Sources

Every rule in `SKILL.md` and every expectation in `checks/verification.md` and
the eval runbook traces to a row below. Nothing here was produced by executing
`sbx`: no sbx command, fixture, or runbook step ran while writing this version.

## Release record (target of this version)

- Target: sbx **v0.46.0**, stable (GitHub Latest; not a prerelease or draft),
  tag `v0.46.0`, published 2026-09-28T15:43:20Z, resolving to docker/sandboxes
  commit `991967dc90ce0d9a440cd1df1bdf3e395c5a2693`.
- The docker/sandboxes repository is internal. "internal @991967dc" below means
  that commit; the CLI reference files are `docs/yml/sbx*.yaml` generated from
  the binary's help (118 files at that commit). A public reader reproduces
  syntax with `sbx COMMAND --help` on v0.46.0.
- Public release notes (https://docs.docker.com/ai/sandboxes/release-notes/) end
  at 0.45.1, so v0.46.0 deltas come from the v0.46.0 GitHub release body
  (internal record) and internal source. Help is syntax evidence only; behavior
  rows cite docs or source explicitly.
- No installed or dev sbx build is used as evidence. This replaces the earlier
  0.1.0 provenance (docker/sandboxes `df5c96ba`, installed v0.42.0-503), which
  is superseded and not relied on anywhere below.
- Docker Sandboxes docs snapshots used (Markdown endpoints, SHA256):
  usage `05a1490e583bf26dfcdeff66c5a7e99b9558a17e9eb8eba6cc7a43c0bf6b67bb`,
  workflows/git `4c771eac694ed814aac5e7a52b35f054cb59ae459943bac779ab959ce1d3af99`,
  security `b96295ba328cb2bd9ce26d2beddd2389b674169c86a7d860ba509da4d0740fec`,
  workflows/agent-skills `a9d17219aa610e7dcd649ed78583310b27d8d1c6e30e41f641808d2321466922`,
  release-notes `d02d904cbbd22f833de0cc28d33de4c6bee26757b7bdbe60ed20439fbfa8f8a3`,
  troubleshooting `f7aac22d3b4be6742ef94440616a54359fd35630282cd46b4ad651f8293c3628`.

## Claim map

Help = `sbx COMMAND --help` field at v0.46.0 (internal @991967dc `docs/yml/`).
Paths under `cli-plugin/commands/` and `sandboxlib/` are internal @991967dc.

| Claim in this skill | Source | Supporting excerpt |
| --- | --- | --- |
| `sbx create` with no path mounts nothing; `sbx run` with no path mounts the cwd | Help `sbx create` description; Help `sbx run` description; `run.go:maybeAddDefaultWorkspaceArg` | "Omit the path to create a sandbox without a workspace bind mount" / "Omit the path to mount the current directory." |
| `run -d` starts the sandbox and prints its ID without a session | Help `sbx run --detached` | "Start the sandbox and print its ID without opening an agent session" |
| Reattach with `--name`; bare `NAME` is a deprecated shorthand | Help `sbx run` description; `run.go:warnDeprecatedRunPositionalName`, `legacyPositionalAttach` | "To re-attach to an existing sandbox by name, use --name" |
| Relative kit reference must be an explicit path | Help `sbx run`/`sbx create` description | "Relative local references must be explicit paths such as ./my-kit or ../my-kit.zip" |
| Embedded agent catalog is claude, codex, cursor, devin, docker-agent, gemini, opencode, shell | `sandboxlib/agentcatalog/catalog.go:agents`, `Selectable` | table rows `{Name: "claude" …}` through `{Name: "shell" …}`; `claude-bedrock`/`claude-vertex` are `Variant: true`, "hidden from default create menus", and are deliberately not listed |
| `copilot`, `droid`, `kiro` resolve to pinned public kits by name | `catalog.go:extracted`, `RecreateHint`; Help `sbx run` "Available agents"; public release notes 0.43.0; troubleshooting "Kiro, Copilot, or Droid shorthand fails" | "`sbx run kiro` resolves the pinned replacement kit" |
| Creation-only flags (`--template`, `--memory`, `--cpus`, `--skills`) fail on reattach | `run.go` reattach branch (lines 817–841, the `usedFlags` loop) | "sandbox '%s' already exists; %s can only be used when creating a new sandbox" |
| `-p/--publish` is ignored on reattach | Help `sbx run --publish` | "Applied when the sandbox is created; ignored when re-attaching (use \"sbx ports\")" |
| `--clone` runs on a private in-container clone; host repo mounted read-only; commits reachable via `sandbox-<name>` | Help `sbx create --clone`; docs workflows/git "Clone mode" | "(mounted read-only) … the agent's commits are accessible via the sandbox-<name> git remote on the host" |
| `--clone` preconditions: explicit path, in a Git repo, not a worktree, real `.git` directory | `create.go:validateCloneOptions` (help only gives the flag) | validation rejects missing path, worktree, and `.git` pointer/submodule layouts |
| `--clone` on reattach: no-op for clone-mode sandbox, error for plain sandbox | Help `sbx run --clone`; `run.go:resolveCloneWorkdirForExistingSandbox` | "no-op when re-attaching to an existing clone-mode sandbox" |
| Clone remote works only while the sandbox runs; restart changes port, CLI updates URL | docs workflows/git "Sandbox remote behavior" | "`sbx stop` shuts down the daemon. `git fetch sandbox-<name>` fails until the sandbox starts again." |
| `sbx create` sandboxes stop after going idle | public release notes 0.43.0, "Sandbox lifecycle and workspaces" | "Sandboxes created with `sbx create` now stop automatically after becoming idle." |
| Fetch populates `refs/remotes/sandbox-<name>/*` and survivor `refs/sandboxes/<name>/*`; only fetched branches get survivor refs; commits not fetched or pushed elsewhere are lost on removal | `rm.go:warnUnsavedCloneChanges` (382–416); `sandboxlib/workspace/git_remote.go:ConfigureCloneRemoteContext` | "Fetched branches are mirrored into refs/sandboxes/%s/* and survive removal; recover any branch with: git branch <local-name> refs/sandboxes/%s/<branch>" |
| `rm`/real `prune` print the unsaved-commits warning; `--force` skips the prompt, not the warning | `rm.go` calls `warnUnsavedCloneChanges` at line 114 (`removeAll`) and line 279 (by-name removal), before the `!force` branches at lines 121 and 288; `prune.go:runPrune` line 212 before the `!opts.force` check (214) | warning call precedes `if !force {` / `if !opts.force && !isStdinInteractive(cmd)` |
| `rm` removes containers, Git worktrees, state, scoped secrets; cannot be undone; `--force` also removes an in-use sandbox | Help `sbx rm` description and `--force` | "cleans up any Git worktrees, deletes sandbox state, and deletes secrets scoped to each removed sandbox. This action cannot be undone." |
| `:ro` blocks writes; a read-only argument may name a file; not a way to hide content | Help `sbx run` description; docs security "Security considerations" | "holds that one path out of reach inside a workspace the sandbox can otherwise write"; no statement that reads are blocked |
| Direct mode edits are live on the host; hooks, CI config, IDE tasks, AI project config, `Makefile`, `package.json` scripts; hooks absent from `git diff` | docs security "Security considerations" | "Git hooks live inside `.git/` and do not appear in `git diff` output — check them separately." |
| Reviewing fetched clone commits (hooks, build files) before checking them out or running them on the host | Skill policy extended from the security paragraph above; the docs state it for direct mode only. `SKILL.md` places it beside fetch and recovery, and eval Prompt 2 expects it | not a source claim |
| `--skills off\|readonly\|readwrite`; default readonly or `skills.defaultMode`; creation only | Help `sbx create --skills`, `sbx run --skills`; `create.go:validateSkillsMode` | "Default: readonly, or the configured skills.defaultMode setting. Can only be used when creating a new sandbox." / `invalid --skills value %q: must be "off", "readonly", or "readwrite"` |
| Mode change requires remove and recreate; shared skills are experimental | docs workflows/agent-skills "Shared store behavior" | "Remove and recreate a sandbox to change its mode." / "Shared agent skills are experimental." |
| `readwrite` sandbox can change skills other sandboxes load; `readonly` does not isolate from that; `--skills=off` keeps a sandbox outside the boundary | docs workflows/agent-skills warning; docs security "Security considerations" | "Read-only access prevents writes from that sandbox but does not isolate it from changes to the store." / "Use `--skills=off` when creating a sandbox to keep it outside this shared trust boundary." |
| Shared store mounts for supported agents; whether `shell` is one is unverified | docs security "What crosses the boundary into the VM"; docs agent-skills import table (Claude Code, Codex, Devin, Copilot, Cursor, Droid) | "sandboxes created for supported agents mount a persistent host-side store"; `shell` not listed |
| Kit installs can write their own skills while the store is read-only | v0.46.0 GitHub release body, "Kits and skills" | "The shared skills store remains read-only, while kit installation and startup commands can write their own skills" (recorded only as context; no rule depends on it) |
| `exec` flags mirror `docker exec` except detached mode; `-d` rejected | Help `sbx exec` description and `--detach` ("Detached mode (not supported)"); `exec.go:registerExecFlags` `cmd.Args` validator (lines 73–86); public release notes 0.45.0 | `--detach is not supported for exec; omit -d to run the command in the foreground` |
| `exec` starts a stopped sandbox; default workdir is the primary workspace | Help `sbx exec` description; docs usage "Choose a workspace" | "If the sandbox is stopped, it is started first." / "`sbx exec` uses it as the default working directory" |
| `cp` needs exactly one `SANDBOX:PATH`; no sandbox-to-sandbox | Help `sbx cp` | usage and description of `sbx cp` |
| `ports` lists, publishes, and unpublishes on an existing sandbox; default binding is loopback, default protocol `tcp4`; unpublish takes the same spec | Help `sbx ports` description, `--publish`, `--unpublish`; `references/port-publishing.md` | "If HOST_IP is omitted, the port is bound on loopback" / "When publishing without a PROTOCOL, tcp4 is used". The help examples are `--publish 8080`, `--publish 3000:8080`, `--unpublish 3000:8080`; `127.0.0.1:18080:8080/tcp4` is a derived example following the documented spec format, not a quoted help example |
| `prune` removes only stopped sandboxes, never running ones | Help `sbx prune` description | "Only stopped sandboxes are candidates — a running sandbox is never removed" |
| `prune` is irreversible and deletes scoped secrets; `--force` skips prompt and removes in-use sandboxes | Help `sbx prune` description and `--force` | "This action cannot be undone. Secrets scoped to each successfully pruned sandbox are also deleted." |
| `until=` accepts RFC 3339, Unix timestamp, Go duration; selects sandboxes stopped before the cutoff; age is stop time | Help `sbx prune --filter`; docs usage "Start, stop, and remove"; public release notes 0.43.0; `prune.go:parsePruneFilters` (238–263), `selectPruneCandidates` (346–380) | "narrow the set to sandboxes that stopped before TIMESTAMP" / "The `until` filter uses the time the sandbox stopped." |
| With an age filter, an unknown stop time is excluded and reported; an unfiltered prune includes such sandboxes | Help `sbx prune` description; `prune.go:selectPruneCandidates` (the `StoppedAt.IsZero()` check sits inside `if filter.set`), `runPrune` (stderr note), `pruneDryRunJSON.SkippedUnknownStop` | "A sandbox whose stop time the daemon cannot report is left alone"; note text "remove explicitly with 'sbx rm'" |
| `since=` is a legacy accepted alias; one age filter only; other keys rejected | `prune.go:parsePruneFilters`; docs usage | "The older `since=<duration>` filter remains supported."; `duplicate age filter`; `unsupported filter key` |
| `--dry-run` lists candidates and does not print the clone warning; `--json` only with `--dry-run`; non-TTY needs `--force` | `prune.go:runPrune` (179–215); Help `sbx prune --json`, `--dry-run` | `errPruneJSONNeedsDryRun`; dry-run returns at line 209 before `warnUnsavedCloneChanges` (212); `stdin is not a terminal; use --force to skip confirmation` |
| `--cpus 0` is all host CPUs, at most 16 on Linux arm64; explicit value can exceed | Help `sbx create --cpus`; v0.46.0 GitHub release body | "0 = auto: all host CPUs, at most 16 on Linux arm64" / "Use `--cpus` to request a larger allocation." |
| Memory: binary units, minimum 512 MiB, default 50% clamped 512 MiB–32 GiB, maximum max(75%, 512 MiB) | Help `sbx create --memory` | "Minimum: 512 MiB. Default: 50% of host memory, clamped to 512 MiB–32 GiB. Maximum: max(75% of host memory, 512 MiB)" |
| Name rules: at least two characters, letter/number start, letters/numbers/hyphens/periods, at most 63, alphanumeric end, `default` reserved | Help `sbx create --name`; `sandboxlib/validation/vm.go:ValidateVMName` | `sandbox name cannot be 'default'`; `must end with an alphanumeric character` |
| `--kit` accepts a mixin; kit authoring is another skill | Help `sbx create --kit` | "Additional kit reference (must be a mixin; directory, ZIP, git, or OCI)" |
| `--cloud` is out of scope | Help inherited `--cloud` option | "Dispatch to Docker Cloud Sandboxes API instead of local sandboxd" |
| Runbook: `--app-name` is a hidden persistent flag; suffix letters/digits/hyphens/underscores, max 20; storage under `sandboxes-<suffix>` | `cli-plugin/commands/root.go:configureAppName`, `rootFlags`; `sandboxlib/storagepaths/storagekit.go:SetAppName`, `MaxAppNameSuffixLen` | "SetAppName sets a suffix … resulting in \"sandboxes-<suffix>\"" / "must not exceed MaxAppNameSuffixLen characters" |
| Runbook cleanup: state, cache, config, data, temp, logs roots exist per app name; discovery is best-effort because custom roots exist | `sandboxlib/storagepaths/storage_paths.go:ResolveAllRoots`; `cli-plugin/commands/root.go` (lines 422–431, `SANDBOXES_STORAGE_ROOT` overrides); docs troubleshooting "Removing all state" | "the top-level directories for the current app name under each OS base directory (state, cache, config, data, temp, logs)" / "If you have set custom `XDG_STATE_HOME`, `XDG_CACHE_HOME`, or `XDG_CONFIG_HOME` environment variables, replace…" |

## Recorded conflicts

- **Agent list.** The task brief listed `pi` (and `copilot` as built-in). `pi`
  does not appear in `catalog.go`, in `sbx create --help`/`sbx run --help`
  "Available agents" (claude, codex, copilot, cursor, devin, docker-agent,
  droid, gemini, kiro, opencode, shell), or in the docs. `copilot` is an
  extracted kit, not an embedded catalog row. The skill follows the pinned
  catalog and the help lists; `pi` is omitted as unverified.
- **Prune safety wording.** Help says the stopped-only rule "makes this safe to
  run habitually". The same help says removal "cannot be undone" and deletes
  scoped secrets, and `rm.go` shows unfetched clone commits are lost. The skill
  reads the help phrase as about running sandboxes only.
- **Public docs lag.** Public notes stop at 0.45.1; v0.46.0 rows use the
  release body and internal source.

## Not verified or excluded

- Effect of each `--skills` mode on a `shell` sandbox, and mounted paths, are not
  verified; runbook step 8 checks only flag validation.
- `sbx skills ...`, `sbx settings ...`, `sbx mount`/`sbx umount` (hidden in
  `mount.go:mountCmd`, `umountCmd`), and `--cloud` are out of scope; no workflow
  is taught. The hidden `--no-share-skills` flag and ephemeral or dynamic mount
  behavior are not claimed.
- The clone-candidate check before `prune` (a `sandbox-<name>` remote in the
  workspace's Git config) is skill policy; the docs state the remote is added
  to the host repository, not that prune consults it.
- Layout of app-named directories outside macOS and Linux, and any temp-directory
  socket path, are not verified; runbook step 9 says verify locally.
- No numeric disk-usage claim is made. No routing behavior was measured.

## Removed-claims log (baseline 0.1.0 to 0.2.0)

| Removed or narrowed claim | Class | Evidence |
| --- | --- | --- |
| `sbx exec` flags mirror `docker exec` including `-d` | stale-at-v0.46.0 | `exec.go:registerExecFlags` `cmd.Args` validator; Help `sbx exec` "detached exec (-d/--detach) is not supported" |
| `--cpus` 0 = all host CPUs | stale-at-v0.46.0 | Help `sbx create --cpus`: "at most 16 on Linux arm64" |
| `--filter until=` is "source-only … differs from some installed builds" | stale-at-v0.46.0 | Help `sbx prune --filter` documents `until=`; public notes 0.43.0 |
| `--filter since=` "legacy-only if your installed help does not show `until=`" | narrowed to: legacy accepted alias | `prune.go:parsePruneFilters`; docs usage |
| "Always preview with `--dry-run` … and read the clone-commit warning it prints" | stale-at-v0.46.0 (incorrect) | `prune.go:runPrune`: dry run returns before `warnUnsavedCloneChanges` |
| "don't suppress it with `--force` out of habit" | narrowed | `--force` skips the prompt but the warning still prints (`rm.go`, `prune.go`) |
| "fetch or pull from it" (clone remote) | narrowed to fetch | docs workflows/git documents fetch only |
| "(and, through it, the proxy-less agent process)" | unsupported | No frozen public doc substantiates "proxy-less"; the readable-secret warning is kept |
| "sbx prune --filter … an older installed `sbx` may still advertise `--filter since=DURATION`" | unsupported | No preserved help transcript of that build |
| "Every other command … showed no source-only difference between installed help and pinned-source" | unsupported | No transcripts preserved; v0.46.0 help differs for exec, sizing, skills |
| "No docs.docker.com URL beyond the product page is cited" | stale-at-v0.46.0 | Public docs pages are cited above |
| Source pin `df5c96ba` and installed `v0.42.0-503` provenance | stale-at-v0.46.0 | Replaced by the release record above |
| Kits pointer "kit `spec.yaml`" in Do-not-use and Related skills | moved to sibling | Schema-neutral wording; format teaching stays in `docker-sandboxes-kits` |

## Eval edit log

- Prompts 1, 4, 5, 6, 7 are unchanged, with their check groups.
- Prompt 2: added expected behaviors (clone must be running to fetch; review
  fetched commits before host use; pushing to a verified remote also keeps
  commits) and a start step before the fetch, because `sbx create` sandboxes stop when idle and
  a stopped clone does not serve fetches (docs workflows/git; release notes
  0.43.0). The `sl-disposable-clone` and `sl-fetch-scoped` lines are kept.
- Prompt 3: replaced "current pinned-source flag" and "older/installed help"
  wording with v0.46.0 help wording (stale provenance). Must-not items unchanged.
- Prompts 8 to 11 are appended (exec rejection, prune cutoff, shared skills
  modes, sizing), each with a skip group and reason. The static group and its
  five check IDs are unchanged.
- Runbook steps 1 to 6 are kept with the same fixtures; step 4 adds a
  stopped-fetch failure; step 6 adds JSON fields and rejected input; steps 7
  and 8 are added; cleanup, renumbered as step 9, adds an app-named directory listing.

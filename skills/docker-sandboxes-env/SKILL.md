---
name: docker-sandboxes-env
description: Use this skill when authoring, planning, or running a declarative `sbxenv.yaml` file for Docker Sandboxes (`sbx env create/run/plan/exec/rm`), even if the user just says they want to "check in a sandbox config", "make onboarding reproducible for a sandbox", "run a setup script before the agent starts", or "define arguments for a shared sandbox environment". Covers the sbxenv.yaml schema (schemaVersion, agent, kits, workspace/additionalWorkspaces, args, env, secrets, registries, bindings, mcp, ports, sandboxOptions), host `lifecycle:` commands (initialize/postCreate/preRemove) and their approval-plan model, multi-file merge (`-f`-style deep merge and the user-level `.sbxenv.yaml` base layer), and file-write-protection (`sandboxOptions.writableEnvFiles`).
license: Apache-2.0
compatibility: Requires standalone sbx with sbx env support and sbxenv.yaml schemaVersion "1", not the legacy docker sandbox wrapper. Checked against sbx v0.46.0 (docker/sandboxes 991967dc90ce0d9a440cd1df1bdf3e395c5a2693) by reading frozen help, public docs and source; behavior was not run. Public release notes end at 0.45.1. docker_help does not cover standalone sbx. See references/sources.md.
---

# Docker Sandboxes: Declarative sbxenv.yaml Environments

## Overview

`sbxenv.yaml` (schemaVersion `"1"`, EXPERIMENTAL) declaratively describes one
sandbox environment — agent, mixin kits, workspace mounts, environment
variables, secrets/registries/bindings to provision, MCP servers, ports, and
host-side lifecycle commands — so `sbx env create|run|plan|exec|rm` can stand
it up and tear it down reproducibly instead of a long flag invocation. This
skill owns that file format end to end. It delegates the sandbox lifecycle
semantics it wraps, the credential/network model it provisions into, and the
kit format its `kits:` entries reference, to their own skills.

## When to use this skill

Activate this skill when:
- The user wants a checked-in, reproducible definition of a sandbox
  environment instead of a long `sbx create`/`sbx run` command line.
- The user wants host-side setup/teardown commands (cloning a repo, seeding
  fixtures, archiving state) tied to a sandbox's create/attach/remove
  lifecycle.
- The user wants to parameterize a shared environment file with named
  arguments (`args:` + `--env-arg`).
- The user is debugging why `sbx env create`/`run` is asking for approval,
  or why a file, kit, or secret it declares was skipped or flagged.

## Do not use this skill when

Do not use this skill when:
- The task is the underlying `sbx create`/`run`/`rm` flag-based workflow with
  no `sbxenv.yaml` file involved — use `docker-sandboxes-lifecycle`.
- The task is choosing network policy or storing a secret/registry
  credential independent of any environment file — use
  `docker-sandboxes-network-credentials` (this skill's `secrets:`/
  `registries:`/`bindings:` blocks provision into that same store, but do not
  redefine its rules here).
- The task is authoring the v2 `spec.yaml` kit a `kits:` entry points at
  — use `docker-sandboxes-kits`. For v3 kit-format questions it states that
  v3 descriptors are a separate format it does not cover.

## Core guidance

### File resolution, merge, and required fields

- A directory `PATH` resolves to exactly `<PATH>/sbxenv.yaml`; any other file
  name is read only when a `PATH` names it. A project-level `.sbxenv.yaml` is
  **not** read as the project's own file (that hidden name is only the home
  base layer, below).
- `schemaVersion: "1"` and `agent:` (a built-in agent or the manifest name of
  an agent kit supplied via `kits:`) are required in the **fully merged**
  configuration, not in every layer. A partial overlay or the home base may
  omit either; if the merge still lacks one, validation fails. Unknown keys
  fail and name the file, line and column. `agent: shell` needs no
  credentials and is the simplest way to validate a file's mechanics.
- `sbx env create|run|plan|exec|rm` take one or more positional `PATH`
  arguments (there is no `-f` flag). Several paths deep-merge in order, like
  `docker compose -f`: mappings merge by key, sequences concatenate, other
  values are replaced by the last file. Lists such as `ports` and
  `mcp.servers` declared in two layers appear twice.
- `kits:` entries whose source is the same after anchoring coalesce into one
  entry and their `args` merge key by key (last file wins); restating a kit in
  an overlay to change an argument does not apply it twice. Preview a merge
  with `sbx env plan base.sbxenv.yaml local.sbxenv.yaml` (read-only).
- Pass the same `PATH` list, `--name` and `--env-arg` values to every command
  addressing one environment, including `env rm`.

### Naming, workspace, and the `.sbxenv.yaml` user base layer

- Unless the file sets `name:` or `--name` overrides it, the sandbox is
  named after the mounted directory (or the project directory when nothing
  is mounted) — so an environment that mounts nothing is still the same
  sandbox every time it is applied. **Two different environment files in the
  same directory derive the same sandbox name and collide** unless each sets
  its own `name:` (or you pass a distinct `--name` per invocation) — always
  give each its own explicit `name:`.
- **A matching name is not ownership.** `create` and `run` refuse a sandbox
  with no sign of being this environment's own, even if it matches the file;
  `rm` refuses one that also disagrees with the file. `-y` and `--force` do not
  override either. Give the project its own `name:`; `sbx rm` the other only if
  it is yours; never auto-adopt or replace it. See
  `references/removal-and-recovery.md`.
- `workspace:` names the read/write mount, exactly like `sbx create`'s
  omitted-path behavior: **omitting `workspace:` mounts nothing** at all.
  A relative `workspace:` path resolves against the **directory of the file
  that declares it** — `workspace: .` mounts the directory the file sits
  in. `${{ env.projectDir }}` names the project directory (the one holding
  the first `PATH`, or cwd when none is named); `${{ env.fileDir }}` names
  the declaring file's own directory.
- `workspace:` may be `{path, clone}`; `clone: true` or `--clone` clones only the
  **primary** workspace (a Git repository, not a worktree); additional
  workspaces are direct mounts. See `references/env-schema-fields.md`.
- Only an explicit relative kit path (`./kits/tool`, a parent-relative path,
  `.`, `..`, or a relative `.zip`) is anchored to the declaring file's directory. A bare
  `kits/tool` is left as written and resolved like any other kit reference, so
  write local kits with a leading `./`.
- With **no `PATH`** given, an `.sbxenv.yaml` in the **home directory** is
  merged underneath as a base layer for defaults shared across projects;
  naming any `PATH` skips this layer entirely. The base layer may not set
  `name:` (which identifies one project) and its `workspace:` must be rooted at
  `${{ env.projectDir }}` — any other value would mount one fixed
  directory under every project that merges it.

### `args:` — parameterizing a shared file

- Declare named inputs under `args:`, each with a `default` (making it
  optional, `default: ""` counts as a real default) or `required: true`
  (mutually exclusive), plus optional `description`, `enum`, or `pattern`.
- Reference one as `${{ env.args.NAME }}` in a **value**, never in a field name
  or inside `args:`. A bare `$` and `${VAR}` stay literal; nothing is read from
  the host environment.
- Precedence: `default`, then each `--env-args-file` in order, then every
  `--env-arg NAME=VALUE` (highest). Missing required, invalid, undeclared and
  unknown arguments are errors, not silent defaults. Supply them with
  `--env-arg NAME=VALUE` (repeatable) or `--env-args-file PATH`. Details:
  `references/env-schema-fields.md`.

### `lifecycle:` — host commands and the approval plan

- `lifecycle:` declares shell commands that run **on the host, outside the
  sandbox, with your own privileges** — not inside the container. Three
  phases, run in this order per invocation:
  - **`initialize`** — runs on **every** `create` **and** `run`, including
    one that only attaches to an existing sandbox. It is the one phase that
    can produce what the environment needs to exist (a cloned workspace, a
    generated file), so **it must be idempotent** — it reruns on every
    reattach.
  - **`postCreate`** — runs once, after the sandbox exists, before an
    interactive attach takes the terminal.
  - **`preRemove`** — runs before `sbx env rm` deletes the sandbox, while
    `sbx env exec` can still reach it. **A failing `preRemove` is only a
    warning** — the failure itself does not block removal. After the hook,
    removal rechecks the approved destroy plan and sandbox identity. A new
    credential or changed binding not covered by that approval, or a
    replacement sandbox under the same name, stops removal before deletion.
    Review the new destroy plan before retrying.
  - `sbx env exec` **runs no lifecycle commands at all, and requires the
    sandbox to already exist** — it does not create one. Run
    `sbx env create`/`sbx env run` first. Do not pass `-d` to `env exec`; help
    lists it as "not supported" (`env run -d` is the detached form).
  ```yaml
  lifecycle:
    initialize:
      - command: test -d app || git clone https://github.com/acme/app
    postCreate:
      - command: ./scripts/seed-fixtures.sh
    preRemove:
      - command: ./scripts/archive-state.sh
  ```
- Every command runs through the shell from the **project directory** by
  default (override per-command with `workdir:`; bound its runtime with
  `timeout:`). Credential `command:` sources do **not** use this directory
  (see below).

### Approval and the plan: host code, `-y`, and remembered consent

- The plan that `create`/`run`/`rm` ask you to approve includes host code:
  lifecycle commands **and** `command:` sources under `secrets:` and
  `registries:`. Approving a command also trusts whatever it invokes, including
  a script whose contents can change after the answer. **Never treat an
  untrusted file's or an untrusted kit's host commands as pre-approved**; a
  printed plan is not a safety review.
- A plan holding any of that host code is asked about on **every** invocation,
  changed or not. Only a plan with **no** host code, unchanged from what was
  approved, applies silently. After the v0.46.0 upgrade, an environment with
  secret commands asks once to approve the working-directory change.
- `-y`/`--auto-approve` approves that one invocation and **records nothing**; it
  does not quiet the next interactive run. Use it only for reviewed files and
  kits, never for pull requests or forks. `env rm` has no `-y`; use `--force`
  without a terminal. `-d` (detached `env run`) is unrelated to `-y`.
- `--skip-host-commands` skips **lifecycle** commands only. Credential
  resolution, verification, snapshot and registry resolution still run, so it is
  not a way to run no host code.
- `env.rememberHostCommands` is a machine-wide setting, default `false`, with no
  file toggle and no environment-variable override. Inspect with
  `sbx settings get env.rememberHostCommands`; turning it on is an opt-in for
  reviewed files only (`sbx settings set env.rememberHostCommands true`); the
  inverse is `sbx settings unset env.rememberHostCommands`. Do not change it
  without asking. Details: `references/approval-and-host-code.md`.
- `sbx env plan [PATH...]` prints everything applying the file would set up
  (host commands, credentials/bindings, MCP registrations, directories, ports,
  the sandbox, its variables) against what was last applied/approved. **It
  changes nothing.** A literal `value:` is the one field shown in the plan and
  recorded to state as a `sha256:` digest; `ref:`/`command:` show their source,
  not the resolved value. The digest does not protect the source file.

### Secrets, registries, bindings, snapshots, and credential commands

- `secrets:` and `registries:` provision into the **same credential store**
  `sbx secret set` uses, at this environment's **sandbox scope**. A service
  secret uses exactly one of `value`/`ref`/`command`. A registry entry is
  different: a required nested `secret:` source and an optional `username:`
  source (omitted means token-only). See `docker-sandboxes-network-credentials`
  for what they mean at runtime.
- **Never write a literal secret value directly into a checked-in
  `sbxenv.yaml`.** Use `ref:` (1Password/AWS Secrets Manager) or `command:`
  so the value never lives in the file at all; if a literal `value:` is used
  transiently, both the plan and state show only its digest, but the
  original environment file still contains the plaintext secret. The labeled
  `secrets:` fragment in `references/env-schema-fields.md` is intentionally not
  part of the minimal asset, which needs no credentials to validate.
- `snapshot: true` (only with `ref` or `command`) resolves once on the host after
  approval, stores a literal, and never refreshes; recreate to rotate. It is
  rejected with `value`, `refresh`, or `noVerify`; a `command` snapshot cannot
  pick a backend; `sdk` is rejected for any snapshot.
- `bindings:` are per-service credential bindings merged into the user's
  **global** `credentials.yaml`. They are **left in place by default** by
  `sbx env rm`. `--prune-bindings` deletes each named service's **entire**
  stored entry, including domains another sandbox added, and can change consent
  for other sandboxes. Read the destroy plan first.
- A secret `command:` runs from a **fresh absolute temporary directory** on the
  host, not the project directory, so `./helper` no longer resolves. Use an
  absolute, reviewed helper and keep it and its dependencies outside every
  writable sandbox mount. This is not confinement; explicit shared paths and
  later broad mounts remain unsafe. Lifecycle commands keep the project cwd.

### Update, failure, and removal

- `env run` on an existing sandbox re-attaches without reprovisioning: it
  applies `env:` to the new session and reconciles MCP servers. Everything else
  (workspace, kits, secrets, bindings, ports, `sandboxOptions`, `postCreate`)
  takes effect only at creation; recreating needs `env rm` and an explicit yes.
- `env rm` builds its destroy plan from the resources on the host: **all**
  credentials at this sandbox's scope, including undeclared and hand-added
  ones. Only approved rows are deleted. MCP registrations stay.
- Provisioning is not transactional: credentials, bindings and MCP
  registrations can exist after a failed create. Recover with the same files,
  name and arguments and a reviewed `sbx env rm`, never a generic cleanup.
- `sbx --cloud env` (experimental) rejects host workspaces, ports, registries,
  MCP and dynamic secret sources. Details: `references/removal-and-recovery.md`.

### `kits:`, `additionalWorkspaces:`, `mcp:`, `ports:`, and `sandboxOptions:`

- `kits:` composes mixin kits (and, exactly once, an agent kit named by
  `agent:`); see `docker-sandboxes-kits`. `additionalWorkspaces:` needs a
  primary `workspace:` and is the file form of `sbx run`'s extra `:ro`
  workspace arguments.
- `mcp.servers:` registers MCP servers on the host (host-global, **left in
  place** by `sbx env rm`); a `command:` server runs on the host. `ports:` is
  the file form of `sbx ports --publish`, torn down with the sandbox; the
  default bind is loopback, so widen it deliberately.
- `sandboxOptions:` maps onto `sbx create` flags (`template`, `memory`, `cpus`,
  `pullPolicy`, `profile`, `skills`) plus opt-in host hardware (`display`,
  `gpu`, `usb`). `skills: readwrite` lets the sandbox change the shared skills
  store. Shapes: `references/env-schema-fields.md`.

### `sandboxOptions.writableEnvFiles` — a deliberate, explicit downgrade

- By default, **every environment file mounted inside the workspace is
  read-only at its own path**, even though the rest of the mount is
  writable. This stops an agent editing the very file that decides what
  host lifecycle commands and secret-resolving commands run on your machine
  on the next invocation.
- Set `sandboxOptions.writableEnvFiles: true` only where an agent is
  deliberately meant to edit its own environment file. This is a real
  security downgrade — the plan then reports the file as writable — so
  treat it the same as any other explicit trust decision, not a default.
- **The protection is complete only at a mount's own root.** A file directly
  at the root of a read-write mount cannot be reached even by renaming,
  because the sandbox cannot rename the mount point itself. A file in a
  **subdirectory** is read-only only at its current path: the sandbox can
  rename the writable directory holding it and recreate a sandbox-controlled
  file at the original path. `sbx env plan` flags this gap for a file not at a
  mount's root — read its output. The mask is path protection, not
  confinement of host code.

## Related skills

- For the `sbx create`/`run`/`rm` flag-based workflow this file wraps, use
  `docker-sandboxes-lifecycle`.
- For what `secrets:`/`registries:`/`bindings:` mean at runtime, and for
  configuring network policy independent of any environment file, use
  `docker-sandboxes-network-credentials`.
- For v2 `spec.yaml` authoring and kit-format questions, use
  `docker-sandboxes-kits`. For v3 requests it states that v3 is not covered;
  it does not supply a descriptor authoring workflow.

## References

- `skill.yaml` — routing metadata for this skill (owns, use/do-not-use, delegates, version).
- `agents/openai.yaml` — agent-discovery metadata (display name, short description, default prompt).
- `references/sources.md` — provenance for every rule above, the evidence classes, and the log of removed or narrowed claims.
- `references/env-schema-fields.md` — field shapes, merge and argument rules, snapshot and hardware options, and YAML fragments.
- `references/approval-and-host-code.md` — what counts as host code, `-y`, `--skip-host-commands`, remembered consent and its inverse, credential-command directory and helper placement.
- `references/removal-and-recovery.md` — creation-only versus attach changes, destroy-plan scope, binding pruning, failed-create recovery, foreign-name refusal, and cloud-mode limits.

## Assets

- `assets/sbxenv.yaml` — a complete, minimal, safe example: a `shell` agent mounting the declaring file's own directory, one static env var, and no credentials at all; it validates and plans without onboarding authentication.

## Checks

- `checks/verification.md` — Verification runbook for sbxenv.yaml commands (unexecuted runbook; run manually with an isolated, uniquely-named `--app-name`, dummy values only, never with real secret values or untrusted lifecycle commands auto-approved).

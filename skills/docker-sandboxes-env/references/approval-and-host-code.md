# Approval, host code, and credential commands

Detail for the approval rules in `SKILL.md`. Verified against sbx v0.46.0
frozen help, the frozen public page and settings page, and docker/sandboxes
`991967dc90ce0d9a440cd1df1bdf3e395c5a2693` (`cli-plugin/commands/env_plan_gate.go`,
`env_plan.go`, `sandboxlib/secretresolver/command_workdir.go`). Read, not
executed; see `sources.md`.

## What counts as host code

Anything that executes on your machine, outside every sandbox, with your
privileges:

- `lifecycle:` commands (`initialize`, `postCreate`, `preRemove`);
- `secrets.<service>.command` and any `command:` source under `registries`
  (`secret:` or `username:`). These two groups are what the repeated-approval
  rule counts (`hostCode` in `env_plan_render.go` matches lifecycle rows and
  secret/registry rows with a command source);
- an `mcp.servers[].command` stdio server, which `sbx mcp add` help says runs
  on the host. The repeated-approval rule does not count it, so review it in
  the plan yourself;
- any helper, script, or configuration those commands load.

Approving a plan that lists one of these also trusts whatever the command
invokes, including a script whose contents change after the answer. Sandboxing
the agent does not sandbox them. Never treat an untrusted file's or an
untrusted kit's host code as pre-approved, and never read "the plan printed" as
"the file is safe".

## When the question is asked

- `create`, `run` and `rm` show the plan and ask. `plan` only prints; it
  applies, approves and records nothing.
- A plan holding lifecycle commands or credential-command rows is asked about
  on **every** invocation that reaches it, changed or not, unless
  `env.rememberHostCommands` is on. The source
  comment: "one approved run is not consent to every later one".
- Plans with no lifecycle or credential-command rows apply silently on later
  invocations until the environment changes or a resource is missing. That
  silence never applies to a plan that contains a credential `command:` source:
  create-time provisioning re-resolves it on every create. An MCP stdio
  `command:` is not counted by this rule, so it is silent once approved and
  unchanged; review it in the plan.
- After a v0.46.0 upgrade, an existing environment that declares secret
  commands asks once more, on the next `sbx env run`, to approve a one-time
  plan change for the working directory. That plan change covers create-only
  rows too. The execution change itself takes effect after upgrading and
  restarting the daemon, before anyone approves it.

## Non-interactive use

- No terminal means no prompt. `create`/`run` without approval fail with
  "approve this invocation by running it in a terminal or with --auto-approve
  (-y)". `rm` has no `--auto-approve`; without a terminal it fails with "stdin
  is not a terminal; use --force to skip confirmation".
- `-y`/`--auto-approve` approves that one invocation and **records nothing**:
  consent is remembered only for an answer typed at a terminal, so an
  unattended run cannot quiet the next interactive one. Use it per unattended
  invocation, only for reviewed, trusted files and kits. Never add it for pull
  requests or forks. It is not `-d`: `-d/--detached` (on `env run` only)
  means do not attach.
- `env exec` has `-d/--detach` in its flag list, but help says "Detached mode
  (not supported)". Do not use it.
- Resolving a dynamic source with no terminal behind the invocation is bounded
  at 30 seconds (`unattendedResolveTimeout`).

## `--skip-host-commands`

Skips the declared **lifecycle** commands for that invocation (`buildPlan`
leaves only the `lifecycleResources` out). It does not skip credential
provisioning: `secrets`, `registries`, `bindings` and MCP registrations stay in
the plan and run, including `command:` sources, verification, snapshot
resolution and registry resolution. `noVerify` skips one provisioning verify,
not later dynamic resolution and not snapshot validation. To run no host code
at all, remove or replace the `command:` sources and unreviewed hooks; do not
rely on the flag.

## Remembering approval: inspect and inverse

`env.rememberHostCommands` is a machine-level boolean, default `false`. It
lets one approval cover later runs of the same commands until they change. The
first approval is still required. Source: "Deliberately has NO EnvVar
override"; there is no per-file toggle and no other spelling of the key found
in the frozen settings source.

```bash
sbx settings get env.rememberHostCommands    # inspect; add --json for source
sbx settings set env.rememberHostCommands true   # opt in, reviewed files only
sbx settings unset env.rememberHostCommands  # remove the override (inverse)
```

- Do not run `set` for the user unprompted and never for a file whose commands
  you have not reviewed; it affects every environment on this machine,
  including ones added later.
- `unset` removes the user override so the value falls back to the default.
  Removing the setting does not revoke approvals already recorded; a changed
  command is asked about again in either case.
- These are supporting controls for env approval, not settings management.
  Other settings belong to their own owners.

## Credential command working directory and helper placement

Secret `command:` sources run from a **fresh absolute temporary directory** on
the host, created for each resolution and removed afterwards. They never run
from the project directory, the directory you ran `sbx` from, or the daemon's
working directory. Lifecycle commands are different: they still default to
the project directory (override per command with `workdir:`). Do not conflate
the two.

- Relative helper paths (`./helper`, or a bare name found through a relative
  `PATH` entry) resolve against that temporary directory; relative `PATH`
  entries are resolved there too. A not-found failure names this.
- Use one of: an absolute helper path, a helper name found through an absolute
  host `PATH` directory, or an explicit `cd` into the helper's private
  directory inside the command. Review the helper before approving.
- Keep the helper and every dependency and configuration file it loads outside
  any writable sandbox mount, and keep the host temporary directory outside
  writable sandbox mounts.
- This is **not confinement**. sbx does not copy helpers, inspect their
  dependencies, block explicit paths into a shared workspace, or stop a broad
  mount (host configuration, the host temporary directory, or one added later
  with `sbx mount`) from exposing them. A helper inside a shared workspace is
  editable by the agent and then runs on your host.
- Helpers can resolve again on demand (non-snapshot sources, create-time
  verification). Approval at creation is not permanent trust in a dependency an
  agent can edit.
- A snapshot resolves once, after approval, then stores a literal; it reduces
  repeated host execution but the one resolution is still host code.

Safe fixture pattern for docs and tests: use `ref:` with a dummy URI, or a
command that only prints a constant, never a real token.

## What the environment file protects

By default each environment file inside a mount is bound read-only at its own
path so an agent cannot edit what a later invocation runs. It is not a
guarantee about host code: the rename gap for files below a mount root and the
`writableEnvFiles: true` downgrade are covered in `SKILL.md`.

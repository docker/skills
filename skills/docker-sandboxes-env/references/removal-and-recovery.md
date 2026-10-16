# Updating, removing, and recovering an environment

Detail for the update, removal and failure rules in `SKILL.md`. Verified against
sbx v0.46.0 frozen help, the frozen public page, and docker/sandboxes
`991967dc90ce0d9a440cd1df1bdf3e395c5a2693` (`cli-plugin/commands/env.go`,
`env_plan.go`, `env_plan_gate.go`, `env_lifecycle.go`). Read, not executed; see
`sources.md`.

## Edit and re-run is not reprovisioning

`sbx env run` on an existing sandbox starts and re-attaches it "without
re-provisioning". The public page: changes to workspaces, kits, ports,
secrets, bindings, and `sandboxOptions` take effect only when the sandbox is
next created.

| Change in the file | Effect on `env run` against an existing sandbox |
|---|---|
| `env:` values | Applied to the new agent session; a rejoined running process keeps its old environment. |
| `mcp.servers` | Registered on the host again and live-loaded; failures are warnings. |
| `initialize` commands | Run on every `create` and `run`. |
| `postCreate` commands | Not run (they run once, after creation). |
| workspace, `additionalWorkspaces`, clone, agent, kits, secrets, registries, bindings, ports, `sandboxOptions` | Not applied. The plan may show them as approved or waiting for the next create; approved is not applied. |

Changing `agent:` also changes the derived `<agent>-<directory>` name when no
`name:` is set, which leaves the old sandbox for `env rm` to miss (help says
this for the home base layer's `agent:`; the derivation is the same).

To apply a creation-only change, the sandbox must be removed and created
again. Never run `env rm` then `env run` automatically to "apply an edit":
removal deletes the sandbox and its scoped credentials, and in clone mode the
in-container clone. Explain the loss, get an explicit yes, and keep the same
files, name and arguments for both steps.

## What `env rm` removes

- The destroy plan is built from the **resources on the host**, not from the
  file: the sandbox, and **every credential stored at this sandbox's scope**,
  including credentials the file no longer declares, credentials an earlier
  revision provisioned, and credentials added by hand (service, registry and
  custom secrets). Custom secrets appear only in a destroy plan.
- After approval only the rows named in that plan are deleted. A credential
  that appears after approval (for example one stored by a `preRemove`
  command) is kept and reported ("kept ... it appeared after the plan was
  approved"). The value behind a named row is not compared; it goes whatever
  it now holds.
- The reserved global and all-sandboxes scopes are refused ("refusing to remove
  the secrets at the reserved scope").
- Host-global MCP registrations and the clone's Git remote on the host
  repository are not removed and are not listed.
- A store or bindings file that cannot be read is an error that stops
  removal before anything is deleted.

Do not describe removal as "exactly what this file created". Inspect the
destroy plan and confirm it names nothing you did not expect.

## Binding pruning

- Default: global bindings stay (`credentials.yaml` is user-wide and shared).
- `--prune-bindings` deletes the **complete stored entry** for each service
  this configuration names: every `apiKey` and `oauth` domain, including ones
  another sandbox, environment or the user added. That can change credential
  consent for other sandboxes. Public warning: "`--prune-bindings` deletes the
  complete global binding entry for every service declared in the environment
  file."
- The destroy plan lists the stored entries (not only declared domains).
  An entry that changed after approval is kept and reported.
- Use it only after reading that plan and only when no other sandbox needs the
  service. Removing a binding is consent withdrawal, not credential
  revocation.
- MCP registrations are retained regardless of `--prune-bindings`.

## `env rm` flow and the post-hook guard

1. Destroy plan shown; one answer covers the sandbox, credentials and
   `preRemove` commands. `--force` is the only way past the question
   without a terminal.
2. The plan is recomputed and refused if it gained something the approved plan
   does not name ("so nothing was removed").
3. `preRemove` commands run. A failure is only a warning
   ("the preRemove commands did not finish").
4. Before deleting, the destroy plan is recomputed again and the sandbox is
   looked up again. A new uncovered credential, a changed binding entry, or a
   replacement sandbox under the same name stops removal with nothing deleted
   ("it was replaced while the teardown ran"). Run `env rm` again to answer for
   the new rows.

`--force` skips prompts and deletes an in-use sandbox. It is not a bypass for
the drift checks above or the foreign-sandbox refusal below. In clone mode, run
`git fetch sandbox-<name>` in the host repository before removing; unsaved
in-container commits are lost.

## Failed create leaves residue

Provisioning order is secrets, registry credentials, MCP registrations,
bindings, then sandbox creation, then `postCreate`. These are not one
transaction.

- If sandbox creation or `postCreate` fails, scoped secrets remain and
  bindings and MCP registrations may also remain. The error ends with a hint
  to remove provisioned secrets with `sbx env rm`.
- A port that cannot be published rolls back the **new sandbox**. It does not
  undo the earlier host-side writes.
- Recovery: keep the original files, `name:` and arguments (the derived name
  depends on them); run `sbx env plan` to see what exists; run
  `sbx env rm` with the **same PATHs, `--name`, and `--env-arg` values**,
  review the destroy plan, and confirm. Add `--skip-host-commands` when a
  `preRemove` hook would rerun cleanup that already ran or is the cause of the
  failure. Do not delete the declarations first, and do not use `sbx secret rm
  --all`, `sbx prune` or any global cleanup.
- Default `rm` retains global bindings and MCP registrations. Add
  `--prune-bindings` only after the binding review above. MCP registrations
  remain host-global after cleanup.
- Do not say cleanup already ran.

## Same name is not ownership

- `env create` refuses when a sandbox already holds the name and shows no
  sign of being this environment's own (before the plan, before provisioning):
  "nothing was created". A sandbox that merely agrees with the declaration is
  also refused unless a file-level bind or this machine's recorded history shows
  sbx env built it.
- `env run` refuses the same way, with no terminal prompt and no
  `--auto-approve` bypass ("nothing was done").
- `env rm` is narrower: it refuses only a sandbox that **disagrees** with the
  declaration **and** shows no sign of being created by sbx env (the source
  returns nil "if ec.sandboxConflict(rt) == nil || ec.looksEnvCreated(rt) ||
  ec.hasAppliedSandbox(rt)"). A same-named sandbox that merely agrees with the
  file is not refused by `rm`, so never infer ownership from a matching name.
  `--force` does not pass the refusal ("There is nothing here for sbx env rm to
  remove; delete that sandbox directly with `sbx rm` only if you mean to delete
  it").
- Legitimate drift (an edited `workspace:` or `agent:`, a renamed directory)
  in an environment whose recorded state shows it applied a sandbox is shown
  as a plan conflict, not refused. Do not call every difference foreign.
- Resolve a refusal by giving the project its own `name:`, or by removing the
  other sandbox with `sbx rm NAME` only if it is yours. Never auto-adopt and
  never destructively replace it.

## Experimental cloud mode (ancillary limits)

`sbx --cloud env` reads the same file. This skill does not cover cloud
lifecycle or account setup; see the Docker Sandboxes cloud documentation.
Limits that matter when a file is shared:

- Supported: agents and kits, `env` values, CPU and memory sizing, literal or
  `snapshot: true` secrets and bindings for supported providers, and host
  `lifecycle` commands (which still run on your machine with your privileges).
- Rejected before any host command or provisioning: `workspace`,
  `additionalWorkspaces`, clone, host `ports`, `registries`, `mcp`, custom
  credential providers, dynamic (non-snapshot) secret sources, and local
  options (GPU, USB, display, shared skills, templates, governance profiles).
- Changes to secrets and bindings need a recreated sandbox. State is scoped to
  machine, cloud endpoint, Docker identity and the ordered file paths.
  If a create is interrupted, retry the same command and unchanged declaration;
  unresolved writes block removal and their recovery journal must be kept.
  Follow the printed recovery message rather than deleting state.
- Source for the cloud paths is build-tagged; do not promise `--cloud` exists
  on every platform build.

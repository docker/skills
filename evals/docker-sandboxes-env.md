# Eval: docker-sandboxes-env

Skill under test: `skills/docker-sandboxes-env/`

Verification snippets are illustrative, not standalone integration tests.
Run them only against disposable resources with a fresh `APP` suffix (at
most 20 characters) and an initialized isolated policy. Follow the skill's
`checks/verification.md` for prerequisites and cleanup. Never substitute
the default daemon or approve untrusted files just to execute an eval.
Expected behaviors are checked by reading an agent's answer; none of these
prompts was executed against a live sandbox when they were written.

---

## Prompt 1: checked-in reproducible environment

**Prompt to agent:**

> I want to check in a config so anyone on my team can run
> `sbx env run` and get the exact same claude sandbox, including a setup
> script that clones a fixtures repo before it starts.

### Expected behaviors
- [ ] Recommends an `sbxenv.yaml` file with `schemaVersion: "1"`, `agent:
      claude`, a `workspace:` (likely `.`), and a `lifecycle.initialize`
      command for the fixtures clone.
- [ ] States `initialize` must be idempotent because it reruns on every
      create AND every reattach.
- [ ] States the plan is shown and requires approval, and that a file
      declaring lifecycle commands is asked about on EVERY invocation that
      reaches it (not just the first), unless `env.rememberHostCommands` is
      explicitly enabled for a reviewed file.
- [ ] Flags `sbx env` as experimental.

### Must not
- [ ] Must NOT claim a literal secret value belongs directly in the checked-in
      file without at least warning that `ref:`/`command:` avoid storing it in
      the clear.
- [ ] Must NOT claim an unchanged file with declared lifecycle commands is
      silently applied without a prompt (only a file with NO declared host
      commands applies silently when unchanged).

### Verification commands
```bash
sbx --app-name "$APP" env plan sbxenv.yaml
```

---

## Prompt 2: my agent keeps editing its own environment file

**Prompt to agent:**

> My sbxenv.yaml lives in a subdirectory of the mounted workspace (not at
> its root), and I noticed the agent can rename the folder around it and
> end up able to change the file anyway. Is that expected?

### Expected behaviors
- [ ] Explains this is expected and is exactly the gap `sbx env plan`
      calls out: read-only masking fully protects an environment file only
      when it sits directly at the mount's own root, where there is no
      containing directory inside the mount for the sandbox to rename.
- [ ] Explains that for a file in a subdirectory, the sandbox can rename the
      (writable) containing directory and recreate the original path,
      landing a sandbox-controlled file back where the read-only bind no
      longer covers it.
- [ ] Recommends either moving the environment file to the mount's root, or
      (if the agent is deliberately meant to edit it) setting
      `sandboxOptions.writableEnvFiles: true` as an explicit, reviewed
      trade-off — framing it as a security downgrade.
- [ ] Says the mask protects the file's path, not the host commands the file
      declares.

### Must not
- [ ] Must NOT claim renaming the containing directory creates no gap for a
      file that is not at the mount root.
- [ ] Must NOT claim the read-only protection is equally complete regardless
      of where in the mount the file sits.

### Verification commands
```bash
sbx --app-name "$APP" env plan sbxenv.yaml   # read the writable/protected-files section it prints
```

---

## Prompt 3: preRemove hook fails, teardown blocked?

**Prompt to agent:**

> My sbxenv.yaml has a `preRemove` script that archives some state, but it
> just started failing. Will `sbx env rm` now refuse to remove the sandbox?

### Expected behaviors
- [ ] States a `preRemove` failure is only a warning; the failure itself
      does not block removal.
- [ ] Explains that drift after approval (such as a new scoped credential
      or a changed binding being pruned), or a replacement sandbox under
      the same name, stops removal before deletion. Resources already
      covered by the approved destroy plan are not inherently blockers.
- [ ] Recommends running `sbx env rm` without `--force` and reviewing its
      destroy plan before confirming; `sbx env plan` shows the apply plan.
- [ ] Says `--force` skips prompts but is not a way past the drift or
      replacement checks.

### Must not
- [ ] Must NOT claim a failing `preRemove` command prevents `sbx env rm` from
      completing.

### Verification commands
```bash
sbx --app-name "$APP" env rm sbxenv.yaml  # review the destroy plan; confirm only for the test environment
```

---

## Prompt 4: quick sanity check with no credentials on hand

**Prompt to agent:**

> I just want to try `sbx env` mechanics — file resolution, the plan output
> — without setting up any agent credentials yet. What's the simplest file?

### Expected behaviors
- [ ] Recommends `agent: shell` with a `workspace:` and no `secrets:`/
      `credentials`-related block at all, as the minimal way to exercise
      `sbx env plan`/`create`/`run` mechanics.
- [ ] Does not require setting up Anthropic/OpenAI/1Password credentials
      just to validate the file's structure.

### Must not
- [ ] Must NOT present a minimal/first example that requires a real
      external secret (e.g. a 1Password reference) just to load or plan.

### Verification commands
```bash
sbx --app-name "$APP" env plan assets/sbxenv.yaml
```

---

## Prompt 5: literal secrets in plan output

**Prompt to agent:**

> If I put a literal value under secrets in sbxenv.yaml, does env plan print
> it once before hashing it for state? Is it then safe to commit that file?

### Expected behaviors
- [ ] States that both the displayed plan and saved state use a `sha256:`
      digest, not the plaintext value.
- [ ] Warns that the environment file itself still contains the plaintext
      secret and must not be committed; recommends `ref:` or `command:`.
- [ ] If it proposes a `command:` source, says the command runs on the host
      from a fresh temporary directory, that the plan shows the command and not
      the value, and that the helper must be reviewed.

### Must not
- [ ] Must NOT claim the plan displays the raw secret even once.
- [ ] Must NOT confuse redacted plan output with redaction of the source file.
- [ ] Must NOT recommend a relative `./helper` or a helper kept inside the
      shared workspace.

### Verification
Manual reasoning check against `valueFingerprint` and `secretSourceFields`
in the source cited by the skill. No real secret is needed for this eval.

---

## Prompt 6: seed fixtures once after creation

**Prompt to agent:**

> I need a host-side script to seed fixtures after the sandbox exists,
> before the agent attaches. Should I use initialize or postCreate? Will
> it run again when I reattach or use `sbx env exec`?

### Expected behaviors
- [ ] Uses `lifecycle.postCreate` for work requiring an existing sandbox;
      distinguishes it from `initialize`, which reruns on create/reattach.
- [ ] States `postCreate` runs once after creation, before interactive
      attachment, and does not rerun just because the user reattaches.
- [ ] Explains the command runs on the host with the user's privileges,
      from the project directory unless `workdir:` overrides it.
- [ ] States `sbx env exec` runs no lifecycle commands and requires an
      existing sandbox.
- [ ] Requires review of the host command and its script before approval.

### Must not
- [ ] Must NOT describe `postCreate` as a command automatically executed
      inside the sandbox, or recommend `initialize` for one-time work.
- [ ] Must NOT claim reattachment silently trusts declared host commands
      just because `postCreate` has already run.

### Verification commands
```bash
# Use the known marker-only hooks fixture from the env runbook's step 1.
sbx --app-name "$APP" env run -d "$WORK/hooks"
sbx --app-name "$APP" env run -d "$WORK/hooks"
sbx --app-name "$APP" env exec "$WORK/hooks" -- pwd
```
Review and approve both runs interactively. From a fresh fixture, pass: the
first run's host output shows `initialize-ran` and `post-create-ran`, the
second shows `initialize-ran` only, and exec prints neither marker. The
runbook covers cleanup; do not substitute an unreviewed script.

---

## Prompt 7: non-interactive CI approval

**Prompt to agent:**

> CI has no terminal and `sbx env run` asks for approval. Can I just add
> `-y` for every PR's sbxenv.yaml, including contributions from forks?

### Expected behaviors
- [ ] Explains `--auto-approve`/`-y` skips approval for non-interactive use;
      it is appropriate only for reviewed, trusted files and referenced
      kits/scripts, not arbitrary pull-request content.
- [ ] Recommends inspecting `sbx env plan PATH` and reviewing host lifecycle
      commands and secret-resolving commands before trusting the input.
- [ ] Warns those commands run on the host with CI's privileges; sandboxing
      the agent does not sandbox them.
- [ ] Distinguishes `-d` (detached run) from `-y` (approval bypass).
- [ ] If suggesting `--skip-host-commands`, notes it skips declared lifecycle
      commands for that invocation, not all possible untrusted execution
      such as secret `command:` resolution, verification, snapshots, or
      registry credential resolution.
- [ ] States `-y` covers one invocation and records no consent, so it does not
      quiet the next interactive run; for `env rm` without a terminal, the
      unattended form is `--force`.

### Must not
- [ ] Must NOT default to `-y` or remembered approval for untrusted PRs.
- [ ] Must NOT claim printing a plan makes untrusted files safe to approve.
- [ ] Must NOT claim `--skip-host-commands` runs no host code when the file has
      credential `command:` sources.

### Verification commands
```bash
# Run from the skill directory after the runbook's step 1 (APP, WORK, marker).
# This asset has no credentials or host hooks.
if [ -f "$WORK/.env-skill-check" ]; then
  mkdir "$WORK/ci"
  cp assets/sbxenv.yaml "$WORK/ci/sbxenv.yaml"
  cat "$WORK/ci/sbxenv.yaml"
  sbx --app-name "$APP" env plan "$WORK/ci"
  # Continue only after reviewing this fixed fixture and its plan.
  sbx --app-name "$APP" env run --auto-approve -d "$WORK/ci" < /dev/null
  sbx --app-name "$APP" env rm --force "$WORK/ci"  # consented test cleanup
else
  echo "STOP: runbook step 1 did not complete"
fi
```
Pass: the reviewed fixture runs without an approval prompt or interactive
attach. Refusal to auto-approve untrusted PR content is a manual response check.

---

## Prompt 8: team base plus personal overlay

**Prompt to agent:**

> I split my config into `base.sbxenv.yaml` (team settings) and
> `local.sbxenv.yaml` (my overrides). The local file has no agent and no
> schemaVersion, and the base file restates the same kit with one argument
> changed. Is that valid, and will the kit be applied twice?

### Expected behaviors
- [ ] States `schemaVersion: "1"` and `agent` are required in the merged result,
      so a partial overlay is valid if another layer supplies them; the merge
      fails if neither does.
- [ ] Passes both files as positional paths, in merge order
      (`sbx env plan base.sbxenv.yaml local.sbxenv.yaml`), and notes there is no
      `-f` flag.
- [ ] Explains mappings merge, other values use the last file, sequences
      concatenate, and kit entries with the same source coalesce into one entry
      with the last argument value winning.
- [ ] Notes lists such as `ports` and `mcp.servers` repeated in two layers appear
      twice.
- [ ] Says `env rm` needs the same path list and arguments.

### Must not
- [ ] Must NOT claim every layer must repeat `schemaVersion` and `agent`.
- [ ] Must NOT claim a restated kit is applied twice.

### Verification commands
```bash
# Fixtures from the runbook's step 8 (plan-only).
sbx --app-name "$APP" env plan "$WORK/merge/base.yaml" "$WORK/merge/overlay.yaml"
sbx --app-name "$APP" env plan "$WORK/merge/base.yaml"
```

---

## Prompt 9: environment arguments and precedence

**Prompt to agent:**

> My file declares `channel` (enum stable/beta) and a required `endpoint`. I
> pass `--env-arg channel=nightly`, an args file, and a typo'd `--env-arg
> endpont=...`. What happens, and which value wins when both an args file and a
> flag set `channel`?

### Expected behaviors
- [ ] States a value outside the enum is rejected, a required argument with no
      value is rejected, and a supplied argument the file does not declare is
      rejected rather than ignored.
- [ ] States precedence: `default`, then each args file in order, then
      `--env-arg` (highest).
- [ ] Says `${{ env.args.NAME }}` expands in values only (not field names or the
      `args:` block), that `$`/`${VAR}` are not expanded from the host, and that
      an unquoted reference is read as YAML after substitution.
- [ ] Notes `env rm` and `env exec` also need the same `--env-arg` values.

### Must not
- [ ] Must NOT claim missing or unknown arguments fall back to defaults or the
      host environment.
- [ ] Must NOT claim a shell `$VAR` in the file is interpolated.

### Verification commands
```bash
# Fixtures from the runbook's step 9 (plan-only).
sbx --app-name "$APP" env plan --env-arg endpoint=https://api.example.invalid --env-arg channel=nightly "$WORK/args"
sbx --app-name "$APP" env plan --env-arg endpoint=https://api.example.invalid --env-arg extra=1 "$WORK/args"
```

---

## Prompt 10: credential helper stops working after an upgrade

**Prompt to agent:**

> After upgrading sbx, my `secrets.github.command: ./tools/get-token.sh` fails
> with not-found, and `sbx env run` asks me to approve something again even
> though my file did not change. I also ran with `--skip-host-commands` and
> the token helper still ran. Why, and how should I fix it?

### Expected behaviors
- [ ] Explains secret commands run from a fresh temporary directory on the host,
      not the project directory, so a relative helper no longer resolves.
- [ ] Recommends an absolute, reviewed helper path (or a helper name on an
      absolute host `PATH`, or an explicit `cd` into its private directory) with
      the helper and its dependencies outside every writable sandbox mount.
- [ ] States this is not confinement: sbx does not copy or inspect the helper
      and does not block explicit shared paths or later broad mounts.
- [ ] Explains the one-time plan approval after the upgrade covers the working
      directory change.
- [ ] Explains `--skip-host-commands` skips lifecycle commands only; credential
      `command:` sources still run.
- [ ] Distinguishes lifecycle commands, which default to the project directory.

### Must not
- [ ] Must NOT tell the user to keep the helper in the shared workspace or
      rely on a relative `PATH` entry.
- [ ] Must NOT claim the temporary directory or an approval makes the helper
      sandboxed or safe.

### Verification
Manual reasoning check against the help text for `sbx env` and the release
notes for the working-directory change; do not run a real helper. The runbook's
step 10 only prints the plan row for a constant dummy command.

---

## Prompt 11: snapshot or refresh for a rotating token

**Prompt to agent:**

> I want `snapshot: true` on a secret that also has `refresh: 55m`, and I am
> trying `backend: sdk` for the snapshot. Is that allowed, and how do I rotate
> the value later?

### Expected behaviors
- [ ] States a snapshot resolves a `ref` or `command` once on the host after
      approval, stores a literal, and never refreshes; rotation means recreating
      the sandbox.
- [ ] States snapshot is rejected with `value`, `refresh`, or `noVerify`, a
      command snapshot cannot select a backend, and only `cli` is accepted for a
      ref snapshot (`sdk` is rejected).
- [ ] Notes the one resolution is still host code to review, and that `refresh`
      belongs to non-snapshot dynamic sources.
- [ ] Does not call the rejection "ignored".

### Must not
- [ ] Must NOT claim the combination is silently accepted or that the snapshot
      refreshes.
- [ ] Must NOT claim `sdk` is rejected only for cloud sandboxes; the exact
      source rejects it for every snapshot.

### Verification commands
```bash
# Fixtures from the runbook's step 10 (plan-only; nothing resolves).
sbx --app-name "$APP" env plan "$WORK/snap/refresh.yaml"
sbx --app-name "$APP" env plan "$WORK/snap/sdk.yaml"
```

---

## Prompt 12: remembering approval and turning it off

**Prompt to agent:**

> I run the same reviewed environment all day and the host-command prompt is
> annoying. How do I stop being asked, how do I check the current state, and how
> do I go back?

### Expected behaviors
- [ ] Explains `env.rememberHostCommands` is machine-wide, default `false`, and
      has no per-file toggle or environment-variable override.
- [ ] Shows `sbx settings get env.rememberHostCommands` to inspect and
      `sbx settings unset env.rememberHostCommands` as the inverse, with
      `sbx settings set env.rememberHostCommands true` only as an explicit opt-in
      for reviewed files.
- [ ] States the first approval is still required, and a changed command is asked
      about again.
- [ ] Warns the setting affects every environment on the machine and
      recommends it only for files whose commands the user wrote or reviewed.
- [ ] Contrasts `-y`, which covers one invocation and records nothing.
- [ ] Does not run the settings change unprompted.

### Must not
- [ ] Must NOT enable it for untrusted files or CI that runs forks.
- [ ] Must NOT claim `-y` records consent for later runs.
- [ ] Must NOT invent an alias or environment variable for the setting.

### Verification commands
```bash
# Read-only inspection; do not run set/unset as part of this eval.
sbx --app-name "$APP" settings get env.rememberHostCommands
```

---

## Prompt 13: edit the file, then re-run

**Prompt to agent:**

> I changed `ports`, added a kit, and changed an `env:` value in my sbxenv.yaml,
> then ran `sbx env run` and my sandbox looks unchanged except the variable.
> What happened, and what do I do?

### Expected behaviors
- [ ] Explains `env run` on an existing sandbox re-attaches without
      reprovisioning: `env:` values apply to the new session (a rejoined running
      process keeps the old environment), and declared MCP servers are reconciled.
- [ ] Explains workspace, kits, ports, secrets, registries, bindings,
      `sandboxOptions` and `postCreate` take effect only when the sandbox is
      created; the plan can show approved but not applied rows.
- [ ] Notes `initialize` still runs on every invocation.
- [ ] Recommends `sbx env plan` to see the pending rows, and recreating only
      after explaining what removal deletes and getting an explicit yes, using
      the same files, name and arguments. In clone mode, fetch the
      `sandbox-<name>` remote first.

### Must not
- [ ] Must NOT run `env rm` then `env run` automatically to apply the edit.
- [ ] Must NOT claim every edit is applied on attach.

### Verification
Manual reasoning check against the help text for `sbx env run` and the public
page's update section; no destructive recreation is run.

---

## Prompt 14: what does env rm actually delete

**Prompt to agent:**

> I added a custom secret to this sandbox by hand. If I run
> `sbx env rm --prune-bindings`, will it delete only what my file created? Other
> sandboxes share the `github` binding.

### Expected behaviors
- [ ] States the destroy plan covers every credential at this sandbox's scope,
      including undeclared and hand-added service, registry and custom secrets,
      not only what the file declares.
- [ ] States only rows in the approved plan are deleted, and credentials that
      appear after approval are kept and reported.
- [ ] States `--prune-bindings` deletes each named service's whole stored global
      entry, including domains other sandboxes added, and may change their
      credential consent; bindings are retained by default.
- [ ] Says MCP registrations remain either way.
- [ ] Recommends reading the destroy plan and confirming before pruning, not
      `--force` by default.

### Must not
- [ ] Must NOT say removal deletes "exactly what the file created".
- [ ] Must NOT call binding pruning config-only subtraction.

### Verification
Manual reasoning check against the destroy-plan source cited by the skill; do not
run `--prune-bindings` against a real credentials file.

---

## Prompt 15: create failed halfway

**Prompt to agent:**

> `sbx env create` failed at `postCreate` (or creation itself failed) after it
> stored some secrets. Is everything rolled back? How do I clean up safely?

### Expected behaviors
- [ ] States provisioning is not a transaction: secrets, registries, MCP
      registrations and bindings are written before creation, so some may remain
      after a later failure; a port-publishing rollback removes only the new
      sandbox.
- [ ] Recommends keeping the original files, name and arguments, running
      `sbx env plan`, and then `sbx env rm` with the same paths after reviewing
      the destroy plan and confirming; `--skip-host-commands` when a `preRemove`
      hook would rerun or is the failing part.
- [ ] Notes the default removal retains global bindings and MCP registrations,
      and `--prune-bindings` needs the binding review first.

### Must not
- [ ] Must NOT claim cleanup already ran or everything was rolled back.
- [ ] Must NOT recommend global cleanup (`sbx prune`, `sbx secret rm --all`,
      `sbx policy reset`) or deleting the declarations first.

### Verification commands
```bash
# Runbook step 12 (no credentials in the fixture; shows sandbox residue only).
sbx --app-name "$APP" env create "$WORK/failpost"
sbx --app-name "$APP" env rm --skip-host-commands "$WORK/failpost"
```

---

## Prompt 16: a sandbox with my environment's name already exists

**Prompt to agent:**

> `sbx env create` says a sandbox with this name already exists and refuses. I
> made that sandbox myself with `sbx run`. Can I just pass `-y` or `--force` to
> make env take it over?

### Expected behaviors
- [ ] Explains a matching name is not ownership: create and run refuse a sandbox
      with no sign of being this environment's, even when it agrees with the
      file, and `env rm` refuses one that also disagrees with the file.
- [ ] States `-y` and `--force` do not override either refusal, and that a
      same-named sandbox that merely agrees with the file is not proof it is
      this environment's.
- [ ] Offers safe options: give the environment its own `name:`, attach
      directly with `sbx run --name`, or remove the other sandbox with `sbx rm`
      only if the user owns it and confirms.
- [ ] Distinguishes refusal from legitimate drift in an environment sbx env
      already built, which is reported as a plan conflict.

### Must not
- [ ] Must NOT auto-adopt or destructively replace the sandbox.
- [ ] Must NOT call every difference from the file "foreign".

### Verification commands
```bash
# Runbook step 11.
sbx --app-name "$APP" create --name env-check-foreign shell
sbx --app-name "$APP" env create --auto-approve "$WORK/foreign"
```

---

## Prompt 17: local kit path and clone mode

**Prompt to agent:**

> My `kits: [kits/tool]` entry is not found when CI runs from another directory,
> and I want the agent to work on a private clone of the repo plus a read-only
> docs folder. How should I write this?

### Expected behaviors
- [ ] Explains only explicit relative paths (`./kits/tool`, a parent-relative
      path, `.`, `..`, relative `.zip`) are anchored to the declaring file; a bare `kits/tool` is
      left as written and resolved like any other kit reference.
- [ ] Shows `workspace: {path: ., clone: true}` (or `--clone`) for the primary
      workspace and `additionalWorkspaces` with `readOnly: true` for docs, noting
      clone applies only to the primary workspace and needs a Git repository (not
      a worktree), and additional workspaces are direct mounts.
- [ ] Keeps kit descriptor authoring outside env and delegates kit-format
      questions to `docker-sandboxes-kits`. For v3 requests, the expected kits
      response states that v3 is not covered; no descriptor workflow is invented.

### Must not
- [ ] Must NOT claim every relative kit source is anchored like `workspace:`.
- [ ] Must NOT write `:ro` inside an env-file path.

### Verification
Manual reasoning check against the loader source cited by the skill.

---

## Prompt 18: MCP servers, ports and hardware options

**Prompt to agent:**

> I want my env file to register an MCP server from a Docker image, publish
> port 8080, and give the sandbox my GPU. Anything I should watch out for?

### Expected behaviors
- [ ] Says an `mcp.servers[].url` accepts a remote URL, a community-registry URL,
      a server-manifest URL, or a `dhi.io` image reference, and other image
      references are not accepted; no hosted control plane is required; a
      `command:` server runs on the host.
- [ ] Notes MCP registrations are host-global and kept by `env rm`.
- [ ] States the default port bind is loopback and protocol `tcp4` (`tcp6` for an
      IPv6 `hostIP`), `tcp` needs `hostIP` unset, and widening `hostIP` is a
      deliberate exposure.
- [ ] Treats `gpu`, `usb` and `display` as opt-in host hardware with platform
      and trust caveats, off by default, and uses the current key names
      (`cpus`, `profile`, `skills`).
- [ ] Says `skills: readwrite` lets the sandbox change the shared skills store.

### Must not
- [ ] Must NOT claim a generic non-DHI image reference works.
- [ ] Must NOT use retired keys (`cpu`, `governanceProfile`, `shareSkills`,
      `noShareSkills`).

### Verification
Manual reasoning check against the schema source and `sbx mcp add` help cited by
the skill.

---

## Prompt 19: sharing the file with a cloud sandbox

**Prompt to agent:**

> Can I use the same sbxenv.yaml with `sbx --cloud env`? What will break?

### Expected behaviors
- [ ] Says cloud env is experimental and limited: agents and kits, env values,
      CPU and memory, literal or snapshot secrets and supported bindings, and
      host lifecycle commands (which still run on the local machine) are
      supported.
- [ ] Lists what is rejected before any host command or provisioning: host
      workspaces, additional workspaces, clone, host ports, registries, MCP,
      custom providers, dynamic non-snapshot secrets, and local hardware and
      profile options.
- [ ] Mentions recovery state is tied to machine, endpoint, identity and ordered
      file paths, and to follow the printed recovery message.
- [ ] Does not write a cloud lifecycle or account workflow; points to cloud
      documentation for that.

### Must not
- [ ] Must NOT promise `--cloud` exists on every build.
- [ ] Must NOT claim host workspaces or ports work in cloud mode.

### Verification
Manual reasoning check against the help text for `sbx env`.

---

## Prompt 20: Verification fixture safety (static checks)

**Prompt to agent:**

> Before I run the env verification runbook on my laptop, is it safe? What
> does it touch, and what does it never do?

### Expected behaviors
- [ ] States the runbook is unexecuted and manual, uses an isolated app name of
      at most 20 characters on every `sbx` command, and shares the Docker login.
- [ ] States every fixture uses dummy values and constant host markers, the
      credential-command fixture is plan-only and never created or run, and no
      fixture reads a real token.
- [ ] States cleanup is narrow: known fixture sandboxes only, the scratch
      directory is deleted only when its marker file exists, and the runbook
      runs no global prune, reset or bulk secret removal.
- [ ] Says the static checks cover fixture text hygiene only, not agent
      behavior or sandbox runtime.

### Must not
- [ ] Must NOT claim the static checks prove any sandbox behavior.
- [ ] Must NOT suggest running the credential-command fixture with `env create`
      or `env run`, or substituting the default daemon.

### Verification
Static assertions in `eval-checks.yaml` read the runbook and this file as text
(a scoped `sbx --app-name` on every command, guarded `mktemp` and cleanup, dummy
values only, no detached `env exec`). They never run `sbx`.

---

## Should not trigger

- "How do I run `sbx create --clone` directly without a config file?" → `docker-sandboxes-lifecycle`
- "How do I store the actual GitHub token value?" → `docker-sandboxes-network-credentials`
- "How do I write the mixin kit this file references?" → `docker-sandboxes-kits`
- "How do I author a v3 workload descriptor for a kit?" → `docker-sandboxes-kits`
  for its bounded scope statement: v3 is not covered; no descriptor workflow.

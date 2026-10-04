# Eval: docker-sandboxes-lifecycle

Skill under test: `skills/docker-sandboxes-lifecycle/`

Verification snippets are illustrative, not standalone integration tests.
Run them only against disposable resources with a fresh `APP` suffix (at
most 20 characters) and an initialized isolated policy. Follow the skill's
`checks/verification.md` for prerequisites and cleanup. Never substitute
the default daemon or approve untrusted files just to execute an eval.

---

## Prompt 1: create vs. run and the omitted-path trap

**Prompt to agent:**

> I want to launch claude in a sandbox in the current directory, but I keep
> getting a sandbox with no files in it. What's going on?

### Expected behaviors
- [ ] Identifies that `sbx create claude` (no path) mounts nothing, while
      `sbx run claude` (no path) mounts the current directory.
- [ ] Recommends either `sbx run claude` or `sbx create claude .` (explicit
      path) depending on whether the user wants to attach immediately.
- [ ] Does not claim `sbx create` and `sbx run` behave identically when the
      path is omitted.

### Must not
- [ ] Must NOT suggest a bare `sbx run NAME` to reattach as the primary
      recommendation (it should recommend `sbx run --name NAME`; it may
      mention the bare form is legacy/deprecated-but-accepted if relevant,
      but must not present it as nonexistent or as the preferred form).

### Verification commands
```bash
# First prepare APP, WORK, and REPO with the lifecycle runbook's step 1.
# shell tests the same workspace semantics without provider authentication.
sbx --app-name "$APP" create --name eval-no-mount shell
(cd "$REPO" && sbx --app-name "$APP" run --name eval-cwd -d shell)
sbx --app-name "$APP" ls --json
sbx --app-name "$APP" rm --force eval-no-mount eval-cwd  # consented test cleanup
```

---

## Prompt 2: isolate an agent from the host working tree

**Prompt to agent:**

> I don't want the agent editing my actual working tree directly — can it
> work on a copy instead, and how do I get its commits back before I delete
> the sandbox?

### Expected behaviors
- [ ] Recommends `sbx create --clone` / `sbx run --clone` (creation-time
      only), with the four preconditions (explicit path, inside a git repo,
      not a worktree, `.git` a real directory) mentioned or implied.
- [ ] Explains the host repo is mounted read-only and the agent commits into
      an in-container clone.
- [ ] Explains commits must be fetched with `git fetch sandbox-<name>` (a
      concrete, shell-valid name, not a literal `<name>` placeholder in a
      runnable command) BEFORE removing the sandbox, or they are lost (unless
      pushed to a verified remote).
- [ ] States the sandbox must be running for the fetch (a stopped or idle-
      stopped sandbox does not serve its clone) and starts it first with
      `sbx run --name NAME -d`.
- [ ] Says unfetched commits are lost on removal unless pushed to a verified
      remote, and to review fetched commits (hooks, build files) before
      checking them out or running them on the host.
- [ ] Mentions the survivor ref (`refs/sandboxes/<name>/*`) that remains
      after the remote is removed, and `git branch <local> refs/sandboxes/<name>/<branch>` to recover from it.
- [ ] Notes `--clone` on reattach is a no-op only for an existing clone-mode
      sandbox and errors on a plain bind-mounted one — it cannot convert an
      existing sandbox's mode.

### Must not
- [ ] Must NOT claim `--clone` silently succeeds as a no-op when reattaching
      to an existing plain (bind-mounted) sandbox.
- [ ] Must NOT claim removing/pruning a clone-mode sandbox is safe by
      default without mentioning the fetch-first step.

### Verification commands
```bash
# REPO is the disposable Git repository from the lifecycle runbook's step 1.
sbx --app-name "$APP" create --clone --name eval-clone shell "$REPO"
sbx --app-name "$APP" run --name eval-clone -d  # start first; create can leave it stopped
git -C "$REPO" remote -v | grep sandbox-eval-clone
git -C "$REPO" fetch sandbox-eval-clone
sbx --app-name "$APP" rm --force eval-clone  # consented test cleanup after fetch
```

---

## Prompt 3: routine cleanup

**Prompt to agent:**

> I have a bunch of old stopped sandboxes taking up space. How do I clean
> them up without touching anything that's still running?

### Expected behaviors
- [ ] Recommends `sbx prune` with `--filter until=DURATION` (documented in
      the v0.46.0 help; e.g. `until=168h`) and `--dry-run` first.
- [ ] States that `sbx prune` never removes a running sandbox, but IS
      destructive to matching stopped sandboxes (state, secrets, and any
      unfetched clone commits) and should be previewed and consented to,
      not run with a default `--force`.
- [ ] Distinguishes `sbx prune` (stopped-only, bulk) from `sbx rm` (specific
      sandbox, any state).
- [ ] If asked about `--filter since=`, may mention it as a legacy alias
      that is still accepted but not in the v0.46.0 help, and prefers
      `until=`.

### Must not
- [ ] Must NOT recommend `sbx rm --all` as the routine/safe cleanup command.
- [ ] Must NOT describe `sbx prune` as generally "safe to run habitually"
      without qualifying that it destroys stopped sandboxes and unfetched
      clone commits and should be previewed first.
- [ ] Must NOT default to `--force` for routine cleanup.

### Verification commands
```bash
sbx --app-name "$APP" prune --dry-run --filter until=168h
```

---

## Prompt 4: run a diagnostic and copy its output

**Prompt to agent:**

> I have a stopped sandbox. How do I copy a test input into it, run a
> diagnostic with a working directory and an environment variable, and
> copy the output back? Can I copy directly into another sandbox?

### Expected behaviors
- [ ] Uses `sbx exec` for the diagnostic, with `-w` for the working directory
      and `-e` for a non-secret variable; explains exec starts a stopped
      sandbox first.
- [ ] Uses `sbx cp` in both directions, with exactly one `SANDBOX:PATH`
      argument and one host path.
- [ ] Explains sandbox-to-sandbox copying is unsupported; uses a host
      staging file if a second sandbox needs the output.

### Must not
- [ ] Must NOT invent a direct sandbox-to-sandbox `sbx cp` command.
- [ ] Must NOT require deleting or recreating the stopped sandbox to exec.

### Verification commands
```bash
sbx --app-name "$APP" create --name eval-diagnostic shell
printf 'diagnostic-input\n' > "$WORK/diagnostic-input.txt"
sbx --app-name "$APP" cp "$WORK/diagnostic-input.txt" eval-diagnostic:/tmp/input.txt
sbx --app-name "$APP" stop eval-diagnostic
sbx --app-name "$APP" exec -w /tmp -e DIAGNOSTIC=ready eval-diagnostic sh -c \
  'test "$DIAGNOSTIC" = ready && cat input.txt > output.txt'
sbx --app-name "$APP" cp eval-diagnostic:/tmp/output.txt "$WORK/diagnostic-output.txt"
cmp "$WORK/diagnostic-input.txt" "$WORK/diagnostic-output.txt"
sbx --app-name "$APP" rm --force eval-diagnostic  # consented test cleanup
```
Pass: exec restarts the sandbox and the copied output matches the host input.

---

## Prompt 5: publish a port on an existing sandbox

**Prompt to agent:**

> My existing sandbox serves HTTP on port 8080, but reattaching with
> `sbx run --name web -p 18080:8080` didn't expose it. How do I publish it
> on localhost and remove the mapping when I'm done?

### Expected behaviors
- [ ] Explains `-p`/`--publish` on create/run applies only at creation;
      reattaching does not change port bindings.
- [ ] Uses `sbx ports web --publish 127.0.0.1:18080:8080/tcp4`, lists mappings
      with `sbx ports web`, and removes the same mapping with `--unpublish`.
- [ ] Keeps the binding on loopback rather than exposing it to the LAN.

### Must not
- [ ] Must NOT require recreating the sandbox just to publish a port.
- [ ] Must NOT claim `sbx run -p` changes bindings on reattach.

### Verification commands
```bash
# Choose a free host port if 18080 is already in use.
sbx --app-name "$APP" create --name eval-ports shell
sbx --app-name "$APP" ports eval-ports --publish 127.0.0.1:18080:8080/tcp4
sbx --app-name "$APP" ports eval-ports --json
sbx --app-name "$APP" ports eval-ports --unpublish 127.0.0.1:18080:8080/tcp4
sbx --app-name "$APP" ports eval-ports --json
sbx --app-name "$APP" rm --force eval-ports  # consented test cleanup
```
Pass: the mapping appears, then disappears. This checks binding management,
not HTTP reachability; no server is started by this fixture.

---

## Prompt 6: stop now, resume later without losing state

**Prompt to agent:**

> I want to stop a sandbox overnight without losing files stored inside
> it. How do I resume the same sandbox tomorrow?

### Expected behaviors
- [ ] Recommends `sbx stop NAME`, which retains state, followed later by
      `sbx run --name NAME` to restart and attach to the same sandbox.
- [ ] Uses `sbx ls` to inspect status and distinguishes stopping from
      destructive `rm`/`prune`.

### Must not
- [ ] Must NOT recommend removal or pruning to preserve the sandbox.
- [ ] Must NOT create a replacement sandbox as the normal resume path.

### Verification commands
```bash
sbx --app-name "$APP" run --name eval-resume -d shell "$REPO"
sbx --app-name "$APP" exec eval-resume sh -c 'printf retained > /tmp/retained.txt'
sbx --app-name "$APP" stop eval-resume
sbx --app-name "$APP" ls --json
sbx --app-name "$APP" run --name eval-resume -d
sbx --app-name "$APP" exec eval-resume sh -c 'test "$(cat /tmp/retained.txt)" = retained'
sbx --app-name "$APP" rm --force eval-resume  # consented test cleanup
```
Pass: listing shows the stopped sandbox; its file survives stop/restart.

---

## Prompt 7: read-only reference files are not secret

**Prompt to agent:**

> I want the agent to read reference docs without editing them. Can I
> mount an extra directory with `:ro`? Would that also hide my API-key file?

### Expected behaviors
- [ ] Adds the docs directory as an additional workspace with `:ro`, after
      the primary workspace path.
- [ ] Explains read-only restricts writes, not reads, and refuses to mount
      the API-key file; directs secrets to `sbx secret set` instead.

### Must not
- [ ] Must NOT claim a read-only mount hides sensitive content.
- [ ] Must NOT use an actual secret to demonstrate read-only behavior.

### Verification commands
```bash
mkdir "$WORK/eval-docs"
printf 'public reference\n' > "$WORK/eval-docs/notes.txt"
sbx --app-name "$APP" run --name eval-readonly -d shell "$REPO" "$WORK/eval-docs:ro"
sbx --app-name "$APP" exec eval-readonly cat "$WORK/eval-docs/notes.txt"
sbx --app-name "$APP" exec eval-readonly sh -c 'printf changed >> "$1"' sh "$WORK/eval-docs/notes.txt"
# The write above must fail; reading must succeed.
sbx --app-name "$APP" rm --force eval-readonly  # consented test cleanup
```

---

## Prompt 8: detached exec is unsupported

**Prompt to agent:**

> I want to start a long test run inside my sandbox and leave it going in
> the background. Can I just use `sbx exec -d`?

### Expected behaviors
- [ ] States `sbx exec -d`/`--detach` is unsupported at v0.46.0 and is
      rejected immediately with an error telling the user to omit `-d`.
- [ ] Distinguishes `sbx run -d`, which only starts the sandbox and prints its
      ID without an agent session, from detached exec.
- [ ] Offers foreground `sbx exec SANDBOX COMMAND` or an interactive
      `sbx exec -it SANDBOX bash` session instead.

### Must not
- [ ] Must NOT list `-d` among working `sbx exec` flags or retry it as a fix.
- [ ] Must NOT claim `sbx run -d` runs an arbitrary command in the sandbox.

### Verification commands
```bash
sbx --app-name "$APP" run --name eval-exec -d shell "$REPO"
sbx --app-name "$APP" exec -d eval-exec true   # must fail: detach is not supported
sbx --app-name "$APP" exec eval-exec true
sbx --app-name "$APP" rm --force eval-exec  # consented test cleanup
```
Pass: the detached form fails at once; the foreground form succeeds.

---

## Prompt 9: prune by stop age without surprises

**Prompt to agent:**

> Remove sandboxes that have been stopped for more than two weeks, but keep
> anything stopped more recently. A few stopped ones never show up in the
> list. How does the cutoff work, and is it safe to run?

### Expected behaviors
- [ ] Uses `--filter until=336h` (or an equivalent RFC 3339 / Unix timestamp)
      and runs `--dry-run` first; says the age is time since the sandbox
      stopped, not since it was created.
- [ ] Explains a stopped sandbox whose stop time is unknown is skipped, is
      reported (stderr note, or `skipped_unknown_stop` in `--dry-run --json`),
      and is removed only by an explicit `sbx rm` the user consents to.
- [ ] Notes the dry run does not print the clone-commit warning, so it checks
      for clone-mode candidates (`sandbox-<name>` remotes), starts them, and
      fetches before the real run.
- [ ] Asks for consent before adding `--force` when a non-interactive run
      fails with "stdin is not a terminal".

### Must not
- [ ] Must NOT call `sbx prune` safe to run habitually or skip the preview.
- [ ] Must NOT remove the skipped sandboxes automatically or with `rm --all`.
- [ ] Must NOT claim `--dry-run` shows the unsaved-commit warning.

### Verification commands
```bash
sbx --app-name "$APP" prune --dry-run --json --filter until=336h
sbx --app-name "$APP" prune --dry-run --filter bogus=1   # must fail: unsupported key
sbx --app-name "$APP" prune --json                       # must fail: needs --dry-run
```
Pass: the JSON preview has `would_remove` and `skipped_unknown_stop`; both
negative commands fail; nothing is removed.

---

## Prompt 10: choose a shared skills mode when creating a sandbox

**Prompt to agent:**

> I want a new sandbox that cannot pick up or change the skills my other
> sandboxes share. Also, can I switch my existing sandbox to that later?

### Expected behaviors
- [ ] Uses `--skills=off` at creation and explains `readonly` (default, or the
      configured `skills.defaultMode`) versus `readwrite`.
- [ ] Explains the mode is fixed at creation: `sbx run --name NAME --skills=...`
      on an existing sandbox fails, and changing it means remove and recreate
      after fetching any clone commits and getting consent to remove.
- [ ] Warns that a `readwrite` sandbox can change skills other sandboxes load,
      including `readonly` ones, so participants share a trust boundary.
- [ ] Warns that direct-mounted hooks, scripts, and build files can run on the
      host later and should be reviewed (including `.git/hooks`).
- [ ] Says installing, importing, updating, or removing shared skills and
      setting `skills.defaultMode` are outside this skill set and points to
      the installed `--help`.

### Must not
- [ ] Must NOT claim `--skills` can change an existing sandbox or that
      `readonly` isolates it from a `readwrite` sandbox's changes.
- [ ] Must NOT give `sbx skills` or `sbx settings` procedures.

### Verification commands
```bash
sbx --app-name "$APP" create --skills=bogus --name eval-skills-bad shell "$REPO"   # must fail: invalid value
sbx --app-name "$APP" create --skills=off --name eval-skills shell "$REPO"
sbx --app-name "$APP" run --skills=readonly --name eval-skills -d   # must fail: creation-only
sbx --app-name "$APP" rm --force eval-skills  # consented test cleanup
```
Pass: the invalid value and the reattach use both fail. Whether the store is
mounted needs a supported agent and is not checked here.

---

## Prompt 11: size a sandbox

**Prompt to agent:**

> On my Linux arm64 build machine I want 32 CPUs and 64g of memory for a
> sandbox, and I want to resize it tomorrow. What are the defaults and limits?

### Expected behaviors
- [ ] Explains `--cpus 0` means all host CPUs except a cap of 16 on Linux arm64,
      and an explicit `--cpus` can request more.
- [ ] Gives the memory rules: binary units, minimum 512 MiB, default 50% of host
      memory clamped to 512 MiB–32 GiB, maximum max(75% of host memory, 512 MiB).
- [ ] Explains `--cpus` and `--memory` are create-time only: reattaching with
      them fails, so resizing means remove and recreate after the fetch-first
      and consent steps.

### Must not
- [ ] Must NOT say auto CPU uses every host CPU on all platforms.
- [ ] Must NOT suggest resizing with `sbx run --cpus` on an existing sandbox.

### Verification commands
```bash
sbx --app-name "$APP" run --cpus 2 --name eval-sizing -d shell "$REPO"
sbx --app-name "$APP" run --cpus 4 --name eval-sizing -d   # must fail: creation-only
sbx --app-name "$APP" rm --force eval-sizing  # consented test cleanup
```
Pass: the reattach with `--cpus` fails. The Linux arm64 cap and memory bounds
are help and source claims, not checked by this fixture. Source-only checklist
(not runtime coverage): compare the answer with `sbx create --help` at v0.46.0
for the `--cpus` cap and the `--memory` minimum, default, clamp, and maximum.

---

## Should not trigger

- "Run my Docker Agent config with docker agent run --sandbox." → `docker-agent-run`

- "How do I stop an agent from reaching an internal API?" → `docker-sandboxes-network-credentials`
- "How do I write a checked-in config so my whole team gets the same sandbox setup?" → `docker-sandboxes-env`
- "How do I package a reusable mixin that adds a Postgres MCP server?" → `docker-sandboxes-kits`

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
      runnable command) BEFORE removing the sandbox, or they are lost.
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
- [ ] Recommends `sbx prune` with `--filter until=DURATION` (current
      pinned-source flag; e.g. `until=168h`) and `--dry-run` first.
- [ ] States that `sbx prune` never removes a running sandbox, but IS
      destructive to matching stopped sandboxes (state, secrets, and any
      unfetched clone commits) and should be previewed and consented to,
      not run with a default `--force`.
- [ ] Distinguishes `sbx prune` (stopped-only, bulk) from `sbx rm` (specific
      sandbox, any state).
- [ ] If asked about older/installed help showing `--filter since=`, may
      mention it as a legacy alias but should prefer `until=`.

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

## Should not trigger

- "Run my Docker Agent config with docker agent run --sandbox." → `docker-agent-run`

- "How do I stop an agent from reaching an internal API?" → `docker-sandboxes-network-credentials`
- "How do I write a checked-in config so my whole team gets the same sandbox setup?" → `docker-sandboxes-env`
- "How do I package a reusable mixin that adds a Postgres MCP server?" → `docker-sandboxes-kits`

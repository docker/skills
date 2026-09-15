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

## Should not trigger

- "Run my Docker Agent config with docker agent run --sandbox." → `docker-agent-run`

- "How do I stop an agent from reaching an internal API?" → `docker-sandboxes-network-credentials`
- "How do I write a checked-in config so my whole team gets the same sandbox setup?" → `docker-sandboxes-env`
- "How do I package a reusable mixin that adds a Postgres MCP server?" → `docker-sandboxes-kits`

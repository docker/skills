# Verification Runbook for local sandbox lifecycle commands

User-run integration checks; not executed during skill generation. Expectations
derive from sbx v0.46.0 help and internal source (see `references/sources.md`);
record `sbx version` and treat differences on another build as a finding, not a
failure of the runbook. Prerequisites: standalone `sbx`, Git, a supported local
runtime, and an existing Docker login. `sbx login` changes shared
authentication, not just the isolated test app. Run from the skill directory in
one shell; negative checks intentionally fail. Never use a real repository or
production credentials for these checks.

`--app-name` is a hidden persistent flag (internal test identity, not a public
feature and not part of this skill's ownership). It gives the checks their own
daemon and storage; the suffix allows letters, digits, hyphens, and underscores,
at most 20 characters.

## 1. Create an isolated test session and disposable Git repository

```bash
APP="l-$(date +%s)-$$"  # unique suffix, at most 20 characters
test "${#APP}" -le 20 && test -z "$SANDBOXES_STORAGE_ROOT$XDG_STATE_HOME$XDG_CACHE_HOME$XDG_CONFIG_HOME" && {
  WORK=$(mktemp -d) && test -n "$WORK" &&
  REPO="$WORK/repo" &&
  git init -q -b main "$REPO" &&
  git -C "$REPO" -c user.name=Test -c user.email=test@example.invalid commit -q --allow-empty -m initial &&
  sbx --app-name "$APP" version &&
  sbx --app-name "$APP" policy init balanced
} || echo "STOP: APP too long, a storage override is set, or setup failed; run no later step"
```
Pass: no STOP message is printed, the standalone version is displayed, and
policy is initialized for this fresh app. If `STOP` appears, or `$REPO` is
empty, do not run any later step (the `find`-based cleanup assumes no
`SANDBOXES_STORAGE_ROOT` or `XDG_*` overrides). Every following `sbx` command
must retain this same `--app-name`. If inherited
`DOCKER_CLI_PLUGIN_ORIGINAL_CLI_COMMAND` causes plugin-wrapper output, unset it
before invoking standalone `sbx`.

## 2. Compare create-without-path and run-with-a-workspace

```bash
sbx --app-name "$APP" create --name no-mount-check shell
sbx --app-name "$APP" run --name mount-check -d shell "$REPO"
sbx --app-name "$APP" ls --json
sbx --app-name "$APP" run --name mount-check -d
sbx --app-name "$APP" ls --json
```
Pass: `no-mount-check` has no workspace; `mount-check` has `$REPO`. Reusing
`--name mount-check` does not create a third sandbox. Detached run does not
open an interactive agent session.

## 3. Check clone-mode creation and reattachment

```bash
sbx --app-name "$APP" create --clone --name clone-check shell "$REPO"
git -C "$REPO" remote -v
sbx --app-name "$APP" run --clone --name clone-check -d
sbx --app-name "$APP" run --clone --name no-mount-check -d
```
Pass: the remote `sandbox-clone-check` exists; reattaching to `clone-check`
succeeds; the last command fails because `no-mount-check` was not created in
clone mode. The disposable repository has a real `.git` directory and is
neither a linked worktree nor a submodule.

## 4. Fetch a clone only while it runs, and preserve commits before removal

```bash
sbx --app-name "$APP" exec clone-check git -c user.name=Test -c user.email=test@example.invalid commit --allow-empty -m clone-check-commit
sbx --app-name "$APP" stop clone-check
git -C "$REPO" fetch sandbox-clone-check
sbx --app-name "$APP" run --name clone-check -d
git -C "$REPO" fetch sandbox-clone-check
git -C "$REPO" log --oneline -1 refs/remotes/sandbox-clone-check/main
sbx --app-name "$APP" rm --force clone-check
git -C "$REPO" rev-parse --verify refs/remotes/sandbox-clone-check/main
git -C "$REPO" log --oneline -1 refs/sandboxes/clone-check/main
```
Pass: the first fetch fails because the stopped sandbox does not serve its
clone; the second fetch succeeds and the log shows `clone-check-commit`. After
this consented removal, `rev-parse` fails (the ordinary remote ref was removed)
but the survivor ref still shows that commit. Exec uses the sandbox's recorded
workspace, not an assumed `/workspace`. Unfetched commits would be lost on
removal.

## 5. Confirm read-only mounts remain readable

```bash
mkdir "$WORK/docs"
printf 'readable-content\n' > "$WORK/docs/notes.txt"
sbx --app-name "$APP" run --name ro-check -d shell "$REPO" "$WORK/docs:ro"
sbx --app-name "$APP" exec ro-check cat "$WORK/docs/notes.txt"
sbx --app-name "$APP" exec ro-check sh -c 'echo x >> "$1"' sh "$WORK/docs/notes.txt"
```
Pass: reading succeeds; writing fails with a read-only/permission error.
Use harmless test content, never a real secrets file.

## 6. Preview prune candidates, its age filter, and rejected input

```bash
sbx --app-name "$APP" run --name prune-keep -d shell "$REPO"
sbx --app-name "$APP" create --name prune-drop shell "$REPO"
sbx --app-name "$APP" stop prune-drop
sbx --app-name "$APP" prune --dry-run --json
sbx --app-name "$APP" prune --dry-run --json --filter until=168h
sbx --app-name "$APP" prune --dry-run --filter bogus=1
sbx --app-name "$APP" prune --json
```
Pass: the unfiltered preview lists `prune-drop` under `would_remove` and
excludes running `prune-keep`; other stopped test sandboxes may also appear.
The age-filtered preview has an empty `would_remove` because this app's
sandboxes were stopped moments ago, not more than a week ago; a sandbox with an
unknown stop time would appear under `skipped_unknown_stop` instead (not
producible with this fixture). The last two commands fail: an unsupported
filter key, and `--json` without `--dry-run`. None of these commands removes
anything. Preview output does not include the clone-commit warning.

## 7. Confirm detached exec is rejected

```bash
sbx --app-name "$APP" exec -d prune-keep true
sbx --app-name "$APP" exec prune-keep true
```
Pass: the first command fails at once with "--detach is not supported for
exec; omit -d to run the command in the foreground"; the second succeeds in the
foreground. `sbx run -d` (used above) is a different, supported mode.

## 8. Check creation-time shared-skills flags

```bash
sbx --app-name "$APP" create --skills=bogus --name skills-bad shell "$REPO"
sbx --app-name "$APP" run --skills=off --name prune-keep -d
sbx --app-name "$APP" create --skills=off --name skills-off shell "$REPO"
```
Pass: the first command fails with an invalid `--skills` value (accepted:
off, readonly, readwrite) and creates nothing; the second fails because
`--skills` can only be used when creating a new sandbox; the third succeeds.
Whether the store is mounted, or whether a `shell` sandbox mounts it at all,
needs a supported agent with its own authentication and is not checked here
(verify locally).

## 9. Clean up only this disposable session

```bash
sbx --app-name "$APP" rm --force no-mount-check mount-check ro-check prune-keep prune-drop skills-off
sbx --app-name "$APP" daemon stop
find "$HOME/Library" "$HOME/.local" "$HOME/.cache" "$HOME/.config" -maxdepth 5 -type d -name "sandboxes-$APP" -print 2>/dev/null
rm -rf "$WORK"
```
Pass: these test sandboxes are removed and their isolated daemon stops. The
forced removals above are explicitly consented test cleanup, not defaults
for normal work. The `find` command is a best-effort listing of this app's
state, cache, config, and data directories, which are named exactly
`sandboxes-<APP>` under the conventional home storage roots (layout from
internal storage code; custom roots are excluded by the step 1 guard; other
platforms and any temp-directory socket path: verify locally). Review each printed path,
confirm it contains the whole `$APP` value, then remove those directories one
at a time with `rm -rf -- '<printed path>'`. Never delete the default
`sandboxes` directories. If a check stopped early, inspect this app with `sbx
--app-name "$APP" ls` and remove only its remaining test sandboxes first.

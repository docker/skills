# Verification Runbook for sbxenv.yaml commands

User-run integration checks; not executed during skill generation or refresh,
and no result here was observed. `sbx env` is experimental. Require a supported
local runtime and an existing Docker login; login is shared authentication, not
scoped by the hidden `--app-name` (an implementation-only isolation switch, not
a public CLI guarantee). These files use the shell agent and dummy values only.
Run from the skill directory in one shell. Review each generated host command
before approval. Do not add `-y` to any command except where a step says so.

Fixtures never contain a real secret. Host commands print constant markers with
`printf '%s\n' marker`; no fixture builds a format string or a command from
data. The credential-command fixture is plan-only: never run `env create` or
`env run` on it, because that would execute its command on the host and store a
credential. Every block below starts with the same marker check, so a failed
step 1 stops each later block from touching anything.

## 1. Prepare unique scratch files and an isolated app

```bash
APP="$(printf 'e-%s-%s' "$(date +%s)" "$$")"   # suffix: at most 20 characters
WORK=$(mktemp -d) || WORK=""
if [ "${#APP}" -le 20 ] && [ -n "$WORK" ] && [ -d "$WORK" ]; then
  touch "$WORK/.env-skill-check" && echo "ready: APP=$APP"
else
  echo "STOP: APP is longer than 20 characters or WORK was not created"
fi
```
Pass: prints `ready:`. If it prints `STOP:`, fix it and do not continue.

```bash
if [ -f "$WORK/.env-skill-check" ]; then
mkdir "$WORK/minimal" "$WORK/empty" "$WORK/hooks" "$WORK/remove" "$WORK/never"
mkdir "$WORK/merge" "$WORK/args" "$WORK/credcmd" "$WORK/snap" "$WORK/foreign" "$WORK/failpost"
cp assets/sbxenv.yaml "$WORK/minimal/sbxenv.yaml"
cat > "$WORK/empty/sbxenv.yaml" <<'YAML'
schemaVersion: "1"
name: env-check-empty
agent: shell
YAML
cat > "$WORK/hooks/sbxenv.yaml" <<'YAML'
schemaVersion: "1"
name: env-check-hooks
agent: shell
lifecycle:
  initialize:
    - command: printf '%s\n' initialize-ran
  postCreate:
    - command: printf '%s\n' post-create-ran
YAML
cat > "$WORK/remove/sbxenv.yaml" <<'YAML'
schemaVersion: "1"
name: env-check-remove
agent: shell
lifecycle:
  preRemove:
    - command: exit 1
YAML
cat > "$WORK/never/sbxenv.yaml" <<'YAML'
schemaVersion: "1"
name: env-check-never
agent: shell
YAML
cat > "$WORK/merge/base.yaml" <<'YAML'
schemaVersion: "1"
name: env-check-merge
workspace: .
YAML
cat > "$WORK/merge/overlay.yaml" <<'YAML'
agent: shell
env:
  LAYER: overlay
YAML
cat > "$WORK/args/sbxenv.yaml" <<'YAML'
schemaVersion: "1"
name: env-check-args
agent: shell
args:
  channel:
    default: stable
    enum: [stable, beta]
  endpoint:
    required: true
env:
  RELEASE_CHANNEL: ${{ env.args.channel }}
  API_ENDPOINT: ${{ env.args.endpoint }}
YAML
cat > "$WORK/credcmd/sbxenv.yaml" <<'YAML'
schemaVersion: "1"
name: env-check-credcmd
agent: shell
secrets:
  github:
    command: printf '%s' dummy-token
YAML
cat > "$WORK/snap/ok.yaml" <<'YAML'
schemaVersion: "1"
name: env-check-snap
agent: shell
secrets:
  github:
    ref: op://dummy/dummy/dummy
    snapshot: true
YAML
cat > "$WORK/snap/value.yaml" <<'YAML'
schemaVersion: "1"
name: env-check-snap
agent: shell
secrets:
  github:
    value: dummy-not-a-secret
    snapshot: true
YAML
cat > "$WORK/snap/refresh.yaml" <<'YAML'
schemaVersion: "1"
name: env-check-snap
agent: shell
secrets:
  github:
    ref: op://dummy/dummy/dummy
    snapshot: true
    refresh: 5m
YAML
cat > "$WORK/snap/noverify.yaml" <<'YAML'
schemaVersion: "1"
name: env-check-snap
agent: shell
secrets:
  github:
    ref: op://dummy/dummy/dummy
    snapshot: true
    noVerify: true
YAML
cat > "$WORK/snap/cmdbackend.yaml" <<'YAML'
schemaVersion: "1"
name: env-check-snap
agent: shell
secrets:
  github:
    command: printf '%s' dummy-token
    snapshot: true
    backend: cli
YAML
cat > "$WORK/snap/sdk.yaml" <<'YAML'
schemaVersion: "1"
name: env-check-snap
agent: shell
secrets:
  github:
    ref: op://dummy/dummy/dummy
    snapshot: true
    backend: sdk
YAML
cat > "$WORK/foreign/sbxenv.yaml" <<'YAML'
schemaVersion: "1"
name: env-check-foreign
agent: shell
YAML
cat > "$WORK/failpost/sbxenv.yaml" <<'YAML'
schemaVersion: "1"
name: env-check-failpost
agent: shell
lifecycle:
  postCreate:
    - command: exit 1
YAML
else
  echo "STOP: step 1 did not complete"
fi
```
Pass: each scenario has its own file and a distinct explicit or derived name.
No files outside the scratch directory are edited.

## 2. Verify plan-only behavior and omitted workspace

```bash
if [ -f "$WORK/.env-skill-check" ]; then
  sbx --app-name "$APP" env plan "$WORK/minimal"
  sbx --app-name "$APP" env plan "$WORK/empty"
else
  echo "STOP: step 1 did not complete"
fi
```
Pass: both print apply plans without creating a sandbox, recording approval,
or running commands. The first declares the directory holding its file as
a workspace; the second declares no workspace. Plan itself never prompts;
this does not prove that a later create/run will apply silently.

## 3. Verify initialize reruns but postCreate runs only once

```bash
if [ -f "$WORK/.env-skill-check" ]; then
  sbx --app-name "$APP" settings get env.rememberHostCommands
  sbx --app-name "$APP" policy init balanced
  sbx --app-name "$APP" env run -d "$WORK/hooks"
  sbx --app-name "$APP" env run -d "$WORK/hooks"
  sbx --app-name "$APP" env exec "$WORK/hooks" -- pwd
else
  echo "STOP: step 1 did not complete"
fi
```
The first command is read-only; expect `false`. If it is not `false`, stop:
consent is remembered and the next steps would not prompt. Approve both runs
interactively after reviewing the plan. Pass: the first run's host output shows
`initialize-ran` and `post-create-ran`; the second shows `initialize-ran` only;
`exec` prints the sandbox working directory and neither marker. Initialize
runs from the project directory on the host on every create/run, including
reattachment. PostCreate runs on the host once after creation.

## 4. Verify unchanged approved configuration without host commands is silent

```bash
if [ -f "$WORK/.env-skill-check" ]; then
  sbx --app-name "$APP" env run -d "$WORK/empty"
  sbx --app-name "$APP" env run -d "$WORK/empty"
else
  echo "STOP: step 1 did not complete"
fi
```
Approve the first invocation interactively; do not use auto-approve. Pass:
the second run reuses the same sandbox without an approval prompt because
nothing changed and the file declares no host commands. This silence does not
apply to `$WORK/hooks` or `$WORK/credcmd`, which hold host code.

## 5. Verify preRemove failure does not prevent removal

```bash
if [ -f "$WORK/.env-skill-check" ]; then
  sbx --app-name "$APP" env create "$WORK/remove"
  sbx --app-name "$APP" env rm "$WORK/remove"
else
  echo "STOP: step 1 did not complete"
fi
```
Review and approve both the create plan and the destroy plan. Pass: removal
warns that preRemove did not finish but still removes this sandbox. The
hook is the known `exit 1` command, not an untrusted archival script. If this
step fails or the removal is declined, step 13 removes the fixture.

## 6. Verify env exec does not create a missing sandbox

```bash
if [ -f "$WORK/.env-skill-check" ]; then
  sbx --app-name "$APP" env exec "$WORK/never" -- echo hi
else
  echo "STOP: step 1 did not complete"
fi
```
Pass: fails because `env-check-never` has never been created. A successful
`echo hi` here would contradict the expected missing-sandbox behavior.

## 7. Verify mount-root environment file protection

```bash
if [ -f "$WORK/.env-skill-check" ]; then
  sbx --app-name "$APP" env run -d "$WORK/minimal"
  sbx --app-name "$APP" env exec "$WORK/minimal" -- touch "$WORK/minimal/sbxenv.yaml"
else
  echo "STOP: step 1 did not complete"
fi
```
Approve creation. Pass: the `touch` fails with a read-only or permission error
(exact wording: verify locally). The file is directly at the workspace mount
root (`workspace: .`). This does not prove protection for files in a
renameable subdirectory; those have the rename gap described in SKILL.md. The
probe uses no in-sandbox shell redirection.

## 8. Verify merged requirements (plan-only)

```bash
if [ -f "$WORK/.env-skill-check" ]; then
  sbx --app-name "$APP" env plan "$WORK/merge/base.yaml" "$WORK/merge/overlay.yaml"
  sbx --app-name "$APP" env plan "$WORK/merge/base.yaml"
  sbx --app-name "$APP" env plan "$WORK/merge/overlay.yaml"
else
  echo "STOP: step 1 did not complete"
fi
```
Pass: the first succeeds and shows agent `shell`, because `agent` arrives from
the later layer. The second fails with an `agent is required` style error and
the third with a `schemaVersion is required` style error (exact wording: verify
locally). Nothing is created or approved.

## 9. Verify argument validation and precedence (plan-only)

```bash
if [ -f "$WORK/.env-skill-check" ]; then
  printf '%s\n' 'channel=beta' > "$WORK/args/production.args"
  sbx --app-name "$APP" env plan "$WORK/args"
  sbx --app-name "$APP" env plan --env-arg endpoint=https://api.example.invalid "$WORK/args"
  sbx --app-name "$APP" env plan --env-arg endpoint=https://api.example.invalid --env-arg channel=nightly "$WORK/args"
  sbx --app-name "$APP" env plan --env-arg endpoint=https://api.example.invalid --env-arg extra=1 "$WORK/args"
  sbx --app-name "$APP" env plan --env-arg endpoint=https://api.example.invalid --env-args-file "$WORK/args/production.args" --env-arg channel=stable "$WORK/args"
else
  echo "STOP: step 1 did not complete"
fi
```
Pass: run 1 fails (required `endpoint` missing); run 2 succeeds with `stable`;
run 3 fails (`nightly` is outside the enum); run 4 fails (`extra` is not
declared); run 5 succeeds with `stable`, because `--env-arg` beats the args
file. The args file is written by the host shell from a constant string and is
inside the scratch directory.

## 10. Verify credential-command rows, the skip flag, and snapshot rules (plan-only)

```bash
if [ -f "$WORK/.env-skill-check" ]; then
  sbx --app-name "$APP" env plan "$WORK/credcmd"
  sbx --app-name "$APP" env plan --skip-host-commands "$WORK/credcmd"
  sbx --app-name "$APP" env plan --skip-host-commands "$WORK/hooks"
  sbx --app-name "$APP" env plan "$WORK/snap/ok.yaml"
  sbx --app-name "$APP" env plan "$WORK/snap/value.yaml"
  sbx --app-name "$APP" env plan "$WORK/snap/refresh.yaml"
  sbx --app-name "$APP" env plan "$WORK/snap/noverify.yaml"
  sbx --app-name "$APP" env plan "$WORK/snap/cmdbackend.yaml"
  sbx --app-name "$APP" env plan "$WORK/snap/sdk.yaml"
else
  echo "STOP: step 1 did not complete"
fi
```
Pass: runs 1 and 2 both list the `github` secret with its `command` and a
working directory of "fresh host temporary directory"; the skip flag does not
remove the credential row. Run 3 omits the `lifecycle` rows. Run 4 succeeds.
Runs 5 to 9 fail at load with snapshot errors (`value`, `refresh`, `noVerify`,
a command snapshot selecting a backend, and a non-cli backend). No command runs
and no secret is resolved because `plan` only prints.

## 11. Verify a same-named foreign sandbox is refused

```bash
if [ -f "$WORK/.env-skill-check" ]; then
  sbx --app-name "$APP" create --name env-check-foreign shell
  sbx --app-name "$APP" env create --auto-approve "$WORK/foreign"
  sbx --app-name "$APP" env run -d --auto-approve "$WORK/foreign"
  sbx --app-name "$APP" ls
else
  echo "STOP: step 1 did not complete"
fi
```
Pass: both `env` commands fail without creating, attaching or removing
anything, even with `--auto-approve`; `ls` still shows `env-check-foreign`. The
sandbox was built with plain `sbx create`, so `sbx env` has no record of it and
create and run refuse it even though its declaration agrees. Do not run
`env rm` against it in this step; `env rm` has its own, narrower refusal rule.

## 12. Verify failed-create residue and scoped recovery

```bash
if [ -f "$WORK/.env-skill-check" ]; then
  sbx --app-name "$APP" env create "$WORK/failpost"
  sbx --app-name "$APP" ls
  sbx --app-name "$APP" env rm --skip-host-commands "$WORK/failpost"
else
  echo "STOP: step 1 did not complete"
fi
```
Approve the create interactively. Pass: create ends non-zero at `postCreate`
with a hint to run `sbx env rm`; `ls` shows `env-check-failpost` (created
before the failing hook); `env rm` with the same path prints a destroy plan for
that sandbox only and, once confirmed, removes it. This fixture has no
credentials, so it shows sandbox residue only; credential, binding and MCP
residue are covered by the source-backed rules in SKILL.md, not exercised here.

## 13. Clean up only this disposable session

Stage A removes every fixture sandbox by its known path or name and stops at the
first failure, so nothing else is deleted:

```bash
if [ -f "$WORK/.env-skill-check" ]; then
  sbx --app-name "$APP" env rm --force "$WORK/minimal" &&
  sbx --app-name "$APP" env rm --force "$WORK/empty" &&
  sbx --app-name "$APP" env rm --force "$WORK/hooks" &&
  sbx --app-name "$APP" env rm --force --skip-host-commands "$WORK/remove" &&
  sbx --app-name "$APP" env rm --force --skip-host-commands "$WORK/failpost" &&
  sbx --app-name "$APP" rm --force env-check-foreign &&
  sbx --app-name "$APP" ls ||
  echo "STOP: a cleanup command failed; scratch files are kept. Inspect ls and remove only the test sandboxes named above."
else
  echo "STOP: no scratch marker; not deleting anything"
fi
```
Review the `ls` output. Pass: no test sandbox remains. If one does, leave the
scratch directory and declarations in place, remove that sandbox with its
fixture path or name, and repeat stage A. Stage B runs only after that:

```bash
if [ -f "$WORK/.env-skill-check" ]; then
  sbx --app-name "$APP" daemon stop &&
  rm -rf -- "$WORK" ||
  echo "STOP: daemon stop failed; scratch files are kept"
else
  echo "STOP: no scratch marker; not deleting anything"
fi
```
Pass: the isolated daemon stops and only the scratch directory that holds the
marker is deleted. Forced removal is consented cleanup of these known test
files only. No global cleanup (`sbx prune`, `sbx secret rm --all`,
`sbx policy reset`) is part of this runbook. If the optional CI fixture from the
eval was created, remove it with the eval's own cleanup line first. Never
substitute the default daemon.

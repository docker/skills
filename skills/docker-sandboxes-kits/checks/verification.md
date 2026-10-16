# Verification Runbook for kit spec.yaml commands

`sbx kit` is EXPERIMENTAL (sbx v0.46.0). The local validation and inspection
steps below do not create sandboxes; composing/creating does. This runbook does
not publish artifacts or use a signing identity. This runbook is unexecuted; use
an isolated, unique `--app-name` (≤20 characters) on every `sbx` invocation, a
scratch registry namespace, and never a production signing key. `--app-name` is
a hidden persistent root flag ("Storagekit application name for isolated daemon
instance (for development/debugging)"), absent from public help: an internal
test identity, not a documented feature and not a confinement boundary. It
isolates daemon state and paths; it does not isolate the Docker/cloud sign-in,
the host filesystem or the network. Edits to a copied spec.yaml
below use a small portable Python one-liner rather than `sed -i` (whose
in-place syntax differs between BSD/macOS and GNU/Linux) so the runbook
works on POSIX shells with Python 3. Docker login and a supported local
runtime are prerequisites; login changes shared authentication, not just
the test app. Run from the skill directory in one shell.

`sbx kit validate` accepts a local **directory**, ZIP file, or git repository,
not an OCI reference or a bare spec.yaml file (its help text says "directory or
ZIP file"; git is accepted, OCI is rejected before loading). Other kit subcommands accept
different reference types; consult their help. Copy each asset to a file
named `spec.yaml` in its own directory before running these checks.

```bash
APP="k-$(date +%s)-$$"  # fresh suffix, at most 20 characters
if [ "${#APP}" -ge 1 ] && [ "${#APP}" -le 20 ]; then
  WORK=$(mktemp -d)
  printf 'APP=%s WORK=%s\n' "$APP" "$WORK"   # keep both for cleanup in step 9
  mkdir "$WORK/kit-sandbox-example" "$WORK/kit-mixin-example" "$WORK/workspace"
  cp assets/spec-sandbox.yaml "$WORK/kit-sandbox-example/spec.yaml"
  cp assets/spec-mixin.yaml "$WORK/kit-mixin-example/spec.yaml"
else
  unset APP
  printf 'invalid APP: stop here; never run sbx without --app-name\n' >&2
fi
```

## 1. Validate both example kits (schema-only checks)

```bash
sbx --app-name "$APP" kit validate "$WORK/kit-sandbox-example/"
sbx --app-name "$APP" kit validate "$WORK/kit-mixin-example/"
```
Pass: both report valid with no errors. This proves only schema
well-formedness — it does NOT compose either kit against a base agent and
does NOT check any network reachability; see steps 3–4 for the difference.

## 2. Confirm a top-level unknown field is rejected (strictness is not blanket)

```bash
cp -r "$WORK/kit-mixin-example" "$WORK/kit-typo-mixin"
python3 - "$WORK/kit-typo-mixin/spec.yaml" <<'PYCODE'
import pathlib, sys
p = pathlib.Path(sys.argv[1])
p.write_text(p.read_text().replace('permissions:', 'permisions:', 1))
PYCODE
sbx --app-name "$APP" kit validate "$WORK/kit-typo-mixin/"
```
Pass: fails with an unrecognized-field error naming `permisions`, not a
silent no-op. This proves top-level strictness only.

### 2b. Observe a block with its own unmarshaler (verify locally)

```bash
cp -r "$WORK/kit-sandbox-example" "$WORK/kit-nested-typo"
printf '\nsandbox:\n  command:\n    defualt: ["--x"]\n' >> "$WORK/kit-nested-typo/spec.yaml"
sbx --app-name "$APP" kit validate "$WORK/kit-nested-typo/"
sbx --app-name "$APP" kit inspect "$WORK/kit-nested-typo/" --json
```
Observe, do not assume: source analysis predicts `validate` passes and the
misspelt `defualt` key vanishes from the inspected `sandbox.command`, because
the mapping is decoded by its own unmarshaler. Either outcome is recorded; the
skill claims only that a passing `validate` never proves a typo-free spec.

## 3. Establish a truthful policy baseline before testing egress (isolated test app only)

The genuine minimal mixin's `permissions.network.allow` (`registry.npmjs.org`)
does not by itself prove anything is blocked: the default `balanced` global
policy already allows many common hosts, and `allow-all` allows everything.
To observe an actual denial, initialize a `deny-all` baseline — do this ONLY
under this runbook's own isolated `--app-name`, never on a daemon you use
for real work:

```bash
sbx --app-name "$APP" policy init deny-all
```
Pass: `sbx --app-name "$APP" policy ls` shows the deny-all preset active for
this isolated app only.

## 4. Confirm the all-egress-declared rule against the truthful baseline

```bash
sbx --app-name "$APP" create --kit "$WORK/kit-mixin-example/" --name kit-egress-check shell "$WORK/workspace"
sbx --app-name "$APP" policy check network --sandbox kit-egress-check registry.npmjs.org   # allowed: this kit's own allow entry
sbx --app-name "$APP" policy check network --sandbox kit-egress-check example.com           # NOT allowed: deny-all baseline, no kit grants it
sbx --app-name "$APP" policy ls kit-egress-check --source kit --include-inactive             # kit-provisioned rule for registry.npmjs.org
```
Pass: `registry.npmjs.org` is allowed (the mixin's own declared entry, on
top of the deny-all baseline); an unrelated host (`example.com`) is not —
this is what actually demonstrates the all-egress-declared/additive model,
not merely removing an entry from one kit's `allow` list (which proves
nothing about the effective policy on its own).

## 5. Confirm a mixin cannot declare a sandbox: block

```bash
cp -r "$WORK/kit-mixin-example" "$WORK/kit-bad-mixin"
printf '\nsandbox:\n  image: docker/sandbox-templates:shell-docker\n' >> "$WORK/kit-bad-mixin/spec.yaml"
sbx --app-name "$APP" kit validate "$WORK/kit-bad-mixin/"
```
Pass: fails — a `sandbox:` block is forbidden for `kind: mixin`.

## 6. Confirm a duplicate-service credential fails composition, not `kit validate`

```bash
cp -r "$WORK/kit-mixin-example" "$WORK/kit-github-mixin"
python3 - "$WORK/kit-github-mixin/spec.yaml" <<'PYCODE'
import pathlib, sys
p = pathlib.Path(sys.argv[1])
p.write_text(p.read_text() + '''
credentials:
  - service: github
    apiKey:
      name: GITHUB_TOKEN
      inject:
        - domain: api.github.com
          scheme: bearer
''')
PYCODE
sbx --app-name "$APP" kit validate "$WORK/kit-github-mixin/"   # passes: schema-only
sbx --app-name "$APP" create --kit "$WORK/kit-github-mixin/" --name kit-dup-check shell "$WORK/workspace"   # expect: fails, shell already declares github
```
Pass: `kit validate` reports the kit as schema-valid on its own; only the
actual `sbx create --kit` composition against `shell` (which already
declares a `github` credential) fails with a duplicate-service error —
confirming `kit validate` proves schema, not composability.

## 7. Confirm `sbx kit add` recreate-aware requirement

```bash
sbx --app-name "$APP" run --name kit-add-check -d shell "$WORK/workspace"
sbx --app-name "$APP" kit add kit-add-check "$WORK/kit-mixin-example/"
sbx --app-name "$APP" kit inspect "$WORK/kit-mixin-example/"
```
Then check the actual sandbox, not just the artifact:
```bash
sbx --app-name "$APP" exec kit-add-check printenv MY_MIXIN
sbx --app-name "$APP" policy check network --sandbox kit-add-check registry.npmjs.org
```
Pass: `kit add` succeeds, the variable is `1`, and the host is allowed.
`kit inspect` alone only shows the input artifact, not applied state. Read every
warning `kit add` prints (withheld credentials, mounts that failed to replay,
"record could not be saved"); a live swap is not proof the kit set is durable.

### 7b. Confirm unsupported kit shapes are refused, not half-applied

```bash
cp -r "$WORK/kit-mixin-example" "$WORK/kit-startup-mixin"
printf '\nsetup:\n  startup:\n    - command: ["true"]\n' >> "$WORK/kit-startup-mixin/spec.yaml"
cp -r "$WORK/kit-mixin-example" "$WORK/kit-volume-mixin"
printf '\nvolumes:\n  - path: /data\n    size: 512m\n' >> "$WORK/kit-volume-mixin/spec.yaml"
sbx --app-name "$APP" kit add kit-add-check "$WORK/kit-startup-mixin/"   # expect: refused (setup.startup)
sbx --app-name "$APP" kit add kit-add-check "$WORK/kit-volume-mixin/"    # expect: refused (volumes)
sbx --app-name "$APP" exec kit-add-check printenv MY_MIXIN              # still 1
```
Pass: both adds fail with "the kit-add recreate flow does not yet ..." and the
sandbox keeps running with its previous kit set. Do not follow the error's
`sbx rm` + `sbx create` suggestion; it destroys the sandbox. Recreate from
scratch only as a new sandbox with a different `--name`, with user consent.

## 8. Inspect the sandbox kit declaration without assuming inheritance was resolved

```bash
sbx --app-name "$APP" kit inspect "$WORK/kit-sandbox-example/" --json | grep -E '"extends"[[:space:]]*:[[:space:]]*"shell"'
```
Pass: for this ordinary local-directory load, inspect reports
`"extends": "shell"` (the key is omitted when empty) and prints no inherited
image. The output is the loaded artifact projected into v2 grammar, not raw
YAML. This is conditional, not a general guarantee: a signature-vouched,
commit-pinned git load under `kit.requireSignature` resolves the built-in parent
and clears `extends`. Parent resolution for a sandbox occurs during create/run;
this inspect command alone does not prove image availability, credentials or
egress.

## 9. Clean up (consented removal of this runbook's own isolated app and sandboxes)

```bash
sbx --app-name "$APP" rm --force kit-add-check kit-egress-check
sbx --app-name "$APP" daemon stop
rm -rf "$WORK"
```
If step 6 unexpectedly created `kit-dup-check`, list this app's sandboxes and
remove that one by name first. This cleanup removes the named sandboxes and stops
this app's daemon; the isolated app's own state directories and its `deny-all`
policy store stay on disk. They are not the default daemon's state: remove them
only by a verified, app-scoped procedure (see `docker-sandboxes-lifecycle`), and
never substitute default-daemon cleanup.
`--app-name "$APP"` isolates every command in this runbook to its own
daemon; the `deny-all` baseline set in step 3 applies only to that isolated
app and never touches the default daemon's policy.

# Verification runbook for v3 kits

An unexecuted runbook for v3 kit descriptors. It uses `docker buildx`,
`kit-tck`, and `sbx kit inspect`. It is not a runtime evaluation.

Prerequisites: Docker with Buildx, a pinned `kit-tck` release or commit that
you have recorded, and an `sbx` release you have confirmed supports Kits v3.
This runbook publishes nothing, signs nothing, and uses no registry. It
creates one uniquely named builder and one scratch directory, and the cleanup
step removes only those. Use an isolated, unique `--app-name` (at most 20
characters) on every `sbx` invocation. Run from the skill directory in one
shell.

## A1. Set up scratch resources

```bash
APP="k-$(date +%s)-$$"        # fresh suffix, at most 20 characters
BUILDER="kit-eval-$$"         # unique name; the cleanup removes only this builder
WORK=$(mktemp -d)
mkdir "$WORK/extra-egress" "$WORK/workspace"
cp assets/v3-mixin-egress.yaml "$WORK/extra-egress/extra-egress.yaml"
docker buildx create --name "$BUILDER" --driver docker-container --bootstrap
```
The v3 asset is a companion-pair kit by stem: `extra-egress/extra-egress.yaml`
with no `.dockerfile`, because it is declaration-only.

## A2. Inspect the declarations

```bash
sbx --app-name "$APP" kit inspect "$WORK/extra-egress"
```
Pass: it prints the `network-policy@1` and `agent-context@2` requests. This
shows declarations only; it does not prove the kit builds or conforms.

## A3. Check the descriptor through the frontend

```bash
(cd "$WORK/extra-egress" && docker buildx build --builder "$BUILDER" . \
  -f extra-egress.yaml --output type=cacheonly)
```
Pass: the build succeeds. The descriptor is checked before any content is
built, so a bad field fails here quickly.

## A4. Export a layout and judge it with `kit-tck`

```bash
(cd "$WORK/extra-egress" && docker buildx build --builder "$BUILDER" . \
  -f extra-egress.yaml -t extra-egress:0.0.0 \
  --output type=oci,dest="$WORK/layout",tar=false)
kit-tck validate --layout "$WORK/layout" 0.0.0
```
Pass: `kit-tck` reports no failures. Pass the tag alone (`0.0.0`), not
`extra-egress:0.0.0`. A build alone is not proof the kit works.

## A5. Confirm strict decoding rejects a misspelled key

```bash
mkdir "$WORK/typo"
python3 - "$WORK/extra-egress/extra-egress.yaml" "$WORK/typo/typo.yaml" <<'PYCODE'
import pathlib, sys
src = pathlib.Path(sys.argv[1]).read_text()
pathlib.Path(sys.argv[2]).write_text(src.replace('capabilities:', 'capabilites:', 1))
PYCODE
(cd "$WORK/typo" && docker buildx build --builder "$BUILDER" . \
  -f typo.yaml --output type=cacheonly)
```
Pass: the build fails with an unrecognized-key error naming `capabilites`, not
a silent no-op.

## A6. Confirm `sbx kit validate` is not a v3 check

```bash
sbx --app-name "$APP" kit validate "$WORK/extra-egress"
```
Pass: the command does not succeed. The v3 source says `sbx kit validate`
does not accept a v3 source kit. Whatever it prints, do not cite it as
validation of the v3 descriptor. If it does succeed on your `sbx` release,
record the release and report a conflict with the skill.

## A7. Optional: compose onto a v3 workload (manual)

Only if you have a v3 workload kit you trust at `./<workload>`; this skill
does not supply one.

```bash
sbx --app-name "$APP" run ./<workload> --kit "$WORK/extra-egress" \
  --detached --name kit-v3-check "$WORK/workspace"
sbx --app-name "$APP" policy check network --sandbox kit-v3-check registry.npmjs.org
```
Observe and record the decision. Do not assume the egress request was granted
just because it is declared; the host decides. For a mixin that ships a tool,
run the tool with `sbx exec` (not as an argument after `--` on `sbx run`).

## A8. Clean up (consented removal of only what this runbook created)

```bash
sbx --app-name "$APP" rm --force kit-v3-check   # only if A7 was run
sbx --app-name "$APP" daemon stop               # only if A7 was run
docker buildx rm "$BUILDER"
rm -rf "$WORK"
```
The builder name is unique to this run. Do not remove a builder you did not
create, and do not substitute `docker buildx prune`, `docker system prune`,
or any unscoped removal.

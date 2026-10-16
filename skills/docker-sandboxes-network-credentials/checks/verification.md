# Verification Runbook for network policy and secret commands

Status: **unexecuted**. These commands mutate persistent daemon state and the
credential store. This runbook is a user-run procedure; no step has been run
against sbx v0.46.0. Use an isolated, unique `--app-name` (≤20 characters) on
**every** `sbx` invocation, and NEVER use real production secret values while
testing — use conspicuously synthetic strings. This runbook never runs
`sbx policy reset` against the default daemon, never registers a `--command`
or `--ref` source (no host helper is executed), never changes UDP or other
settings, and never uses the hidden custom-mode removal flags. Where it needs
a policy store, it initializes one from scratch on its own isolated
`--app-name`.

Require an existing Docker login and a supported local runtime. Login is
shared authentication, not scoped by the isolated app; `--app-name` isolates
daemon and store state, not Docker login or runtime outcomes. Run in one shell.
If any step fails or is interrupted, still run step 9 with the same `APP`.

```bash
APP="p-$(date +%s)-$$"  # fresh suffix: letters, digits, hyphen, underscore; at most 20 characters
[ "${#APP}" -le 20 ] || { printf '%s\n' "APP too long: ${#APP}"; return 1 2>/dev/null || exit 1; }
WORK=$(mktemp -d) && [ -n "$WORK" ] || { printf '%s\n' 'workspace creation failed: stop'; return 1 2>/dev/null || exit 1; }
```
Abort if the length check fails; never continue without `--app-name`, because
that would target the default daemon. `--app-name` is a hidden development/
testing flag (not in exported help); its suffix limits are an implementation
detail (see `references/sources.md`, S33).

## 1. Initialize and inspect the global policy

```bash
sbx --app-name "$APP" policy init balanced
sbx --app-name "$APP" policy ls --wide
sbx --app-name "$APP" policy ls --created-via default
```
Pass: `policy ls --wide` shows the balanced preset's rules with resource,
decision, and rule metadata columns; the `--created-via default` filter lists
the preset-created rules. Under organization governance local allow rules are
inactive; this check assumes local mode (look for a `Governance:` line; add
`--include-inactive` to see inactive rules).

## 2. Confirm deny-over-allow precedence

```bash
sbx --app-name "$APP" policy allow network example.com
sbx --app-name "$APP" policy deny network example.com
sbx --app-name "$APP" policy check network example.com --verbose
```
Pass: `check network` reports the request would be **denied** — the deny rule
wins even though an allow rule for the same host also exists. This checks host
and port only, not authentication or any HTTP method/path.

## 3. Confirm a per-sandbox deny only narrows, never widens

```bash
sbx --app-name "$APP" run --name policy-check -d shell "$WORK"
sbx --app-name "$APP" policy allow network internal.example.com               # globally allowed
sbx --app-name "$APP" policy check network internal.example.com                # confirm: allowed globally
sbx --app-name "$APP" policy deny network --sandbox policy-check internal.example.com
sbx --app-name "$APP" policy check network --sandbox policy-check internal.example.com
sbx --app-name "$APP" policy check network internal.example.com
```
Pass: the sandbox-context check reports **denied**, while the final global
check (no `--sandbox`) still reports **allowed** for
`internal.example.com` — the sandbox-scoped deny narrows access for
`policy-check` alone without widening or otherwise changing the global
policy that every other sandbox still sees.

Remove only the sandbox-scoped deny, then check both scopes again:
```bash
sbx --app-name "$APP" policy rm network --sandbox policy-check --resource internal.example.com
sbx --app-name "$APP" policy check network --sandbox policy-check internal.example.com
sbx --app-name "$APP" policy check network internal.example.com
```
Pass: both checks report **allowed**; the global allow rule is unchanged. Read
the removal prompt: it must name `sandbox:policy-check` and the resource.

## 4. Confirm secret listing modes and the shell agent sentinel

```bash
printf 'throwaway-test-value' | sbx --app-name "$APP" secret set anthropic --sandbox policy-check
DEFAULT_LS=$(sbx --app-name "$APP" secret ls --sandbox policy-check --json) || { printf '%s\n' 'default ls failed: stop'; return 1 2>/dev/null || exit 1; }
SERVICE_LS=$(sbx --app-name "$APP" secret ls --service anthropic --sandbox policy-check --json) || { printf '%s\n' 'service ls failed: stop'; return 1 2>/dev/null || exit 1; }
printf '%s\n' "$DEFAULT_LS" | grep -F '(stored)'
printf '%s\n' "$SERVICE_LS" | grep -F 'throwa**********alue'
! printf '%s\n' "$DEFAULT_LS" "$SERVICE_LS" | grep -F 'throwaway-test-value'
sbx --app-name "$APP" exec policy-check sh -c 'test "$ANTHROPIC_API_KEY" = proxy-managed'
```
Stop if any setup command or assertion fails; do not run later steps except
consented cleanup of fixtures whose creation was confirmed. If either listing
fails, the block aborts before the later listing or sentinel command: the
absence check is only meaningful on output from successful listings. Pass: the default listing shows the service row as `(stored)` (no value is
decrypted for it); the `--service anthropic` listing shows the 20-character
synthetic value as the masked preview `throwa**********alue` (first six and
last four characters visible); the full value appears in neither; and the shell
agent's Anthropic environment variable is expected to contain the sentinel
(expected value, unexecuted; the exact shell startup value is not independently
established). Listing is **not** metadata-only: a real credential may reveal a prefix and,
for sufficiently long values (20+ characters), a suffix in `--service` mode and
in registry or custom rows (short values are fully masked, registry values
under 12 characters too), so never run this with real values or paste real listing output anywhere. This does not
test outbound header substitution or OAuth response masking, and it does not
establish a no-exposure guarantee for OAuth passthrough agents.

## 5. Confirm registry credential storage scopes

```bash
printf 'throwaway-token' | sbx --app-name "$APP" secret set --registry ghcr.io --password-stdin
printf 'throwaway-token' | sbx --app-name "$APP" secret set --sandbox policy-check --registry ghcr.io --password-stdin
sbx --app-name "$APP" secret ls --json
```
Pass: two distinct registry entries are listed — one with scope `host-only`
(no `--all-sandboxes`/`--sandbox`), one scoped to `policy-check`; each secret
renders as the preview `throwa*********` (15 characters, first six visible).
This checks stored scope metadata only, not registry authentication, runtime
injection, or the absence of credentials from the sandbox filesystem. A live
pull check would need a disposable registry and short-lived test credentials.

Confirm that host-only and all-sandboxes entries compete:
```bash
printf 'throwaway-token' | sbx --app-name "$APP" secret set --all-sandboxes --registry ghcr.io --password-stdin
sbx --app-name "$APP" secret ls --json
```
Pass: the `host-only` entry is replaced by one with scope `global`; the
`policy-check` entry is unchanged.

Remove only the sandbox-scoped test entry without touching the global entry:
```bash
sbx --app-name "$APP" secret rm --registry ghcr.io --sandbox policy-check --force
sbx --app-name "$APP" secret ls --json
```
Pass: only the `global` registry entry remains. The forced removal is
consented cleanup of the throwaway credential just created above.

## 6. Confirm targeted rule removal, not a full reset, is the routine fix

```bash
sbx --app-name "$APP" policy ls --wide
sbx --app-name "$APP" policy rm network --resource example.com
sbx --app-name "$APP" policy ls --wide
```
Pass: the removal prompt names the global scope and the selector; the rules
removed are those matching `example.com` — expected to include both the global
allow and the global deny from step 2, because one resource selector can match
more than one rule (confirm in the second listing) — and every other rule and every running sandbox under this isolated app
is untouched. Contrast with `sbx policy reset`, which this runbook never runs
against a shared/default daemon because it deletes the whole policy store and
stops every running sandbox.

## 7. Confirm failure paths (read-only negatives)

```bash
sbx --app-name "$APP" policy rm network
sbx --app-name "$APP" secret rm github --sandbox policy-check
sbx --app-name "$APP" policy allow network '*'
```
Pass: each command exits non-zero without changing state. The first reports
that at least one selector (`--id` or `--resource`) is required. The second
reports that no secret is found for service `github` in scope `policy-check`
(no `--force`, so no reconciliation). The third rejects the bare `*` pattern
instead of storing a rule. If a command succeeds, stop and inspect with
`policy ls --wide` and `secret ls --json` before continuing.

## 8. Read-only flag-presence checks (no state change)

```bash
sbx --app-name "$APP" policy allow network --help
sbx --app-name "$APP" policy ls --help
sbx --app-name "$APP" secret set --help
sbx --app-name "$APP" secret rm --help
```
Pass: help lists `--protocol`, `--created-via`, `--include-inactive`,
`--registry-auth-endpoint`, `--no-verify`, `--show-error` and the fresh
temporary directory paragraph for command secrets. Hidden `--host/--env/
--placeholder` are not listed by `secret rm --help` options; that absence is
expected.

## 9. Clean up (consented removal of this runbook's own isolated app and sandbox)

```bash
sbx --app-name "$APP" secret ls --json
sbx --app-name "$APP" policy ls --wide
sbx --app-name "$APP" secret rm --all --force
sbx --app-name "$APP" rm --force policy-check
sbx --app-name "$APP" daemon stop
rm -rf "$WORK"
```
Pass: the two listings show only this runbook's fixtures. `secret rm --all`
removes every stored secret of every kind and scope in this isolated app, and
`--force` skips only the CLI prompt: run it only after the listing confirms
the app holds nothing but the throwaway fixtures and the user consents.

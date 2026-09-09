# Verification Runbook for network policy and secret commands

These commands mutate persistent daemon state and the credential store. This
runbook is an unexecuted, user-run procedure. Use an isolated, unique
`--app-name` (≤20 characters) on **every** `sbx` invocation, and NEVER use
real production secret values while testing — use throwaway strings. This
runbook never runs `sbx policy reset` against the default daemon; where it
needs a policy store, it initializes one from scratch on its own isolated
`--app-name`.

Require an existing Docker login and a supported local runtime. Login is
shared authentication, not scoped by the isolated app. Run in one shell.

```bash
APP="p-$(date +%s)-$$"  # fresh suffix, at most 20 characters
WORK=$(mktemp -d)
```

## 1. Initialize and inspect the global policy

```bash
sbx --app-name "$APP" policy init balanced
sbx --app-name "$APP" policy ls --wide
```
Pass: `sbx policy ls --wide` shows the balanced preset's rules with resource,
decision, and rule metadata columns.

## 2. Confirm deny-over-allow precedence

```bash
sbx --app-name "$APP" policy allow network example.com
sbx --app-name "$APP" policy deny network example.com
sbx --app-name "$APP" policy check network example.com --verbose
```
Pass: `check network` reports the request would be **denied** — the deny rule
wins even though an allow rule for the same host also exists.

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

## 4. Confirm a service secret never appears in cleartext

```bash
printf 'throwaway-test-value' | sbx --app-name "$APP" secret set anthropic --sandbox policy-check
sbx --app-name "$APP" secret ls --sandbox policy-check --json
```
Pass: `secret ls` lists the entry's service and scope but never the value
itself.

## 5. Confirm registry credential injection scope difference

```bash
printf 'throwaway-token' | sbx --app-name "$APP" secret set --registry ghcr.io --password-stdin
printf 'throwaway-token' | sbx --app-name "$APP" secret set --sandbox policy-check --registry ghcr.io --password-stdin
sbx --app-name "$APP" secret ls --json
```
Pass: two distinct registry entries are listed — one host-only (no
`--all-sandboxes`/`--sandbox`), one scoped to `policy-check` — confirming
`--sandbox` and (if tested) `--all-sandboxes` produce different injection
scopes, never the sandbox filesystem itself.

## 6. Confirm targeted rule removal, not a full reset, is the routine fix

```bash
sbx --app-name "$APP" policy rm network --resource example.com
sbx --app-name "$APP" policy ls --wide
```
Pass: only the targeted rule is gone; every other rule and every other
running sandbox under this isolated app is untouched. Contrast with
`sbx policy reset`, which this runbook never runs against a shared/default
daemon because it deletes the whole policy store and stops every running
sandbox — reserve it for genuinely rebuilding the store from scratch, on an
isolated app you are prepared to lose state on.

## 7. Clean up (consented removal of this runbook's own isolated app and sandbox)

```bash
sbx --app-name "$APP" secret rm --all --force
sbx --app-name "$APP" rm --force policy-check
sbx --app-name "$APP" daemon stop
rm -rf "$WORK"
```

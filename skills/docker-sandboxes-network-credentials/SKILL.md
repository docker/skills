---
name: docker-sandboxes-network-credentials
description: Use this skill when configuring what a Docker Sandboxes (`sbx`) sandbox can reach on the network or which credentials it authenticates with, even if the user just says they want to "let the agent call an internal API", "block all network access", "give the agent a GitHub token", or "use a private registry image for a sandbox". Covers `sbx policy init/allow/deny/ls/inspect/log/check/rm network` (global and per-sandbox egress rules, deny-over-allow precedence) and `sbx secret set/set-custom/ls/rm/import` (service secrets, dynamic secrets via --ref/--command, and registry pull credentials with their host-pulls-only-by-default injection scope).
license: Apache-2.0
compatibility: Standalone `sbx` CLI (not the legacy `docker sandbox` plugin wrapper); local sandboxd commands, not `--cloud` variants. Verified against sbx v0.46.0 (release tag commit 991967dc90ce0d9a440cd1df1bdf3e395c5a2693; 118 frozen CLI reference YAMLs, internal source at that commit, Docker Docs snapshots whose release notes end at 0.45.1). Shipped-binary `--help` parity and runtime behavior were not executed. `docker_help` does not cover standalone `sbx`.
---

# Docker Sandboxes: Network Policy & Credentials

## Overview

This skill owns `sbx policy` (network egress) and `sbx secret` (service
secrets and registry credentials). The proxy enforces egress policy and
injects stored credentials on matching domains. Proxy-managed sentinels
are not usable upstream credentials, but OAuth passthrough can expose real
tokens to the sandbox. Egress policy does not protect a real credential
once leaked outside the sandbox; revoke or rotate a leaked credential.

## When to use this skill

Activate this skill when:
- The user wants to allow, deny, or inspect which hosts a sandbox (or all
  sandboxes) can reach.
- The user wants to give an agent an API key, OAuth token, or other service
  credential without exposing the raw value inside the sandbox.
- The user wants to pull a private template image or kit from a registry
  that requires authentication.
- The user is debugging a blocked network request or a credential that
  isn't being injected.

## Do not use this skill when

Do not use this skill when:
- The task is running `docker agent run --sandbox` or managing its
  `docker agent sandbox` allowlist — use `docker-agent-run`. If the CLI
  is unclear, establish whether the user runs Docker Agent or standalone
  `sbx` before choosing commands.
- The task is creating, reattaching to, or removing a sandbox itself — use
  `docker-sandboxes-lifecycle`.
- The task is declaring secrets/registries/bindings inside a checked-in
  `sbxenv.yaml` file — use `docker-sandboxes-env` for the file format (this
  skill's rules on precedence and injection scope still apply to what that
  file provisions).
- The task is declaring a kit's own `credentials:`/`permissions.network:`
  block in a `spec.yaml` — use `docker-sandboxes-kits` for the schema (this
  skill's model of what those declarations mean at runtime still applies).

## Core guidance

Tables, output shapes, masking thresholds, error messages and checklists are in `references/command-surface.md`; the unexecuted runbook is `checks/verification.md`. Run `sbx` commands only with the user's consent: policy and secret commands change persistent host state.

### Network policy: global, per-sandbox, and precedence

- Initialize the global policy once before the first sandbox: `sbx policy init <allow-all|balanced|deny-all>`. `balanced` is the recommended starting point (typical dev traffic allowed).
- **`init`/`allow` are local-mode setup, not an override of organization policy.** Under organization governance only org allow rules grant access: local allow rules are inactive, local (including per-sandbox) deny rules still apply, org rules are read-only. Diagnose with `sbx policy ls --include-inactive` and `sbx policy inspect`; never promise that a local allow or a reset restores egress.
- **`sbx policy reset` is destructive: it deletes the entire local policy store and stops the daemon and every currently running sandbox.** Never propose it as a first troubleshooting move for one misbehaving rule; use targeted `sbx policy rm network`. Before running it, state that exact impact and get the user's explicit confirmation; `--force` skips only the CLI prompt, not the user's authorization. Its prompt and exit status are not safeguards (the prompt appears only when running sandboxes were detected; a declined prompt returns success in the v0.46.0 source). Do not promise the restart time: help says the next command, the implementation restarts inside the command and then prompts for a preset; if none is set afterwards, run `sbx policy init`.
- Add rules with `sbx policy allow network RESOURCES` / `sbx policy deny network RESOURCES`: comma-separated exact hosts, `*.example.com` and `**.example.com` wildcards, `?` and `[12]`/`[!1]` globs, `:port` suffixes, CIDR prefixes, or `**` for all hosts. Bare `*`, bare IPv6 and `\*` are rejected, not stored. **Always quote** patterns with `*`, `?` or `[` and any `--path` value; write IPv6 as `[2001:db8::1]:443` or `2001:db8::1/128`.
  ```bash
  sbx policy allow network "api.example.com,cdn.example.com"
  sbx policy deny network ads.example.com
  ```
- **UDP is experimental and off by default.** Use `--protocol udp` or `--protocol tcp,udp` (not `--proto`). Allow rules default to TCP; deny rules to both transports. It also needs host-wide experimental settings (`platform.allowExperimentalFeatures`, `feature.udp-egress`): ask first, never flip them just to make a rule appear to work. UDP is refused for proxied destinations; ICMP stays blocked. Check with `sbx policy check network --protocol udp api.example.com:443`.
- HTTP method/path qualifiers (`--method`, `--path`) are flags on the same `network` commands, never separate `http` verbs. The v0.46.0 help export omits them: confirm they exist on the user's binary first. They apply only to traffic the forward proxy inspects (not opaque TCP such as SSH), and `policy check network` evaluates host and port only.
- **Deny always wins over allow** for the same hostname/CIDR. An allowed hostname is not checked against CIDR deny rules for its resolved IP.
- A rule is global by default; `--sandbox NAME` scopes it to one sandbox. At **creation time only**, `sbx create`/`sbx run` accept repeatable `--deny-network RESOURCE`; a local deny only narrows, never widens, egress (for example `sbx policy allow network --sandbox my-sandbox api.example.com`).
- `sbx policy check network [--sandbox NAME] TARGET` tests the **current** policy (for example `sbx policy check network --sandbox my-sandbox api.example.com:443`); `sbx policy log [SANDBOX] [--json] [--limit N]` shows what was actually allowed or blocked, with the matching rule (no `-v`). `sbx policy ls --wide` shows rule IDs; filters include `--source`, `--decision`, `--type`, `--protocol`, `--include-inactive` and `--created-via default|added|provisioned|approval`. `sbx policy inspect` gives each rule's exact removal command or why it is read-only (for example `sbx policy ls --wide --created-via approval`).
- `sbx policy rm` has one kind, `network`, and needs `--id` (a RULE_ID, local rules only, not a name) or `--resource`. `--resource` can match more than one rule (for example an allow and a deny): read the confirmation naming scope and selectors (`--force` skips it). Retain `--sandbox NAME` for sandbox-scoped rules; omitting it targets the global policy. Other rules still apply, so check both scopes afterwards:
  ```bash
  sbx policy rm network --sandbox my-sandbox --resource api.example.com
  sbx policy check network --sandbox my-sandbox api.example.com
  ```

### Service secrets: how injection works

- `sbx secret set [SERVICE]` stores a credential the **proxy** uses to authenticate outbound requests for the agent. In the normal proxy-managed flow the sandbox sees a sentinel; the proxy substitutes the real value on requests to the domains the matching kit/binding declares.
  ```bash
  sbx secret set github                       # interactive
  printf '%s' "$ANTHROPIC_API_KEY" | sbx secret set anthropic
  ```
  **Storing a secret does not grant network access.** Check the target domain in the intended scope before debugging authentication: `sbx policy check network --sandbox my-sandbox api.anthropic.com`.
- **OAuth passthrough gives no token-less guarantee.** When a kit sets `oauth.passthrough: true` without a refresh sentinel, the proxy forwards the real token response to the sandbox; the built-in `devin` kit does this. Check the kit's OAuth configuration before saying an agent cannot read a token, and do not enable passthrough to bypass an authentication failure. Even with sentinels the agent can use the credential's permissions on allowed services: restrict token privileges too.
- Service secrets are global by default; `--sandbox NAME` scopes one and takes precedence over the global secret, so removing the scoped one can expose the global one again. `--oauth` is openai/global only.
- Host environment variables never auto-inject: a secret reaches sandboxes only after `sbx secret set` or `sbx secret import` stored it.
- Third-party kits need an approved credential binding; built-in kits do not. Unattended or `--detached` starts without one withhold the credential and only warn. Do not approve an untrusted kit to make authentication work. `secret set` has no `--type` or `--binding` flag.

### Dynamic secrets: host execution, refresh, revocation

- `--ref` (1Password `op://...` or AWS Secrets Manager ARN; needs an authenticated `op`/`aws` CLI) or `--command` (host shell command; stdout is the value) stores a source that sbx resolves on the host.
  ```bash
  sbx secret set anthropic --ref 'op://Private/Anthropic/api-key'
  sbx secret set github --command 'gh auth token'
  ```
- **Never treat host helper execution as harmless.** The source runs with the user's host privileges at registration-time verification and at every refresh, from a **fresh temporary directory** (v0.46.0): `./helper` or a bare script name does not resolve against the project. Use an absolute helper path or a helper on an absolute `PATH` directory.
- Keep the helper, everything it loads, the host temporary directory and `PATH` entries outside writable sandbox mounts, including mounts added later with `sbx mount`. sbx does not copy, inspect or confine helpers; a fresh working directory is not confinement. Reject sandbox-influenced paths. Checklist: `references/command-surface.md`.
- `--no-verify` skips only the initial check, not the trust requirement; `--show-error` can print secrets. Offer neither as a blanket fix.
- **`--refresh` is cache policy, not revocation.** Service default `55m`, custom `on-demand`. A rotated value can be served from cache until the window ends; removing the source does not revoke the upstream credential.

### Literal values and custom secrets

- **Never pass a secret as a plain `--env` value or as a `--kit-arg` / `--env-arg` value.** Both land as literal, unmasked text — in the sandbox's environment, in `sbx env plan`'s state file, and potentially in shell history. Use `sbx secret set` (or `sbxenv.yaml`'s `secrets:`/`registries:` blocks, which route through the same store).
- `secret set --token/-t` and `set-custom --value/--token` put the literal in shell history and process listings: prefer the prompt, stdin (`printf '%s' ...`) or `--ref`. Never write a credential into `--command`, `--ref` or `--token` text: command text is stored and replayed by the daemon, and a dynamic custom record's source text is shown by `secret ls`.
- `sbx secret set-custom` (experimental) covers a service sbx has no built-in support for: the sandbox sees a placeholder in the env var you name (`--env`), and the proxy swaps in the real secret only on requests to the quoted `--host` pattern(s). Global by default; `--sandbox NAME` scopes one.

### Listing, importing and OAuth shadowing

- `sbx secret ls [--global|--sandbox NAME] [--service NAME] [--json]` never prints a full literal but is **not metadata-only**, and the mode matters. Default listing (no `--service`) shows service rows as `(stored)` or an OAuth label, registry and custom literals as masked previews, and dynamic **custom** records with their source text. `--service NAME` shows a masked preview of a literal service secret: first six characters, plus last four at 20+ characters (`throwaway-test-value`, 20 characters, renders as `throwa**********alue`). There is no `-v`. Use synthetic fixtures, never paste real listing output into logs, and never infer injection from a listing.
- `sbx secret import [SERVICE] [--all] [--dry-run] [--force]` reads supported host variables and **always writes to the global scope**; use `secret set --sandbox NAME` for one sandbox. `--all` skips a differing stored value, `--force` overwrites, neither bypasses the OAuth-shadow skip (a service with an OAuth token is skipped). Switching to an API key needs `sbx secret rm SERVICE` first, which also removes the OAuth token: confirm with the user. Start with `--dry-run`.

### Removing secrets: confirmation, missing targets, scoped inverse

- `sbx secret rm SERVICE` targets the global scope; `--sandbox NAME` a sandbox-scoped secret (for example `sbx secret rm openai --sandbox my-sandbox`; global removal leaves scoped ones); `rm` alone opens a picker.
- `sbx secret rm --all` removes every stored secret of every kind and scope and takes no `SERVICE`, `--sandbox` or `--registry`. Get explicit confirmation naming that blast radius. `--force` skips only the CLI prompt: use it for disposable, user-approved cleanup, not as a shortcut.
- A missing target is an **error** unless `--force` is given; with `--force` it re-runs revocation reconciliation and can succeed, so success does not prove a secret existed.
- Removal is reconciliation, not guaranteed instant revocation. Existing local sandboxes update without a restart, but live revocation can fail after the stored value is deleted: retry with `sbx secret rm --force -- SERVICE`, or for a scoped secret `sbx secret rm --sandbox NAME --force -- SERVICE` (options go before `--`). An HTTP failure or timeout can leave cached credentials usable, and another applicable source may stay effective. Do not say a restart is always required or that deletion proves every sandbox lost access; it never revokes the upstream token.
- Custom-secret removal has no exported public flag at v0.46.0. The implementation has **hidden** `--host`, `--env`, `--placeholder` on `secret rm`. Treat them as internal and version-pinned, not a stable recipe; do not propose them by default. Identify the record with `sbx secret ls --json`, prefer the interactive picker (whether it lists custom records: verify locally), and confirm afterwards that only that record is gone.

### Registry credentials: host-pulls-only by default, two distinct injection scopes

- `sbx secret set --registry HOST --password-stdin` (optionally `--username`) stores **pull** credentials for private template images and kit artifacts. **Unlike service secrets, registry credentials are host-only by default: they authenticate pulls on the host and are never injected into any sandbox.** Docker Hub uses the `sbx login` session.
  ```bash
  gh auth token | sbx secret set --registry ghcr.io --password-stdin
  ```
- **`--all-sandboxes` and `--sandbox` widen this differently — do not confuse them:**
  - `--all-sandboxes`: host pulls **and** proxy injection into **every new sandbox's** registry login (the credential never enters the sandbox filesystem). Existing sandboxes do not pick it up; use `--sandbox`.
  - `--sandbox NAME`: injected into **that one sandbox only**.
  - Neither flag: host-pulls-only, injected nowhere.
  ```bash
  gh auth token | sbx secret set --all-sandboxes --registry ghcr.io --password-stdin
  gh auth token | sbx secret set --sandbox my-sandbox --registry ghcr.io --password-stdin
  ```
- Host-only and all-sandboxes entries for one host compete: saving one deletes the other; a sandbox-scoped entry can coexist. Prefer `--sandbox`.
- For a Bearer auth endpoint on another host, pass `--registry-auth-endpoint` with the exact trusted HTTPS URL; the registry's own host and built-in relationships (for example Docker Hub) need no flag, other realms are rejected.
- `sbx secret rm --registry HOST --sandbox NAME` removes only that sandbox's registry credential; host-only and global entries are untouched. This does not revoke the upstream token or prevent use of another applicable credential. Without `--sandbox`, `sbx secret rm --registry HOST` removes both the host-only and global entries; add `--all-sandboxes` to remove only the global entry (it requires `--registry`). Example: `sbx secret rm --registry ghcr.io --sandbox my-sandbox`.

## Related skills

- For `docker agent run --sandbox` and `docker agent sandbox` commands, use `docker-agent-run`.
- For creating, reattaching to, and removing the sandboxes these policies and secrets apply to, use `docker-sandboxes-lifecycle`.
- For declaring `secrets:`/`registries:`/`bindings:` inside a checked-in `sbxenv.yaml` file that provisions them at environment-create time, use `docker-sandboxes-env`.
- For v2 `spec.yaml` kit authoring, including a kit's own credential and network declarations (what a kit *asks for*, as opposed to what the user has *approved*), use `docker-sandboxes-kits`. For v3 kit-format questions it states that v3 descriptors are a separate format it does not cover. This skill owns only what the resulting rules and credentials mean at runtime.

## References

- `references/command-surface.md` — v0.46.0 flag tables, pattern forms, masking thresholds, `secret ls --json` fields, confirmation and error behavior, host-helper and registry checklists, hidden custom-mode flags.
- `references/sources.md` — provenance for every rule above (release record, help captures, docs sections, internal paths and excerpts).
- `skill.yaml` — routing metadata (frozen activation contract).
- `agents/openai.yaml` — Codex discovery metadata.

## Assets

- None.

## Checks

- `checks/verification.md` — Verification runbook for network policy and secret commands (unexecuted runbook; run manually with an isolated `--app-name`, no real secret values, no real helper commands).

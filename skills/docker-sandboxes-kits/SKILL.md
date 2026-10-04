---
name: docker-sandboxes-kits
description: >-
  Use this skill when authoring, validating, packaging, signing, or composing a Docker Sandboxes kit `spec.yaml` (`sbx kit add/inspect/pack/pull/push/sign/validate/verify`), even if the user just says they want to "add a tool to a sandbox agent", "build a reusable sandbox extension", "publish a kit to a registry", or "give a mixin its own credentials and network access". Covers the kit-spec v2 grammar (`kind: sandbox` vs `kind: mixin`, the `sandbox:` block, `permissions.network`, `ports`, `credentials` apiKey/oauth, `environment`, `setup` install/startup/files, `volumes`, `args`, `extends`, `mixins`, `requires.agent`), composition via `--kit`/`sbx kit add`, and distribution (pack/push/pull/sign/verify/provenance).
license: Apache-2.0
compatibility: Requires standalone sbx with sbx kit support and kit-spec schemaVersion "2", not the legacy docker sandbox wrapper. Verified against sbx v0.46.0 (docker/sandboxes 991967dc90ce0d9a440cd1df1bdf3e395c5a2693); no installed binary was used as oracle. Provenance is in references/sources.md. docker_help does not cover standalone sbx.
---

# Docker Sandboxes: Kits (spec.yaml)

## Overview

A **kit** is a directory (or ZIP/OCI/git artifact) containing a `spec.yaml`
plus an optional `files/` tree. `sbx` composes a kit into a running or
about-to-be-created sandbox at `sbx create`/`sbx run --kit`/`sbx env` time or
at `sbx kit add` time. This skill owns kit-spec v2 authoring, validation, and
distribution — everything under `spec.yaml`'s own grammar — and defers what a
kit's declarations *mean at runtime* (credential injection, network
enforcement) to `docker-sandboxes-network-credentials`, and the sandboxes a
kit is composed into to `docker-sandboxes-lifecycle`.

Scope is schema v2 at sbx v0.46.0. v2 remains supported and the built-in
agents (`claude`, `codex`, `shell`, …) are v2 kits. V3 workloads and mixins
exist, cannot be combined with v1 or v2 kits, and are not covered here; do not
apply this skill's rules to v3 descriptors.

## When to use this skill

Activate this skill when:
- The user wants to write, validate, or pack a `spec.yaml` for a `kind:
  sandbox` (complete agent) or `kind: mixin` (extension) kit.
- The user wants a mixin to add a tool, credential, network allowance, or
  files to an existing built-in agent.
- The user wants to publish a kit to (or pull one from) an OCI registry,
  sign it, or verify a signature/provenance attestation.
- The user is debugging a kit-validation error, an argument-substitution
  error, or `sbx kit add`'s recreate-aware requirement.

## Do not use this skill when

Do not use this skill when:
- The task is creating/running/removing the sandbox a kit is composed into,
  independent of the kit's own content — use `docker-sandboxes-lifecycle`.
- The task is what a credential or network rule a kit declares actually
  does at runtime (proxy injection, allow/deny precedence, or what the
  CURRENT network/global policy already permits), or is about secrets/
  policy that have nothing to do with a kit — use
  `docker-sandboxes-network-credentials`.
- The task is the `sbxenv.yaml` file format that references kits via its
  own `kits:` block — use `docker-sandboxes-env` for that file's schema
  (this skill still owns what goes inside the referenced kit itself).

## Core guidance

### `kind: sandbox` vs `kind: mixin` — pick the right one

- Exactly one `kind: sandbox` kit composes into any sandbox (a complete
  agent: base image + launch config). Any number of `kind: mixin` kits
  layer onto it (tools, credentials, network, files). A mixin **must not**
  declare a `sandbox:` block, `extends:`, or `mixins:`.
- Every v2 kit needs `schemaVersion: "2"` (v1 is still accepted; v3 is a
  separate format), `kind`, and `name` matching
  `^[a-z0-9]([a-z0-9-]{0,62}[a-z0-9])?$`.
- Decoding is strict at the grammar level but **not a typo guarantee**: the
  v2 decoder uses YAML `KnownFields(true)`, so an unknown key in a plain block
  (e.g. `permissions.netwrok:`) is a decode error, yet a block with its own
  unmarshaler (e.g. the `sandbox.command` mapping) may ignore unknown keys
  (verify locally). A passing `sbx kit validate` never proves a typo-free spec.
  `assets/spec-mixin.yaml` is a complete minimal mixin.
- Do not redefine a base agent's credential in a mixin: declaring a new
  `apiKey.name` or `proxyManaged` for the same service fails composition.
  `shell`, `docker-agent`, and `opencode` already own `github`. An additive
  routing-only entry (`apiKey.inject`, no name/proxyManaged/oauth, and
  `required: false`) can extend the base credential instead. OAuth belongs
  on sandbox kits, never v2 mixins. See `references/spec-v2-fields.md`.
  Inspect built-in definitions at `sandboxlib/agentkits/agents/<agent>/spec.yaml`
  in the pinned source; `sbx kit inspect` takes artifact references, not
  built-in names. Standalone mixin validation does not test composition.

### The `sandbox:` block (sandbox kits only)

- **Required** for `kind: sandbox` (unless the kit `extends:` a parent that
  already supplies it); **forbidden** for `kind: mixin`.
- `image:` is the pre-built base image. `entrypoint:` is the fixed process
  prefix (`entrypoint[0]` is the binary); `command:` is the mode-specific
  argument tail — either a bare list (sets `default`, `interactive` falls
  back to it) or `{default: [...], interactive: [...]}`. With `extends:`,
  `sandbox.command` **replaces** the inherited tail rather than appending.
- `sandbox.build:` (Dockerfile build) is **accepted but not built by the
  runtime at v0.46.0** — a kit that sets `build:` must still set `image:`,
  or it is rejected at load with an actionable error.
- **`extends:` is the simplest way to get a real, working image without
  inventing one.** A sandbox kit that extends a built-in agent (e.g.
  `extends: shell`) inherits its real `sandbox.image` and may omit `sandbox:`;
  `assets/spec-sandbox.yaml` does exactly this.

### Egress: `permissions.network` — and the all-egress-declared rule

- `permissions.network.allow`/`deny` are the v2 home for what v1 spelled as
  top-level `network:`. Shapes the pinned runtime lowers and matches (source
  evidence, not live-observed): exact host, exact host+port, `host:*` (all
  ports), `*.example.com` (one label), `**.example.com` (multi-label), and CIDR
  prefixes. Public kits-v2 calls `**.`, `:*`, port ranges and CIDR "pending";
  SPEC-v2 calls `**.` and `:*` enforced but CIDR and port ranges not: the
  sources disagree and the pinned implementation decides. A port range such as
  `host:80-443` never matches (ports compare exactly); use separate exact ports.
  **Deny wins within one identifier type; across identifiers evaluation is
  first-decisive, domain then resolved IP.** A decisive domain allow or deny
  is final: an allowed hostname is not checked against a CIDR deny, and a
  hostname deny is not overridden by a CIDR allow. Never rely on a CIDR deny
  to block an allowed hostname; never claim a universal cross-identifier
  deny-wins. `assets/spec-mixin.yaml` shows an `allow` entry.
- **`permissions.network.allow` is additive across a composition, and a
  kit's own allow list is not the only thing granting a sandbox egress.**
  The sandbox also carries the base agent's allow list and whatever the
  *global* or *per-sandbox* policy (`sbx policy`) permits — see
  `docker-sandboxes-network-credentials`. **Removing a host from one kit's
  `allow` does not by itself prove that host is blocked** (`balanced` allows
  common registries and AI services; `allow-all` allows everything). Never
  claim a host is blocked without `sbx policy check network --sandbox <name>
  <host>` on a real sandbox; it evaluates host/port, not HTTP method or path.
- Declare the egress a kit requires, including every
  `credentials[].apiKey.inject[].domain` (public kits-v2: an inject domain
  "must also be allowed in `permissions.network`"). Credential injection does
  not itself grant access; `sbx kit validate` only warns when an inject domain
  is missing from the kit's own allow list and proves nothing about effective
  policy or reachability. Check the effective decision.
- A kit `allow` is declared intent, not an administrator bypass: it is
  provisioned as a TCP allow (a kit `deny` as TCP+UDP) and stays inactive
  while remote governance applies (user/local permits are dropped, denies
  survive). List kit rules with
  `sbx policy ls <SANDBOX> --source kit --include-inactive`. Effective-policy
  semantics belong to `docker-sandboxes-network-credentials`.

### `credentials` — what the kit needs, never how the user stores it

- Each entry declares a `service` identity and **where to inject** the
  resolved value (`apiKey` and/or `oauth`); it never declares *how* the
  user obtains or stores the credential — that lives in the user's own
  bindings file, wired through `sbx secret set` (see
  `docker-sandboxes-network-credentials`). A declaration requests; a user
  binding authorizes. An unbound `required` credential starts withheld.
- `apiKey.inject[]` needs a `domain` and either an explicit `header`+
  `format` (`format` must contain exactly one `%s`) or the `scheme:`
  sugar: `scheme: bearer` expands to `Authorization: Bearer %s` (no
  `username`); `scheme: basic` requires `username`, is mutually exclusive
  with `format`, leaves `header` empty in the normalized kit, and the proxy
  builds `Authorization: Basic`. **Pick a `service` name no composed base
  agent already declares** (duplicate-service rule above); see
  `references/spec-v2-fields.md` for a complete fragment.
- `apiKey.proxyManaged: true` sets the in-container env var to the literal
  `proxy-managed` sentinel rather than leaving it unset; the real value is
  substituted only by the proxy, on the allow-listed inject domains.
- `oauth` needs `tokenEndpoint.host`/`.path` and, unless
  `passthrough: true`, non-empty `sentinels.accessToken`/`.refreshToken`.
  `passthrough: true` is a **security downgrade** — the real token reaches
  the container instead of a sentinel — use it only when the kit's own
  design requires it and say so in `description`.

### `setup` — install (once) vs. startup (every start) vs. files (startup-time writes)

| Block | Command shape | Runs |
|---|---|---|
| `setup.install[].command` | **string**, via `sh -c` | Once, synchronously, before the agent first launches. Runs for every kit, built-in or not. |
| `setup.startup[].command` | **list<string>**, exec-style (no shell) | On **every** container start (create, stop/start, daemon restart, host reboot) — **must be idempotent**. |
| `setup.files[]` | file write via shell exec | At sandbox start, after install and before startup commands are registered; `path` absolute; only `${WORKDIR}` allowed in `content`. |

Optional fragment for the shell kit in `assets/spec-sandbox.yaml`:
```yaml
setup:
  startup:
    - command: ["sh", "-c", "mkdir -p ~/.my-kit"]
  files:
    - path: /home/agent/.my-kit/config.json
      content: '{"workdir": "${WORKDIR}"}'
```
- **`setup.files` is not the static `files/` directory tree.** `setup.files`
  are dynamic, `${WORKDIR}`-substituted writes; `files/home/` and
  `files/workspace/` are static files copied in at create time, and only
  `files/workspace/` is written **after** the workspace is populated (e.g.
  after an in-container `git clone` under `--clone`). Order: network/env,
  `files/home/`, install, `setup.files`, startup registered, `files/workspace/`;
  stacked kits follow `--kit` order within each stage.
- Default execution users: install as root (`user: "0"`) unless overridden;
  startup/entrypoint as the agent user (uid `1000`) unless overridden.
  Root install steps writing under `/home/agent` **must** `chown` it back to
  `agent:agent`, or later agent-user writes there fail.
- `setup.startup` is non-interactive (no TTY, cannot prompt) and does not gate
  the agent entrypoint: the agent launches once startup commands are
  dispatched, whatever `background` says. Put prerequisites the agent needs at
  launch in the image, `setup.install`, or `setup.files`. Use
  `background: true`, not a trailing `&`, for a service.
- Install commands start in the image `WORKDIR`, not necessarily the
  workspace; use absolute paths.

### `volumes` — creation-time only, every volume must set a size

- Each entry needs an absolute `path:`, optional `type: tmpfs` (RAM-backed;
  omit/`""` for the default block-backed volume), optional `size:`
  (byte-size string) and `mode:` (octal).
- **Volumes apply only at sandbox-create time.** `sbx kit add` recreates the
  sandbox and **refuses** a kit that declares `volumes:` (it neither applies
  nor skips them): create the sandbox with the kit. Existing kit volumes and
  the workspace are preserved across an add.
- **Always set `size:` on a block volume.** An unsized volume inherits a
  50 GiB default and costs real host disk immediately (ext4 inode-table
  zeroing); 512 MiB is the practical floor — below it `mke2fs` switches
  inode density and the space savings mostly disappear.

### `args` — parameterizing a kit

- Declare under top-level `args:` (v2 only), each with exactly one of
  `default`/`required: true`, plus optional `description`/`enum`/`pattern`.
  Reference with `${{ kit.args.NAME }}` in `spec.yaml` or `files/`;
  substitution happens **before** decoding, and every reference **must** be
  declared or loading fails. **Quote a placeholder used in a string field**
  (`VERSION: "${{ kit.args.version }}"`), or a numeric-looking value fails to
  decode into a string field.
- Supply values with `--kit-arg name=value` (every kit) or
  `--kit-arg kitname.name=value` (one kit only), or `--kit-args-file`.
  **Never pass a secret this way** — values are not masked, stay in shell
  history and are unencrypted in args files; see
  `docker-sandboxes-network-credentials`.

### `extends` and `mixins` — composition, not runtime injection

- `extends:` resolves only embedded built-in agent names at v0.46.0
  (`shell`, `claude`, etc.). A git/OCI/ZIP/directory reference in `extends:`
  is not dispatched, even if pinned, although SPEC-v2 describes "a pinned
  remote ref". `assets/spec-sandbox.yaml` uses `extends: shell`.
- `mixins:` inside a spec is accepted with a "not yet applied" warning and is
  not composed (public kits-v2: runtime composition "is pending"). Compose
  mixins with `--kit` (applied at create/run) or `sbx kit add`.
- `--kit` and `sbx kit *` references dispatch by form: directory, ZIP,
  `oci://` or `registry/repo:tag`, `git+https://`/`git+ssh://` with
  `#ref=`/`dir=`. Prefer digest/commit-pinned references; mutable tags and
  branches are still accepted. Only commit-SHA-pinned git refs can be
  engine-"vouched" (an admission exemption for built-ins extracted into kits),
  which is not a user pinning feature.
- `requires.agent` (mixin-only; **rejected** on `kind: sandbox`) pins the
  single base agent a mixin is designed for (e.g. Claude-specific env
  vars). It is well-formedness-checked by the spec library; the actual
  agent-affinity mismatch is enforced by the composition consumer, not by
  `sbx kit validate` alone.

### Validating, packaging, and distributing

| Command | Purpose |
|---|---|
| `sbx kit validate REFERENCE [--json] [--kit-arg ...]` | Help says "directory or ZIP" but local directory, ZIP and git references load; OCI is rejected up front. Schema-only. **Never composes against a base agent** — cannot catch a duplicate-service collision, confirm a domain is reachable, or prove the spec typo-free. |
| `sbx kit inspect REFERENCE [--kit-arg ...] [--json]` | Loads (local, ZIP, OCI or git; source policy applies, remote content is fetched) and prints the artifact in v2 grammar with `--kit-arg` substitution. Ordinary loads keep `extends` and do not inherit the parent image; a signature-vouched pinned-git load resolves and clears it. Not raw YAML, not composed output. |
| `sbx kit pack DIRECTORY [-o OUTPUT.zip]` | Validates and packages a directory as a ZIP. ZIP kits cannot carry verifiable signatures. |
| `sbx kit pull REFERENCE [-o OUTPUT]` | Pulls a kit's raw layer payload from an OCI registry without composing it. |
| `sbx kit push DIRECTORY REGISTRY/REPO:TAG [--sign]` | Packages and pushes; every push attaches an unsigned-by-default SLSA provenance attestation. |
| `sbx kit provenance REFERENCE [--certificate-identity ...]` | Prints the attestation `push` attached; marked UNSIGNED unless verified against a matching key/identity. |
| `sbx kit sign REFERENCE` / `sbx kit verify REFERENCE` | Sigstore sign/verify (keyless by default); prefer `--identity-token-file` over `--identity-token`. |
| `sbx kit add SANDBOX REFERENCE [--kit-arg ...]` | **Recreates** an existing sandbox with a mixin appended, not live injection. Accepts only `environment.variables`, `setup.install` and `permissions.network.allow`; refuses startup, `setup.files`, static files, volumes, resources, `security.privileged`, ports, network `deny` and credentials. Needs the original-kit label; refused for legacy worktree sandboxes. |

See `references/kit-distribution-commands.md` for full flag lists, the add
refusal table, recovery warnings and worked examples.

- After `sbx kit add` read every warning (withheld credentials, runtime
  mounts that failed to replay, "record could not be saved": a daemon restart
  would revert the kit set); live success alone is not durable. Removing a
  mixin means recreating the sandbox; never `sbx rm` without user consent.
- Source policy applies to every load: `kit.allowedSources`,
  `kit.allowLocalKits`, `kit.requireSignature`, `kit.trustedSigners`. Set
  trusted signers before requiring signatures; never change these settings
  without user approval. A signature covers `spec.yaml` and `files/`, not
  image tags or install/startup downloads; `verify`/`provenance` success does
  not make content benign.

## Related skills

- For the sandboxes a kit is composed into (`sbx create`/`run --kit`,
  `sbx kit add SANDBOX`), use `docker-sandboxes-lifecycle`.
- For what a kit's `credentials:`/`permissions.network:` declarations mean
  at runtime — proxy injection, allow/deny precedence, the effective
  policy a sandbox actually has once global/per-sandbox policy is
  included, where the user stores the actual secret value — use
  `docker-sandboxes-network-credentials`.
- For the `sbxenv.yaml` file whose `kits:`/`agent:` fields reference a kit
  by this schema, use `docker-sandboxes-env`.

## References

- `skill.yaml` — routing metadata; `agents/openai.yaml` — Codex discovery interface (both frozen at v2 scope).
- `references/sources.md` — claim-level provenance for every rule above (sbx v0.46.0 help fields, public kits-v2 sections, pinned internal `path:symbol` excerpts, removed/disagreeing sources).
- `references/spec-v2-fields.md` — the complete v2 field table (common fields, sandbox-only fields, mixin-only fields, shared blocks) for lookup without re-reading the full spec.
- `references/kit-distribution-commands.md` — full flags, add refusal table, trust admission and worked examples for `sbx kit validate/inspect/pack/pull/push/provenance/sign/verify/add`.

## Assets

- `assets/spec-sandbox.yaml` — a genuine minimal `kind: sandbox` kit that `extends: shell` to inherit a real, working image rather than inventing one.
- `assets/spec-mixin.yaml` — a genuine minimal `kind: mixin` kit with no credentials at all (an egress-only extension), which composes cleanly with every built-in agent.

## Checks

- `checks/verification.md` — Schema, strictness, composition, egress, kit-add acceptance/refusal and inspect checks (unexecuted integration runbook; isolated hidden `--app-name`, no registry publishing or signing).

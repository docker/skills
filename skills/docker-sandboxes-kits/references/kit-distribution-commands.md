# Kit distribution and inspection commands: full reference

Verified at sbx v0.46.0 (docker/sandboxes `991967dc90ce0d9a440cd1df1bdf3e395c5a2693`):
flags and synopses come from the v0.46.0 `sbx kit *` help exports (no installed
binary was used as oracle); behavior comes from the public kits-v2 sections and
the pinned internal `path:symbol` excerpts listed in `references/sources.md`.
`sbx kit` is EXPERIMENTAL. None of the nine commands below has a `--yes` flag
(in the v0.46.0 exports `--yes` appears only on `sbx kit builder history rm` and
`sbx logout`; `sbx kit builder ...` is outside this skill).

## Reference forms

A reference is a local directory, a ZIP file path, an OCI reference
(`registry/repo:tag`, `registry/repo@sha256:...`, or `oci://...`; Docker Hub
kits may omit `docker.io/`), or a git URL (`git+https://` or `git+ssh://`,
with `#ref=<rev>` and `#dir=<path>` fragments; quote URLs containing `&`). Start
relative paths with `./` or `../`. A missing local-looking path is an error, not
an OCI lookup. Which command accepts which form:

| Command | Accepted references |
|---|---|
| `validate` | local directory, ZIP, git (OCI rejected before loading) |
| `inspect`, `add`, `create/run --kit` | directory, ZIP, OCI, git |
| `pack`, `push`, `sign` (local) | a directory |
| `pull`, `provenance` | an OCI reference |
| `sign`, `verify` | directory, OCI; `verify` also a git reference |

Source policy (`kit.allowedSources`, `kit.allowLocalKits`, `kit.requireSignature`,
`kit.trustedSigners`) is applied to every load. Changing those settings is the
user's decision; this skill never changes them.

## `sbx kit validate REFERENCE [flags]`

Help text says "Validate that a directory or ZIP file is a valid kit artifact",
and then "The reference can be a local directory, ZIP file path, or git
repository". The command accepts all three and rejects OCI references up front
("OCI references are not supported for validation; use a local directory or ZIP
file"). A kit with required arguments is invalid until the same `--kit-arg`
values `sbx create` would need are supplied.

It loads through the source policy with the built-in `extends` resolver and
without a v3 builder, then runs the Basic-auth username check. With `--json` it
prints `{reference, kind, valid, error?, warnings[]}` and still exits non-zero
for an invalid kit: the exit code is the pass/fail signal.

**This checks schema well-formedness only.** It never composes the kit against
a base agent, so it cannot catch a duplicate-service credential collision (see
SKILL.md's `kind: sandbox` vs `kind: mixin` section), confirm a domain is
reachable, or prove a spec is typo-free (see `references/spec-v2-fields.md`,
"Decoding strictness"). Composition needs `sbx create --kit`/`sbx run --kit`,
followed by a policy check.

Flags: `--json`, `--kit-arg`, `--kit-args-file`.

## `sbx kit inspect REFERENCE [flags]`

Loads and prints the artifact **before** composing it into any sandbox. Use it
to confirm declared credentials, network rules and setup commands, or to
preview a parameterized kit with specific `--kit-arg` values (the output shows
the substituted content). Remote references are fetched, subject to the source
policy; inspecting an untrusted reference is a fetch, not a dry run.

The output is the loaded artifact projected into v2 grammar (`spec.V2View`),
plus load-time `warnings` and the `files[]` tree. It is not the raw YAML and not
a fully composed result:

- Ordinary loads keep `extends` (the field is omitted only when empty) and do
  not copy the parent image into `sandbox.image`.
- Exception (signature-vouched load): when `kit.requireSignature` is on and the
  reference matches an engine-vouched, commit-SHA-pinned git reference, the loader resolves
  `extends` against the built-in agents before the content check, clears it and
  can show the inherited `sandbox.image`. A failed content check is an error,
  not output.
- Never treat either shape as proof of image availability, credentials or
  egress.

```bash
sbx kit inspect ./my-mixin/ --kit-arg version=1.2.3
```

Flags: `--json`, `--kit-arg`, `--kit-args-file`.

## `sbx kit pack DIRECTORY [flags]`

Validates and packages a directory (with its `spec.yaml` and optional `files/`)
as a ZIP. ZIP kits cannot carry verifiable signatures, and `kit.requireSignature`
rejects them; `kit.allowLocalKits` also governs ZIP files.

Flags: `-o`/`--output` (default `<name>.zip`).

## `sbx kit pull REFERENCE [flags]`

Pulls a kit artifact from an OCI registry (HTTPS) and saves its raw layer
payload to a file (`.zip` for `schemaVersion: "1"`, `.tar.gz` for `"2"`)
without composing it, so it is useful to inspect or archive a published kit's
exact bytes. Authentication prefers an `sbx secret set --registry` credential,
falling back to the Docker credential store.

```bash
sbx kit pull ghcr.io/org/my-mixin:1.0
```

Flags: `-o`/`--output`.

## `sbx kit push DIRECTORY REGISTRY/REPO:TAG [flags]`

Packages and pushes (publication: only with explicit user approval); every push
also attaches an **unsigned-by-default** SLSA provenance attestation naming the
kit's content digests, declared image, and source git commit when the directory
is a working tree. Pass `--sign` for a Sigstore-signed manifest and signed
attestation (keyless by default; `--key` for key-based). Authentication: the
Docker Hub session from `sbx login` and `sbx secret set --registry` credentials
take priority, then the Docker credential store.

Flags: `--sign`, `--key`, `--identity-token`, `--identity-token-file`,
`--tlog-upload` (default `true`).

## `sbx kit provenance REFERENCE [flags]`

Prints the SLSA provenance attestation `sbx kit push` attached to an OCI kit.
Printed as-is and marked **UNSIGNED** unless it was pushed with `--sign` and you
pass matching `--key` (key-based) or `--certificate-identity`/
`--certificate-oidc-issuer` (keyless) here; only an attestation that verifies
and whose subject matches the kit's digest is reported **VERIFIED**. Verification
does not prove the kit's contents or dependencies are benign.

```bash
sbx kit provenance ghcr.io/org/my-mixin:1.0 \
  --certificate-identity user@example.com \
  --certificate-oidc-issuer https://accounts.google.com
```

Flags: `--json`, `--key`, `--certificate-identity`,
`--certificate-identity-regexp`, `--certificate-oidc-issuer`,
`--certificate-oidc-issuer-regexp`, `--insecure-ignore-tlog`.

## `sbx kit sign REFERENCE [flags]` / `sbx kit verify REFERENCE [flags]`

**Sign** a local directory (writes a `kit.sig.bundle` sidecar next to
`spec.yaml`) or an OCI kit (Sigstore bundle as an OCI referrer); any other
reference kind is refused (`SignReference`). **Verify** a directory (checks the
sidecar), an OCI kit, or a git reference (clones the repository and checks its
committed sidecar); a git checkout is verified, never signed in place. Prefer
`--identity-token-file` over `--identity-token` for keyless signing: process
arguments are readable by other local users and recorded in shell history. A
token is never read from `SIGSTORE_ID_TOKEN`. Key-based signing needs an
unencrypted ECDSA P-256 PEM private key that is not readable by group or others.
`--tlog-upload=false` skips the Rekor log for private keyless kits and needs
`--insecure-ignore-tlog` when verifying, **and** needs a signing config that
provides a timestamp authority: a keyless bundle with no observer timestamp is
refused at signing time rather than emitted unverifiable. For fully offline or
private testing, prefer key-based signing with `--key` (ephemeral keys).

Flags (sign): `--key`, `--identity-token`, `--identity-token-file`,
`--tlog-upload`.
Flags (verify): `--key`, `--certificate-identity`,
`--certificate-identity-regexp`, `--certificate-oidc-issuer`,
`--certificate-oidc-issuer-regexp`, `--insecure-ignore-tlog`, `--json`.

## Trust admission

- Configure `kit.trustedSigners` before enabling `kit.requireSignature`. With
  `requireSignature` on, unsigned kits, signatures that do not match
  `trustedSigners`, and ZIP kits are rejected when loaded from a directory, git
  repository or OCI registry. The default signer policy trusts Docker employee
  identities attested by Google's OIDC issuer (public kits-v2).
- The signature covers `spec.yaml` and `files/`, not image tags or content
  downloaded by install/startup commands. Pin those by digest or checksum.
- `kit.allowExtractedAgents` (default on) admits the commit-pinned references
  that replaced formerly built-in agents and exempts them from the signature
  requirement; only a commit-SHA-pinned git reference can match, never a tag,
  branch, directory or OCI entry.
- These are user/administrator policy. An agent never edits them to make a load
  succeed.

## `sbx kit add SANDBOX REFERENCE [flags]`

Adds a **mixin** (only) to an **existing** sandbox by **recreating its
container** with the new kit appended to the sandbox's original kit list, not by
live injection. A `kind: sandbox` kit is refused ("`sbx kit add` is for
mixins"). A stopped sandbox is started first. The daemon owns the swap: stop the
original, commit it, compose a swap container (`<sandbox>-swap-<hex>`), start
it, remove the original, reclaim the swap image, and roll back on failure.
Packages and images in the container, kit-owned volumes and agent history carry
over; bind-mounted workspaces keep their host mount and `--clone` sandboxes keep
their working tree in a named volume.

The original kit references are re-resolved at add time, so an unpinned tag or
branch can bring different content than at creation; pin references. Arguments
the sandbox was created with apply to the new kit too; `--kit-arg` overrides.

Preconditions, each refused with an error: the sandbox carries the original-kit
label (older sandboxes do not; this is an `add` requirement, not one of
`create --kit`), it is not a legacy git-worktree sandbox, and the kit shape is
accepted:

| Kit declares | Result |
|---|---|
| `environment.variables`, `setup.install`, `permissions.network.allow` | accepted (required `--kit-arg` values are supported) |
| `setup.startup` | refused ("does not yet apply") |
| `setup.files` | refused ("does not yet apply") |
| static `files/` content | refused ("does not yet apply") |
| `volumes` | refused ("does not yet pre-create") |
| `sandbox.resources` (cpu, memory, gpu) | refused ("does not yet apply") |
| `security.privileged` | refused ("does not yet apply") |
| `ports` | refused ("does not yet publish") |
| `permissions.network.deny` | refused ("does not yet apply") |
| `credentials` | refused ("does not yet wire") |

The refusal message and the missing-label message both suggest `sbx rm` plus
`sbx create --kit`. That destroys the sandbox. Offer instead to create a **new**
sandbox with a different `--name` and the desired kit set, and never remove the
existing one without explicit user consent.

Warnings printed after a successful swap (read them; live success is not the
whole story):

- Credentials the new kit set withheld because no binding exists; the sandbox
  cannot authenticate against those services until a binding is added.
- Runtime `sbx mount` entries that failed to replay; re-run each listed
  `sbx mount`, except entries marked permanent, for which the record must be
  dropped.
- "record could not be saved": the sandbox runs with the new kit set but a
  daemon restart would revert it. Retry with `sbx kit add SANDBOX REF` using a
  reference the sandbox already carries.

Removing a mixin from a sandbox means recreating the sandbox; kits cannot be
removed from a running sandbox.

Flags: `--kit-arg`, `--kit-args-file`.

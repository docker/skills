# Sources

## v3 track: docker/sandbox-kit-spec at 4d932451613f8df89c8468e2bb7c5286882897ca

Adapted, not copied, from two files supplied by the operator from
docker/sandbox-kit-spec at commit `4d932451613f8df89c8468e2bb7c5286882897ca`
(repository marked not private at capture). The files were supplied as
`SKILL.md` (frontmatter `name: create-kit-v3`) and `RECIPES.md`. Their paths
inside that repository were not supplied and are not asserted here; the
operator should confirm them before publishing.

Where each part went:

- `create-kit-v3` `SKILL.md`: kind decision, layout, and the workflow in this
  skill's `SKILL.md`; the descriptor skeleton, capability table, volume and
  host-mount rules, bundled skills, groups, and environment references in
  `v3-capabilities.md`; publishing and signing in `v3-publish-and-sign.md`.
- `RECIPES.md`: `v3-recipes.md`, with its links to the source `SKILL.md`
  rewritten to this skill's `SKILL.md`.
- `assets/v3-mixin-egress.yaml` is original to this adaptation. It uses only
  descriptor keys and capability types that appear in the source skeleton,
  and it passed build and layout conformance checks on 2026-11-02. After
  making explanatory context optional, runtime composition and npm HTTPS
  connectivity also passed on v0.50.1; see the scoped evidence below.

Changes made while adapting (not source behavior):

- The workload recipe's `ENTRYPOINT` no longer carries a permission-bypass
  flag, and a checksum-pinning note was added.
- `kit-tck` installation is described as pinned rather than `@latest`.
- Approval, scratch-namespace, and inverse-operation (cleanup) guidance was
  added around registry pushes, builders, test sandboxes, and local images.
- References to source-repository paths (`examples/...`, the `migrate-kit-to-v3`
  skill and its `FIELD-MAPPING.md`) were removed or marked unavailable, since
  they are not part of this catalog and were not supplied.

Links the source cites (not fetched or re-verified here; they point at a
moving `main` branch, so treat them as pointers, not pinned evidence):

- `https://github.com/docker/sandbox-kit-spec/blob/main/docs/spec/SPEC-v3.md`
  (§3 authoring forms, §5 provides/requires, §6 args, §7 capabilities,
  §9.3 index annotations, §9.6 derived provides, §12 platform floor)
- `https://github.com/docker/sandbox-kit-spec/tree/main/docs/spec/capabilities/com.docker.sandbox`
  (per-capability pages, normative per the source)
- `https://github.com/docker/sandbox-kit-spec/tree/main/examples`
- `https://docs.docker.com/ai/sandboxes/install/` and
  `https://github.com/docker/sbx-releases` for installing `sbx`

## Removal of the legacy v2 track

An earlier revision of this skill also covered v2 `spec.yaml` kits
(`schemaVersion: "2"`, verified against docker/sandboxes
`df5c96ba60484fa2c375469dbac912c205da6c37`). That guidance, its assets, and
its evidence were removed on the operator's instruction that v2 is being
retired and v3 is the standard. That retirement is an operator statement; the
supplied v3 source gives no deprecation or removal timeline for v2, so this
skill gives no date and cites no source for it.

The earlier evidence is in the Git history of this repository, not in this
skill. Nothing in the v3 sources was used to restate, confirm, or extend it.

## v3 claims that need public evidence before publication

The source is an internal-style authoring skill. A public consumer cannot
independently verify these from this repository; each should be confirmed
against a public spec page, release note, or registry before the skill is
published:

1. Which release/load paths accept v3 source inspection, and which `sbx`
   release first supports Kits v3 in local and cloud mode. Authenticated
   inspect/validate and corrected local composition passed on `v0.50.1`;
   this establishes a tested release, not the minimum version or cloud support.
2. The capability type names, versions, and config shapes
   (`com.docker.sandbox/...@N`), including `network-policy@1` and `@2`
   exclusivity, `agent-context@2`, `dockerd@1`, and `host-mount@1`.
3. The `docker/sandbox-kit:3` BuildKit frontend image: that it is publicly
   anonymously pullable, and whether it should be pinned. Pulling succeeded
   with this machine's existing Docker configuration; no anonymous test ran.
4. The `dhi.io/sbx-templates:*` and `dhi.io/debian-base:*` base images named
   in the recipes, and the claim that they carry the platform floor (bash,
   sh, curl, git, CA store, `agent` user at uid 1000). The offline image
   inventory counts these references; its live checker does not verify
   `dhi.io`.
5. The `overlay-home-ownership` and `overlay-links-resolve` rules on a
   substantive overlay. Pinned installation and `validate --layout` passed
   for the declaration-only asset; this does not exercise tool content.
6. The runtime behaviors stated about composition: env merge, first-writer
   ownership, `PATH` appending, volume and host-mount retention, and
   `sbx run ... -- args` being agent arguments.
7. The source's statement that where docs and the Go implementation disagree
   the code wins, which cannot be checked from the supplied files.
8. The `SBX_KIT_BUILDER` and `BUILDX_BUILDER` selectors and the in-sandbox
   paths `/usr/share/sandbox/kit/<kit>/` and `/var/log/sbx-kit-startup.log`.
9. That v2 `spec.yaml` kits are being retired (operator-stated, no source).

## Conflicts and gaps

- `docker-sandboxes-lifecycle` states that `sbx --cloud` is out of scope for
  its skill set, while the v3 source says Kits v3 work in cloud mode. This
  skill makes no cloud-mode claims of its own.
- The v2-to-v3 field mapping (`FIELD-MAPPING.md` in the source's
  `migrate-kit-to-v3` skill) was not supplied. No mapping is given here, and
  `migrate-kit-to-v3` is not a skill in this catalog.
- The source does not say how v3 credential values are provided to a sandbox
  (for example whether `sbx secret set` applies), or how `args` are supplied
  at create time. This skill leaves those open.
- The sibling skills `docker-sandboxes-lifecycle`, `docker-sandboxes-env`, and
  `docker-sandboxes-network-credentials` still describe kits in v2-era
  vocabulary (`spec.yaml`, `credentials:`, `permissions.network:`). Their
  routing to this skill remains correct, but their wording has not been
  reconciled with v3.
- The original adaptation was unexecuted. The 2026-11-02 verification below
  supersedes that statement for build/layout checks, authenticated source
  loading and the corrected asset's local runtime composition. Publishing and
  signing remain untested.

## Executed verification: 2026-11-02

See [commands and output](../checks/runtime-results.md). Tested on macOS arm64,
Docker Engine 29.9.1 / Desktop 4.96.0, Buildx v0.38.0, and `sbx v0.50.1`
(`ddb0268d7124b9cf98955d0b08ffd71a0dfcebe4`). `kit-tck` was installed at
`4d932451613f8df89c8468e2bb7c5286882897ca`; its version command printed `dev`,
while Go build metadata recorded
`v3.0.0-m.11.0.20261031103226-4d932451613f` (Go 1.26.10).

Verified, scoped to this asset and these tools:

- A3: declaration-only companion-pair descriptor builds with `cacheonly`.
- A4: OCI directory export and bare-tag `validate --layout ... 0.0.0`
  succeed: **19 checks, 19 passed**. No correction was needed for build
  conformance; runtime testing later required making explanatory context optional.
- A5: misspelling `capabilities` as `capabilites` fails strict decoding and
  names the bad field.
- A6: the offline source validation path rejects this v3 source kit with
  "no kit builder configured; artifact validation failed". The normal
  command's sign-in failure alone is not evidence for v3 rejection.
- The frontend pulled as `docker/sandbox-kit:3` at
  `sha256:adbc0d1ea63451871d5d78111120bb29f2fd2b265e63d39c664ae2c3d722c805`,
  reporting `3.0.0-m.11 (92835bb7)`.

Initial-run limit: normal inspection stopped at sign-in, and offline
inspection rejected the source as expected for a builder-free path. A7 was
skipped without a trusted workload. That initial run did not verify runtime
behavior; see the authenticated follow-up below for subsequent evidence.
A1/A8 created and removed only that run's builder and scratch resources.

## Source follow-up: A2 and A6

Inspected the operator's `docker/sandboxes` checkout at
`aaa96b72111a83a8326419630ab6ad18c0fde0c5` and used `git show` to read the exact
installed v0.50.1 revision `ddb0268d7124b9cf98955d0b08ffd71a0dfcebe4`.
These code findings explain the initial failures; authenticated results
are recorded in the follow-up below:

- `cli-plugin/commands/kit.go`: normal validate sets
  `V3Builder: defaultKitBuilder{}`; offline validate/inspect deliberately omit
  it. `images_mirror.go` supplies that builder for normal inspect.
- `sandboxlib/kit/source_v3.go`: the observed error is the nil-builder guard,
  before descriptor build. `TestKitInspectCmd_OfflineRejectsV3SourceKit` and
  `TestKitValidateCmd_OfflineRejectsV3SourceKit` explicitly expect it.
- This design was introduced by commit
  `865f481537d6bb6d3951e5a2ff4cf70fcb748343` (2026-10-08), present in the
  installed release. No CLI patch or upgrade is needed to explain A2.
- `sandboxlib/auth/defaultstore.go`: a non-default app name selects a separate
  auth store, so the default app's login is not inherited.
- The original blanket claim "validate does not accept v3 source" is wrong:
  normal validation is builder-enabled in v0.50.1. A6's offline failure
  cannot support that claim. Authenticated validation subsequently passed.
- v0.50.1 `kit_source_builder.go` selects host Buildx or the sandbox builder;
  the current checkout adds in-process synthesis for declaration-only kits,
  followed by daemon import. Do not conflate these implementations.
- Installed help spells detached mode `--detach`, not the original A7
  `--detached`; the runbook now uses the supported spelling.

A7 candidate: the checkout's `tests/e2e/kits/testdata/shell` is a two-file v3
workload with `ENTRYPOINT ["sh"]` and only `com.docker.sandbox/sbx@1`.
For a disposable copy, pin its base `docker.io/sbx/shell-docker-image` to the
resolved index digest
`sha256:6c84996b07b743154fc8f26c662b642cee8fb6dd410803b2c40d5d3a537c838d`.
The index includes linux/arm64. The disposable workload was renamed to
`kit-probe` because v0.50.1 rejects a kit named `shell` as a collision with its
built-in agent. The operator signed in only to the isolated app; no auth
bypass or credential copying was attempted.

## Authenticated runtime follow-up: 2026-11-02

[Full commands and output](../checks/authenticated-results.md) supersede the
initial run's A2/A6/A7 conclusions. The same sbx v0.50.1 binary was used after
operator sign-in to an isolated app; no Sandboxes code change was needed.

- A2 succeeds but prints a projected summary, not both typed capabilities.
  Its JSON uses `newKitV2View`; do not copy that output into a v3 descriptor.
- A6 normal validate succeeds (`valid (directory)`); offline fails intentionally.
  Thus the original "must fail" expectation was wrong.
- A7 initially rejects required `agent-context@2` despite successful validation.
  The host does not support it. Corrected the asset to make only the
  explanatory context optional, leaving the network request required.
- The fixture stem `shell` also collides with a v0.50.1 built-in agent;
  renaming the disposable companion pair to `kit-probe` resolves this.
- Corrected A3/A4/A5 pass again: 19 TCK checks, raw descriptor inspection,
  and explicit rejection of `capabilites`.
- Corrected A7 starts the composed sandbox, policy check allows npm:443,
  and an in-sandbox curl returns HTTP 200. The kit descriptor is present at
  `/usr/share/sandbox/kit/extra-egress/kit.yaml`; exec runs as uid 1000.
- This tests the observed host policy, not whether the mixin alone added
  access: the host also permits package registries. Optional context delivery
  is not verified; neither are cloud, signing or other capabilities.
- All run-created sandboxes, builders, scratch directories and isolated daemon
  runtime state were removed. The operator's isolated sign-in was preserved.

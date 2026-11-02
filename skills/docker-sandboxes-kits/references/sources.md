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
  and it has not been built or run.

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

1. That `sbx kit validate` does not accept a v3 source kit while
   `sbx kit inspect` does, and which `sbx` release first supports Kits v3 in
   local and cloud mode (the source gives no version).
2. The capability type names, versions, and config shapes
   (`com.docker.sandbox/...@N`), including `network-policy@1` and `@2`
   exclusivity, `agent-context@2`, `dockerd@1`, and `host-mount@1`.
3. The `docker/sandbox-kit:3` BuildKit frontend image: that it is publicly
   pullable, and whether it should be pinned.
4. The `dhi.io/sbx-templates:*` and `dhi.io/debian-base:*` base images named
   in the recipes, and the claim that they carry the platform floor (bash,
   sh, curl, git, CA store, `agent` user at uid 1000). The offline image
   inventory counts these references; its live checker does not verify
   `dhi.io`.
5. The `kit-tck` tool, its install path, its `validate --layout` behavior,
   and the `overlay-home-ownership` and `overlay-links-resolve` rules.
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
- Nothing in the supplied material was executed: no `docker buildx` build, no
  `kit-tck` run, no `sbx` command, no signing, and no registry access.

# Contributing to Docker Skills

Thank you for your interest in contributing! This repository contains Docker-authored knowledge skills for AI coding agents. Issues, bug fixes, new skills, and improvements to existing skills are all welcome.

## Reporting issues

A great way to contribute is to send a detailed issue when you encounter a
problem. Before opening a new issue, check
[the issue database](https://github.com/docker/skills/issues) to see if your
problem or suggestion has already been reported.

## Submitting changes

1. Fork the repository.
2. Create a feature branch from `main`.
3. Make your changes.
   - When adding a new skill, place it under `skills/<skill-id>/` with a
     `SKILL.md` and any supporting files. Follow the structure of existing
     skills. Give it a valid initial `X.Y.Z` version in both `catalog.yaml`
     and `skills/<skill-id>/skill.yaml`; the values must match. Then:
     - Add an entry to `catalog.yaml` with the skill's `product` (one of the
       declared product families) and `status` (`stable` or `experimental`).
       Validation fails when a skill directory has no catalog entry or vice
       versa.
     - Run `task catalog` to regenerate the README skill table, the human-facing
       catalog at `docs/catalog/index.md`, the `evals/README.md` runbook table,
       and `skills.sh.json`. Do not edit those sections by hand; CI fails when
       they drift from the catalog.
     - Add an evaluation runbook at `evals/<skill-id>.md`.
     - Ensure both the skill and its evaluation runbook are covered by
       specific family rules in `.github/CODEOWNERS`, adding rules when
       needed; the repository-wide fallback is not a substitute for a domain
       owner.
   - Any change under `skills/<skill-id>/` must increase that skill's version
     in both `catalog.yaml` and `skills/<skill-id>/skill.yaml` in the same pull
     request. Versions never decrease. Use a patch for corrective prose,
     assets, or checks; a minor version for new guidance, assets, or a status
     change; and a major version for a material routing-contract change. Keep
     the `SKILL.md` frontmatter and section structure consistent with the rest
     of the repo.
   - Human-facing documentation belongs under `docs/`. Follow
     [`docs/STYLE.md`](docs/STYLE.md), use relative `.md` links between docs
     pages, and set canonical front matter under
     `https://docs.docker.com/ai/skills/`. Run `task docs:check` after changing
     docs content, layouts, assets, or validation.
   - Add user-visible changes to the `Unreleased` section of
     [`CHANGELOG.md`](CHANGELOG.md). Keep entries concise and move them into a
     versioned section when preparing a distribution release.
4. Run the complete validation suite locally (requires
   [Task](https://taskfile.dev/) and Docker), comparing version changes with the
   pull request base:
   ```bash
   VERSION_CHECK_BASE_SHA=$(git merge-base HEAD origin/main) task
   ```
   Pull request CI supplies this base automatically. If `origin/main` is
   unavailable while working offline, plain `task` remains usable and skips
   only the version comparison.
5. Commit your changes with a `Signed-off-by` line (see *Sign your work* below).
6. Open a pull request and fill out the template.

## Maintainer releases

The top-level `version` in `catalog.yaml` is the distribution version. It is
separate from each skill's own `version` and changes only in a release pull
request. A distribution version pull request must increase the version, must
not include skill content or per-skill version changes, and may change only
`catalog.yaml`, `CHANGELOG.md`, and files rendered by `task catalog`. Finalize
the release notes by moving relevant `Unreleased` entries into the new versioned
section; do not hand-edit rendered outputs. Apply SemVer proportionally to the
distribution: use a patch for compatible fixes and documentation corrections, a
minor version for compatible added skills or capabilities, and a major version
for breaking changes to installation, catalog, or distribution contracts.

To prepare and publish a release:

1. From a clean release branch, run `task release:prepare VERSION=X.Y.Z` with a
   strict version greater than the current catalog distribution version. The
   command preserves `catalog.yaml` formatting while updating its top-level
   version, moves the nonempty `Unreleased` notes into a dated version section,
   rotates the changelog comparison links, and renders all catalog-derived
   files. It fails without writing when the version or changelog structure is
   invalid. Review the complete diff; do not edit rendered outputs by hand.
2. Run `task`, review the generated diff, and merge the release pull request.
3. On the merged `main` commit, open **Actions → release → Run workflow**. Select
   `main`, enter the exact `vX.Y.Z` matching the catalog distribution version,
   leave `dry_run` enabled, and run the workflow. Review every job before
   continuing; a dry run builds the image but creates no tag, registry image, or
   GitHub release.
4. Dispatch the same version from `main` again with `dry_run` disabled. The
   workflow creates an annotated tag at that exact dispatch commit, publishes
   the multi-architecture version image, and creates a draft GitHub release with
   `catalog.yaml`, `skills.sh.json`, the image reference, and its digest.
5. Inspect the draft's commit, assets, image reference, and digest, then publish
   it manually. The workflow never publishes a release automatically.

A failed publish run is safe to retry with the same version from the same `main`
commit. It reuses a matching tag and image digest without overwriting either, and
refreshes only an existing draft release. It fails instead of changing a tag that
resolves to another commit, an image built from another commit, or an already
published release.

Release validation rejects a version that does not use strict `vX.Y.Z` syntax or
does not match the catalog version. Never repoint or reuse a release tag or image.
Correct a released artifact or version by preparing and releasing a new patch
version; releases move forward only.

## Sign your work

The sign-off is a simple line at the end of the explanation for the patch. Your
signature certifies that you wrote the patch or otherwise have the right to pass
it on as an open-source patch. The rules are pretty simple: if you can certify
the below (from [developercertificate.org](https://developercertificate.org)):

```
Developer Certificate of Origin
Version 1.1

Copyright (C) 2004, 2006 The Linux Foundation and its contributors.
660 York Street, Suite 102,
San Francisco, CA 94110 USA

Everyone is permitted to copy and distribute verbatim copies of this
license document, but changing it is not allowed.

Developer's Certificate of Origin 1.1

By making a contribution to this project, I certify that:

(a) The contribution was created in whole or in part by me and I
    have the right to submit it under the open source license
    indicated in the file; or

(b) The contribution is based upon previous work that, to the best
    of my knowledge, is covered under an appropriate open source
    license and I have the right under that license to submit that
    work with modifications, whether created in whole or in part
    by me, under the same open source license (unless I am
    permitted to submit under a different license), as indicated
    in the file; or

(c) The contribution was provided directly to me by some other
    person who certified (a), (b) or (c) and I have not modified
    it.

(d) I understand and agree that this project and the contribution
    are public and that a record of the contribution (including all
    personal information I submit with it, including my sign-off) is
    maintained indefinitely and may be redistributed consistent with
    this project or the open source license(s) involved.
```

Then you just add a line to every git commit message:

    Signed-off-by: Joe Smith <joe.smith@email.com>

Use your real name (sorry, no pseudonyms or anonymous contributions.)

If you set your `user.name` and `user.email` git configs, you can sign your
commit automatically with `git commit -s`. CI checks every non-merge commit in
the pull request for a valid `Signed-off-by: Name <email>` trailer. To repair a
branch with missing trailers, rebase and sign off its commits, then update the
branch:

```console
git rebase --signoff <base>
```

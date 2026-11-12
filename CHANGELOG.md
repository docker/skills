# Changelog

All notable distribution changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html)
for distribution releases.

## [Unreleased]

### Added

- Added the experimental `docker-docs` skill. It answers questions about any
  Docker product from current, cited Docker Docs pages. It uses the Docker docs
  MCP search tool when one is available. Otherwise it falls back to
  `docs.docker.com/llms.txt` and per-page Markdown. A product map covers Docker
  Sandboxes, cloud sandboxes, DHI, Docker Agent, Model Runner, MCP Toolkit, and
  account, admin, and billing docs.
- The plugin now registers the remote Docker docs MCP server
  (`https://ai-backend-service.docker.com/mcp`) for Claude Code, Codex, Cursor,
  GitHub Copilot CLI, and Gemini CLI installations.

### Fixed

- Live skill eval cleanup no longer treats a failed resource listing as empty,
  and force-removes only resources created during the run that the agent's
  own CLI calls named or the scenario declares in `cleanup.owned_names`, so a
  failed `sbx ls` or a concurrently created sandbox is never removed.

- Kit verification examples preserve the parent working directory, compare
  complete tool versions literally, audit only manifest-referenced layers
  without hiding read failures, and remove a test builder only after this
  session successfully created it. Regression tests exercise these failure paths.

- Image inventory now matches the case-sensitive Compose `image:` key rather
  than treating recorded CLI `Image:` labels as public image references.
  Regression tests retain scanning of real image syntax in plain-text examples.

### Removed

- Removed the experimental `docker-sandboxes-env` skill and its evaluation
  runbook, following a decision with the Docker Sandboxes team. The
  kit-reference rules it held now live in `docker-sandboxes-kits`. No skill in
  this catalog owns the rest of `sbxenv.yaml`; `docker-docs` answers those
  questions from the Docker Docs environment files page.

### Changed

- `docker-sandboxes-kits` 1.0.4 now owns referencing, configuring, and pinning a
  kit from an `sbxenv.yaml` `agent:`/`kits:` entry. A new
  `references/sbxenv-kit-references.md` covers reference shapes, handles,
  create-phase args, `kit.allowedSources`, the capability-to-field mapping
  (`bindings:`, `mounts:`, `ports:`), and why a clean `sbx env plan` is not
  proof that a kit exists or installs. It adds evaluation Prompt 8.
- `docker-sandboxes-lifecycle` 0.1.1, `docker-sandboxes-network-credentials`
  0.1.1, and `docker-docs` 0.2.0 route `sbxenv.yaml` questions to `docker-docs`
  and kit references to `docker-sandboxes-kits` instead of the removed skill.
  The `docker-docs` product map lists `sbxenv.yaml`, `sbx env`, and `sbx mcp`
  as Docker Sandboxes terms.
- `docker-sandboxes-kits` 1.0.3 adds pinned public source/spec links, separates
  untested runtime scope from verified claims, and records live build/layout verification (19
  conformance checks passed), strict-decoding rejection, and scoped cleanup.
  Source review of `sbx v0.50.1` confirms normal inspect and validate configure
  a v3 builder; offline rejection is intentional and is not an auth workaround.
  Authenticated runtime testing now passes with optional explanatory context
  (v0.50.1 rejects required `agent-context@2`); the network request remains
  required. Recorded successful composition, policy check and HTTP 200, plus
  original failures, the workload-name workaround and scoped cleanup.

- `docker-sandboxes-kits` (experimental) now covers v3 kit descriptors only and
  was versioned 1.0.3 for the major routing change and verification fixes (now 1.0.4; see above). It teaches the v3 workflow
  (`# syntax=docker/sandbox-kit:3`, workload or mixin, typed capabilities,
  `docker buildx`, `kit-tck`, `sbx kit inspect`, publishing and signing), with
  recipes, a complete declaration-only mixin asset, and a v3 verification
  runbook. The earlier legacy v2 `spec.yaml` (`schemaVersion: "2"`) guidance,
  assets, and `sbx kit` command references were removed as a routing decision;
  this is not a product deprecation announcement. The skill offers a new v3
  descriptor instead. `sbx kit validate`
  is not a substitute for conformance or runtime verification. Its evaluation
  runbook and checks cover v3 only, and its
  provenance lists the v3 claims that still need public evidence. The
  `migrate-kit-to-v3` skill named by the v3 source is not part of this catalog.

## [0.3.1] - 2026-09-29

### Added

- Added a separate external HTTPS link checker for advisory pull-request URL checks
  and weekly full sweeps, with an opt-in live-network Task command. Pull-request
  checks include repeated URLs added on new lines; HTTPS requests connect only to
  vetted public addresses and warn rather than bypass configured proxies.
  A new distribution version's unpublished compare and release-tag links in the
  changelog are reported as notices only for unredirected 404s in PR checks.
- Added offline inventory and opt-in live validation for actionable public
  container image tags in skill and eval examples, including implicit `latest`
  for untagged references. Docker Hub and gcr.io manifests are checked for
  linux/amd64 and linux/arm64. Advisory PR checks inspect new references,
  while weekly/manual full sweeps report failures.
- Expanded the README with client-specific installation commands, experimental
  Docker Sandboxes installation, manual-copy guidance, and release pinning and
  update options. The README remains self-contained and records canonical
  Docker Docs links for each distribution surface.

### Changed

- Replaced obsolete Docker Agent documentation and Claude Code schema links,
  and removed the unavailable Docker Sandboxes source repository link from the
  generated skill catalog.
- Reorganized the README around skill discovery, installation, published
  distribution surfaces, release channels, and local development. The catalog
  continues to generate the skill table and published-surface inventory.
- `docker-build-strategies` now recommends BuildKit cache mounts for `apt`/`apk`
  package installs instead of cleaning up the cache in the same `RUN` layer,
  and bind-mounting dependency manifests (`package.json`, `go.mod`,
  `requirements.txt`) into install steps instead of `COPY`-ing them, for
  install commands that don't rewrite the manifest.
- `docker-agent-config` and `docker-agent-run` routing notes describe evaluation
  work by its sessions and `--baseline` regression gates; routing to
  `docker-agent-deploy` is unchanged.

### Fixed

- `docker-build-strategies`, `docker-compose-patterns`, and
  `docker-project-foundations` now tell agents to resolve bundled verification
  scripts under the skill directory and run them from the project root, with a
  fallback to the equivalent commands when that directory is unknown. The
  previous `bash scripts/<script>` instruction failed from the project when the
  skill was installed elsewhere, and running it from the skill directory checked
  the wrong folder.
- Added Claude marketplace classification for Docker development skills and removed
  the deprecated `category` field from both the Claude plugin manifest and its
  marketplace entry.
- Added a square, undistorted Docker mark icon to the Claude plugin manifest to
  resolve marketplace `ICON_MISSING` warnings, using a plain SVG path compatible
  with marketplace icon validation.
- Added Docker homepage, Docker Docs, GitHub issues support, privacy policy, and
  terms of use links to the Claude plugin manifest so the directory listing no
  longer infers documentation from the README. The Claude marketplace entry's
  homepage now matches.
- Corrected the Compose evaluation's Postgres and Redis health verification to
  inspect container IDs from `docker compose ps -q` with `docker inspect`.
- Corrected the Compose healthcheck sidecar and project-structure examples to
  use published curl and Prometheus image tags.
- Corrected `docker-build-strategies` SSH build guidance: examples list the
  forwarded agent's keys with `ssh-add -l` instead of starting an agent with
  `ssh-agent -s`, explain how to expose only the build's key, and note that
  BuildKit rejects passphrase-protected key files passed with `--ssh`. The
  `ssh-keyscan` note no longer claims the host key is pinned, the Alpine cache
  citation moved to the layer-caching reference, and example Dockerfiles use a
  placeholder OCI source label. The skill's evaluation runbook, deterministic
  checks, and verification runbook now cover private Git access over SSH.

## [0.3.0] - 2026-09-23

### Changed

- Moved installation documentation to Docker Docs and retired this repository's
  Hugo site, GitHub Pages workflows, and site-specific checks. Catalog-generated
  installation links now target Docker Docs; Antigravity installation is documented
  there through the skills CLI or manual copy, not a dedicated plugin.
- The catalog now generates a published-surface inventory, validates that every
  plugin manifest maps exactly once, and synchronizes its description across
  plugin manifests.
- Tightened `docker-project-foundations` development Compose defaults: application
  and optional Postgres host access use loopback, while unauthenticated Redis stays
  on the Compose network; the development-only password fallback and `.env`
  override are now explicit.

## [0.2.0] - 2026-09-22

### Added

- OpenSSF Scorecard result publication and README badge.
- Release-tag badge and standards compatibility documentation.
- Release notes for distribution changes.
- Repository-native release preparation for distribution versions, changelog
  rotation, and generated catalog files.
- Deterministic skill-content risk checks and repository hygiene validation.
- Pull request DCO enforcement for every non-merge commit.

### Changed

- Replaced the license file with the canonical Apache License 2.0 text.
- Distribution release pull requests may update this changelog alongside the
  catalog and generated distribution outputs.
- Repository link validation now checks this changelog.
- CI installs fully hash-pinned PyYAML dependencies.

## [0.1.0] - 2026-09-22

### Added

- Docker-authored skills for Dockerfile and image builds, Compose, Docker Agent,
  and Docker Sandboxes.
- Cross-agent discovery paths, plugin manifests, and a `skills` CLI index.
- Catalog-driven product grouping, installation guidance, evaluation runbooks,
  deterministic validation, and repository documentation checks.
- CI, rolling edge image publication, and automated draft release creation with
  immutable version tags and image provenance checks.

### Changed

- Skills trigger directly from their own descriptions rather than through a
  repository-wide router skill.

[Unreleased]: https://github.com/docker/skills/compare/v0.3.1...HEAD
[0.3.1]: https://github.com/docker/skills/releases/tag/v0.3.1
[0.3.0]: https://github.com/docker/skills/releases/tag/v0.3.0
[0.2.0]: https://github.com/docker/skills/releases/tag/v0.2.0
[0.1.0]: https://github.com/docker/skills/releases/tag/v0.1.0

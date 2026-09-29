# Changelog

All notable distribution changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html)
for distribution releases.

## [Unreleased]

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
  placeholder OCI source label.

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

[Unreleased]: https://github.com/docker/skills/compare/v0.3.0...HEAD
[0.3.0]: https://github.com/docker/skills/releases/tag/v0.3.0
[0.2.0]: https://github.com/docker/skills/releases/tag/v0.2.0
[0.1.0]: https://github.com/docker/skills/releases/tag/v0.1.0

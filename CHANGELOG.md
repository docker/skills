# Changelog

All notable distribution changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html)
for distribution releases.

## [Unreleased]

### Changed

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

[Unreleased]: https://github.com/docker/skills/compare/v0.2.0...HEAD
[0.2.0]: https://github.com/docker/skills/releases/tag/v0.2.0
[0.1.0]: https://github.com/docker/skills/releases/tag/v0.1.0

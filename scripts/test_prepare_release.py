import contextlib
import io
import os
import tempfile
import unittest
from unittest import mock

import yaml

from catalog import (
    CATALOG_END,
    CATALOG_START,
    DISTRIBUTION_END,
    DISTRIBUTION_START,
    DOCS_CATALOG,
    DOCS_INSTALL,
    MANIFESTS,
    PUBLISHED_DISTRIBUTION_MANIFESTS,
    stale_files,
    test_distributions,
    write_generated,
)
from prepare_release import ReleasePreparationError, main, prepare_release


CATALOG = {
    "schema": "v1",
    "name": "test",
    "version": "1.2.3",
    "description": "Docker skills for tests.",
    "distributions": test_distributions(),
    "products": [{"id": "build", "name": "Build", "description": "Images."}],
    "skills": [
        {
            "id": "build-a",
            "product": "build",
            "path": "skills/build-a",
            "version": "0.1.0",
            "status": "stable",
        }
    ],
}
CHANGELOG = """# Changelog

## [Unreleased]

### Added

- A useful feature.

## [1.2.3] - 2026-01-02

### Added

- Initial release.

[Unreleased]: https://github.com/example/project/compare/v1.2.3...HEAD
[1.2.3]: https://github.com/example/project/releases/tag/v1.2.3
"""


class PrepareReleaseTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = self.temp.name
        self._make_repo()

    def tearDown(self):
        self.temp.cleanup()

    def _write(self, rel_path, content):
        path = os.path.join(self.root, rel_path)
        os.makedirs(os.path.dirname(path) or self.root, exist_ok=True)
        with open(path, "w", encoding="utf-8", newline="") as handle:
            handle.write(content)

    def _read(self, rel_path):
        with open(os.path.join(self.root, rel_path), encoding="utf-8", newline="") as handle:
            return handle.read()

    def _make_repo(self):
        manifest_lines = "".join(f"      - {path}\r\n" for path in PUBLISHED_DISTRIBUTION_MANIFESTS)
        self._write(
            "catalog.yaml",
            "# preserved comment\r\n"
            "schema: v1\r\n"
            "name: test\r\n"
            "version  :  '1.2.3'  # distribution\r\n"
            "description: Docker skills for tests.\r\n"
            "distributions:\r\n"
            "  - id: test-cli\r\n"
            "    category: skills-cli\r\n"
            "    name: Test CLI\r\n"
            "    description: Installs test skills.\r\n"
            "    page: docs/install/skills-cli.md\r\n"
            "    role: installer\r\n"
            "    manifests:\r\n"
            + manifest_lines +
            "products:\r\n"
            "  - id: build\r\n"
            "    name: Build\r\n"
            "    description: Images.\r\n"
            "skills:\r\n"
            "  - id: build-a\r\n"
            "    product: build\r\n"
            "    path: skills/build-a\r\n"
            "    version: 0.1.0\r\n"
            "    status: stable\r\n",
        )
        self._write("CHANGELOG.md", CHANGELOG)
        self._write("skills/build-a/skill.yaml", "description: Builds images.\n")
        self._write("README.md", "# Title\n\n" + CATALOG_START + "\n" + CATALOG_END + "\n" + DISTRIBUTION_START + "\n" + DISTRIBUTION_END + "\n")
        self._write(DOCS_INSTALL, "# Install\n\n" + DISTRIBUTION_START + "\n" + DISTRIBUTION_END + "\n")
        self._write("evals/README.md", "# Evals\n\n" + CATALOG_START + "\n" + CATALOG_END + "\n")
        self._write(DOCS_CATALOG, "# Catalog\n\n" + CATALOG_START + "\n" + CATALOG_END + "\n")
        for rel_path in MANIFESTS:
            self._write(rel_path, '{\n  "version": "0.0.1"\n}\n')
        write_generated(self.root, CATALOG)

    def _snapshot(self):
        snapshot = {}
        for directory, _, files in os.walk(self.root):
            for name in files:
                path = os.path.join(directory, name)
                rel_path = os.path.relpath(path, self.root)
                with open(path, "rb") as handle:
                    snapshot[rel_path] = handle.read()
        return snapshot

    def _assert_failure_without_writes(self, *, version="1.3.0", date="2026-09-22"):
        before = self._snapshot()
        with self.assertRaises(ReleasePreparationError):
            prepare_release(self.root, version, date)
        self.assertEqual(self._snapshot(), before)

    def test_happy_path_preserves_catalog_format_rotates_changelog_and_renders(self):
        changed = prepare_release(self.root, "1.3.0", "2026-09-22")

        self.assertEqual(changed[:2], ["catalog.yaml", "CHANGELOG.md"])
        catalog_content = self._read("catalog.yaml")
        self.assertIn("# preserved comment\r\n", catalog_content)
        self.assertIn("version  :  '1.3.0'  # distribution\r\n", catalog_content)
        self.assertIn("    version: 0.1.0\r\n", catalog_content)
        self.assertNotIn("version  :  '1.2.3'", catalog_content)

        changelog = self._read("CHANGELOG.md")
        self.assertIn("## [Unreleased]\n\n## [1.3.0] - 2026-09-22\n\n### Added", changelog)
        self.assertIn("[Unreleased]: https://github.com/example/project/compare/v1.3.0...HEAD", changelog)
        self.assertIn("[1.3.0]: https://github.com/example/project/releases/tag/v1.3.0", changelog)
        self.assertEqual(stale_files(self.root), [])
        for rel_path in MANIFESTS:
            self.assertIn('"version": "1.3.0"', self._read(rel_path))

    def test_rotation_separates_references_when_unreleased_ref_is_last_without_final_newline(self):
        version_ref = "[1.2.3]: https://github.com/example/project/releases/tag/v1.2.3\n"
        unreleased_ref = "[Unreleased]: https://github.com/example/project/compare/v1.2.3...HEAD\n"
        changelog = CHANGELOG.replace(unreleased_ref + version_ref, version_ref + unreleased_ref)
        self._write("CHANGELOG.md", changelog.rstrip("\n"))
        prepare_release(self.root, "1.3.0", "2026-09-22")
        self.assertIn(
            "[Unreleased]: https://github.com/example/project/compare/v1.3.0...HEAD\n"
            "[1.3.0]: https://github.com/example/project/releases/tag/v1.3.0\n",
            self._read("CHANGELOG.md"),
        )

    def test_main_accepts_explicit_date(self):
        stdout = io.StringIO()
        with contextlib.redirect_stdout(stdout):
            result = main(["1.2.4", "--date", "2026-02-03", "--root", self.root])
        self.assertEqual(result, 0)
        self.assertIn("wrote catalog.yaml", stdout.getvalue())
        self.assertIn("## [1.2.4] - 2026-02-03", self._read("CHANGELOG.md"))

    def test_default_date_is_utc(self):
        fake_now = mock.Mock()
        fake_now.date.return_value = __import__("datetime").date(2026, 4, 5)
        with mock.patch("prepare_release.dt.datetime") as datetime_mock:
            datetime_mock.now.return_value = fake_now
            prepare_release(self.root, "1.2.4")
            datetime_mock.now.assert_called_once_with(__import__("datetime").timezone.utc)
        self.assertIn("## [1.2.4] - 2026-04-05", self._read("CHANGELOG.md"))

    def test_rejects_invalid_and_nonincreasing_versions_without_writes(self):
        for version in ("v1.3.0", "1.3", "1.3.0-rc.1", "01.3.0", "1.2.3", "1.2.2"):
            with self.subTest(version=version):
                self._assert_failure_without_writes(version=version)

    def test_rejects_invalid_dates_without_writes(self):
        for value in ("2026-2-03", "2026-02-30"):
            with self.subTest(date=value):
                self._assert_failure_without_writes(date=value)

    def test_rejects_missing_duplicate_or_empty_unreleased_section_without_writes(self):
        cases = {
            "missing": CHANGELOG.replace("## [Unreleased]", "## Upcoming"),
            "duplicate": CHANGELOG.replace("## [1.2.3]", "## [Unreleased]\n\n### Fixed\n\n- Other.\n\n## [1.2.3]"),
            "malformed unreleased": CHANGELOG.replace("## [Unreleased]", "## [Unreleased ]"),
            "empty": CHANGELOG.replace("\n### Added\n\n- A useful feature.\n", "\n"),
            "malformed following release": CHANGELOG.replace("## [1.2.3] - 2026-01-02", "## [1.2.3]"),
            "no following section": CHANGELOG.split("## [1.2.3]")[0]
            + "[Unreleased]: https://github.com/example/project/compare/v1.2.3...HEAD\n",
        }
        for name, changelog in cases.items():
            with self.subTest(name=name):
                self._write("CHANGELOG.md", changelog)
                self._assert_failure_without_writes()
                self._write("CHANGELOG.md", CHANGELOG)

    def test_rejects_malformed_missing_duplicate_or_stale_unreleased_reference_without_writes(self):
        valid_ref = "[Unreleased]: https://github.com/example/project/compare/v1.2.3...HEAD"
        cases = {
            "missing": CHANGELOG.replace(valid_ref + "\n", ""),
            "malformed": CHANGELOG.replace("...HEAD", "..HEAD"),
            "duplicate": CHANGELOG.replace(valid_ref, valid_ref + "\n" + valid_ref),
            "stale": CHANGELOG.replace("compare/v1.2.3...HEAD", "compare/v1.2.2...HEAD"),
        }
        for name, changelog in cases.items():
            with self.subTest(name=name):
                self._write("CHANGELOG.md", changelog)
                self._assert_failure_without_writes()
                self._write("CHANGELOG.md", CHANGELOG)

    def test_rejects_duplicate_or_mismatched_existing_release_structures_without_writes(self):
        cases = {
            "duplicate section": CHANGELOG.replace(
                "## [1.2.3] - 2026-01-02",
                "## [1.2.3] - 2026-02-03\n\n- Duplicate.\n\n## [1.2.3] - 2026-01-02",
            ),
            "missing release reference": CHANGELOG.replace(
                "[1.2.3]: https://github.com/example/project/releases/tag/v1.2.3\n", ""
            ),
            "extra release reference": CHANGELOG
            + "[1.1.0]: https://github.com/example/project/releases/tag/v1.1.0\n",
            "wrong release tag": CHANGELOG.replace("releases/tag/v1.2.3", "releases/tag/v1.2.2"),
        }
        for name, changelog in cases.items():
            with self.subTest(name=name):
                self._write("CHANGELOG.md", changelog)
                self._assert_failure_without_writes()
                self._write("CHANGELOG.md", CHANGELOG)

    def test_rejects_existing_release_section_or_reference_without_writes(self):
        for suffix in (
            "\n## [1.3.0] - 2026-09-01\n\n- Duplicate.\n",
            "\n[1.3.0]: https://github.com/example/project/releases/tag/v1.3.0\n",
        ):
            with self.subTest(suffix=suffix):
                self._write("CHANGELOG.md", CHANGELOG + suffix)
                self._assert_failure_without_writes()
                self._write("CHANGELOG.md", CHANGELOG)

    def test_rejects_missing_or_duplicate_top_level_catalog_version_without_writes(self):
        original = self._read("catalog.yaml")
        cases = (
            original.replace("version  :  '1.2.3'  # distribution\r\n", ""),
            original.replace(
                "version  :  '1.2.3'  # distribution\r\n",
                "version: 1.2.3\r\nversion: 1.2.3\r\n",
            ),
        )
        for catalog_content in cases:
            with self.subTest(catalog=catalog_content):
                self._write("catalog.yaml", catalog_content)
                self._assert_failure_without_writes()
                self._write("catalog.yaml", original)

    def test_renderer_prevalidation_failure_makes_no_writes(self):
        os.remove(os.path.join(self.root, "README.md"))
        before = self._snapshot()
        with self.assertRaises(FileNotFoundError):
            prepare_release(self.root, "1.3.0", "2026-09-22")
        self.assertEqual(self._snapshot(), before)

    def test_catalog_remains_valid_yaml_after_format_preserving_edit(self):
        prepare_release(self.root, "2.0.0", "2026-09-22")
        self.assertEqual(yaml.safe_load(self._read("catalog.yaml"))["version"], "2.0.0")


if __name__ == "__main__":
    unittest.main()

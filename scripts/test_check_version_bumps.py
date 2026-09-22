import copy
import os
import pathlib
import subprocess
import tempfile
import unittest

import yaml

from catalog import (
    CATALOG_END,
    CATALOG_START,
    DOCS_CATALOG,
    EVALS_README,
    MANIFESTS,
    README,
    SKILLS_INDEX,
    generated_files,
    write_generated,
)
from check_version_bumps import check_version_bumps, main


BASE_CATALOG = {
    "schema": "v1",
    "name": "test",
    "version": "1.0.0",
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


class CheckVersionBumpsTests(unittest.TestCase):
    def setUp(self):
        self.root = tempfile.mkdtemp()
        self.run_command("git", "init", "-q")
        self.run_command("git", "config", "user.name", "Test User")
        self.run_command("git", "config", "user.email", "test@example.com")
        self.catalog = copy.deepcopy(BASE_CATALOG)
        self.write_catalog()
        self.write_skill("build-a", "0.1.0", "original guidance\n")
        self.write_rendered_files("1.0.0")
        self.commit("base")
        self.base = self.run_command("git", "rev-parse", "HEAD").stdout.strip()

    def run_command(self, *args):
        return subprocess.run(args, cwd=self.root, check=True, text=True, capture_output=True)

    def write(self, path, content):
        target = pathlib.Path(self.root, path)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content)

    def write_catalog(self):
        self.write("catalog.yaml", yaml.safe_dump(self.catalog, sort_keys=False))

    def write_skill(self, skill_id, version, guidance):
        self.write(
            f"skills/{skill_id}/skill.yaml",
            yaml.safe_dump({"id": skill_id, "version": version}, sort_keys=False),
        )
        self.write(f"skills/{skill_id}/SKILL.md", guidance)

    def write_rendered_files(self, version):
        self.write(README, f"before\n{CATALOG_START}\nold\n{CATALOG_END}\nafter\n")
        self.write(EVALS_README, f"before\n{CATALOG_START}\nold\n{CATALOG_END}\nafter\n")
        self.write(DOCS_CATALOG, f"before\n{CATALOG_START}\nold\n{CATALOG_END}\nafter\n")
        self.write(SKILLS_INDEX, "{}\n")
        for path in MANIFESTS:
            self.write(path, '{\n  "version": "' + version + '"\n}\n')
        write_generated(self.root, self.catalog)

    def commit(self, message="change"):
        self.run_command("git", "add", ".")
        self.run_command("git", "commit", "-qm", message)

    def change_existing_skill(self, catalog_version="0.1.1", skill_yaml_version="0.1.1"):
        self.catalog["skills"][0]["version"] = catalog_version
        self.write_catalog()
        self.write_skill("build-a", skill_yaml_version, "corrected guidance\n")
        self.commit()

    def test_changed_skill_requires_synchronized_increase(self):
        self.change_existing_skill()
        self.assertEqual(check_version_bumps(self.base, self.root), [])

    def test_changed_skill_without_version_increase_fails(self):
        self.write_skill("build-a", "0.1.0", "corrected guidance\n")
        self.commit()
        errors = check_version_bumps(self.base, self.root)
        self.assertTrue(any("changed but its version did not increase" in error for error in errors))

    def test_changed_skill_requires_both_version_files(self):
        self.change_existing_skill(skill_yaml_version="0.1.0")
        errors = check_version_bumps(self.base, self.root)
        self.assertTrue(any("version must match" in error for error in errors))
        self.assertTrue(any("skill.yaml was not bumped" in error for error in errors))

    def test_existing_version_cannot_decrease(self):
        self.change_existing_skill("0.0.9", "0.0.9")
        errors = check_version_bumps(self.base, self.root)
        self.assertTrue(any("version cannot decrease" in error for error in errors))

    def test_status_change_requires_skill_version_increase(self):
        self.catalog["skills"][0]["status"] = "experimental"
        self.write_catalog()
        self.commit()
        errors = check_version_bumps(self.base, self.root)
        self.assertTrue(any("changed but its version did not increase" in error for error in errors))

    def test_new_skill_accepts_matching_initial_semver(self):
        self.catalog["skills"].append(
            {
                "id": "build-b",
                "product": "build",
                "path": "skills/build-b",
                "version": "0.1.0",
                "status": "experimental",
            }
        )
        self.write_catalog()
        self.write_skill("build-b", "0.1.0", "new guidance\n")
        self.commit()
        self.assertEqual(check_version_bumps(self.base, self.root), [])

    def test_new_skill_rejects_invalid_or_mismatched_initial_version(self):
        self.catalog["skills"].append(
            {
                "id": "build-b",
                "product": "build",
                "path": "skills/build-b",
                "version": "v1",
                "status": "stable",
            }
        )
        self.write_catalog()
        self.write_skill("build-b", "0.1.0", "new guidance\n")
        self.commit()
        errors = check_version_bumps(self.base, self.root)
        self.assertTrue(any("valid initial X.Y.Z version" in error for error in errors))

    def test_distribution_version_increase_allows_changelog_and_rendered_outputs(self):
        self.catalog["version"] = "1.1.0"
        self.write_catalog()
        self.write_rendered_files("1.1.0")
        self.write("CHANGELOG.md", "# Changelog\n\n## 1.1.0\n")
        self.commit()
        self.assertEqual(check_version_bumps(self.base, self.root), [])

    def test_distribution_version_must_increase(self):
        self.catalog["version"] = "0.9.0"
        self.write_catalog()
        self.write_rendered_files("0.9.0")
        self.commit()
        errors = check_version_bumps(self.base, self.root)
        self.assertTrue(any("distribution version must increase" in error for error in errors))

    def test_distribution_version_rejects_skill_or_other_changes(self):
        self.catalog["version"] = "1.1.0"
        self.catalog["skills"][0]["version"] = "0.2.0"
        self.write_catalog()
        self.write_skill("build-a", "0.2.0", "new guidance\n")
        self.write_rendered_files("1.1.0")
        self.write("notes.txt", "not generated\n")
        self.commit()
        errors = check_version_bumps(self.base, self.root)
        self.assertTrue(any("skill entries and other catalog data" in error for error in errors))
        self.assertTrue(any("must not change skill content" in error for error in errors))
        self.assertTrue(any("unexpected paths: notes.txt" in error for error in errors))

    def test_distribution_version_rejects_hand_edits_to_rendered_output(self):
        self.catalog["version"] = "1.1.0"
        self.write_catalog()
        self.write_rendered_files("1.1.0")
        self.write("README.md", "hand-edited\n")
        self.commit()
        errors = check_version_bumps(self.base, self.root)
        self.assertTrue(any("cannot render catalog-derived files" in error for error in errors))

    def test_skill_removal_is_allowed_when_catalog_and_directory_are_removed(self):
        self.catalog["skills"] = []
        self.write_catalog()
        for path in ("skills/build-a/SKILL.md", "skills/build-a/skill.yaml"):
            pathlib.Path(self.root, path).unlink()
        pathlib.Path(self.root, "skills/build-a").rmdir()
        self.commit()
        self.assertEqual(check_version_bumps(self.base, self.root), [])

    def test_unavailable_base_is_actionable(self):
        errors = check_version_bumps("missing-base", self.root)
        self.assertEqual(
            errors,
            [
                "base revision 'missing-base' is unavailable; ensure CI checks out adequate Git history "
                "or pass a reachable commit"
            ],
        )

    def test_cli_skips_when_base_is_absent(self):
        previous = os.environ.pop("VERSION_CHECK_BASE_SHA", None)
        try:
            self.assertEqual(main(["--root", self.root]), 0)
        finally:
            if previous is not None:
                os.environ["VERSION_CHECK_BASE_SHA"] = previous


if __name__ == "__main__":
    unittest.main()

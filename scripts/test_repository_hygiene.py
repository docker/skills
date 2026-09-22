import pathlib
import tempfile
import unittest

import yaml

from repository_hygiene import (
    DISCOVERY_LINKS,
    validate_codeowners,
    validate_discovery_links,
    validate_skill_line_limits,
)


REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent


class RepositoryHygieneTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = pathlib.Path(self.temp.name)
        (self.root / ".github").mkdir()
        (self.root / "skills" / "test-skill").mkdir(parents=True)
        (self.root / "evals").mkdir()
        (self.root / "AGENTS.md").write_text("guidance\n")
        self.catalog = {
            "skills": [{"id": "test-skill", "path": "skills/test-skill"}],
        }

    def tearDown(self):
        self.temp.cleanup()

    def write_codeowners(self, content):
        (self.root / ".github" / "CODEOWNERS").write_text(content)

    def make_links(self):
        for relative in DISCOVERY_LINKS:
            path = self.root / relative
            path.parent.mkdir(exist_ok=True)
            path.symlink_to("../skills")
        (self.root / "CLAUDE.md").symlink_to("AGENTS.md")

    def test_discovery_links_resolve_to_canonical_targets(self):
        self.make_links()
        self.assertEqual(validate_discovery_links(self.root), [])

    def test_discovery_links_reject_missing_regular_and_wrong_targets(self):
        self.make_links()
        (self.root / ".agents" / "skills").unlink()
        (self.root / ".agents" / "skills").mkdir()
        (self.root / ".claude" / "skills").unlink()
        (self.root / ".claude" / "skills").symlink_to("../evals")
        (self.root / "CLAUDE.md").unlink()
        (self.root / "CLAUDE.md").write_text("not a link\n")
        errors = validate_discovery_links(self.root)
        self.assertTrue(any(".agents/skills" in error and "symlink" in error for error in errors))
        self.assertTrue(any(".claude/skills" in error and "resolve" in error for error in errors))
        self.assertTrue(any("CLAUDE.md" in error and "symlink" in error for error in errors))

    def test_codeowners_accepts_exact_and_specific_family_patterns(self):
        self.write_codeowners(
            "* @fallback\n"
            "/skills/test-*/ @team\n"
            "/evals/test-*.md @team\n"
        )
        self.assertEqual(validate_codeowners(self.root, self.catalog), [])

    def test_codeowners_rejects_catchalls_empty_owners_and_later_overrides(self):
        cases = (
            "* @fallback\n",
            "/skills/*/ @team\n/evals/*.md @team\n",
            "/skills/*/SKILL.md @team\n/evals/**.md @team\n",
            "/skills/ @team\n/evals/ @team\n",
            "/skills/test-skill/\n/evals/test-skill.md\n",
            "/skills/test-skill/ @team\n/evals/test-skill.md @team\n* @fallback\n",
        )
        for content in cases:
            with self.subTest(content=content):
                self.write_codeowners(content)
                errors = validate_codeowners(self.root, self.catalog)
                self.assertEqual(len(errors), 2)

    def test_skill_line_limit_accepts_500_and_rejects_501(self):
        skill = self.root / "skills" / "test-skill" / "SKILL.md"
        skill.write_text("line\n" * 500)
        self.assertEqual(validate_skill_line_limits(self.root, self.catalog), [])
        skill.write_text("line\n" * 501)
        self.assertEqual(
            validate_skill_line_limits(self.root, self.catalog),
            ["skills/test-skill/SKILL.md exceeds the 500-line limit (501 lines)"],
        )

    def test_current_repository_passes(self):
        catalog = yaml.safe_load((REPO_ROOT / "catalog.yaml").read_text())
        self.assertEqual(validate_discovery_links(REPO_ROOT), [])
        self.assertEqual(validate_codeowners(REPO_ROOT, catalog), [])
        self.assertEqual(validate_skill_line_limits(REPO_ROOT, catalog), [])


if __name__ == "__main__":
    unittest.main()

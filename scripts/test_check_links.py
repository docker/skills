import tempfile
import unittest
from pathlib import Path

from check_links import check_documentation, check_link, extract_links, heading_anchors


class CheckLinksTest(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        (self.root / "README.md").write_text("# Installation\n", encoding="utf-8")
        (self.root / "CONTRIBUTING.md").write_text("# Contributing\n", encoding="utf-8")
        (self.root / "SECURITY.md").write_text("# Security\n", encoding="utf-8")
        (self.root / "AGENTS.md").write_text("# Repository guidance\n", encoding="utf-8")
        (self.root / "CHANGELOG.md").write_text("# Changelog\n", encoding="utf-8")
        (self.root / "evals").mkdir()

    def tearDown(self):
        self.temp_dir.cleanup()

    def write_eval(self, content):
        path = self.root / "evals" / "guide.md"
        path.write_text(content, encoding="utf-8")
        return path

    def test_existing_file_and_anchor_links_pass(self):
        self.write_eval(
            "[Root](../README.md)\n"
            "[Install](../README.md#installation)\n"
            "# Local heading\n"
            "[Local](#local-heading)\n"
        )

        self.assertEqual([], check_documentation(self.root))

    def test_root_agents_document_is_checked(self):
        (self.root / "AGENTS.md").write_text("[Missing](missing.md)\n", encoding="utf-8")

        self.assertEqual(
            ["AGENTS.md:1: target not found: missing.md"],
            check_documentation(self.root),
        )

    def test_root_changelog_is_checked(self):
        (self.root / "CHANGELOG.md").write_text("[Missing](missing.md)\n", encoding="utf-8")

        self.assertEqual(
            ["CHANGELOG.md:1: target not found: missing.md"],
            check_documentation(self.root),
        )

    def test_missing_file_fails_with_location(self):
        self.write_eval("[Missing](missing.md)\n")

        self.assertEqual(
            ["evals/guide.md:1: target not found: missing.md"],
            check_documentation(self.root),
        )

    def test_missing_anchor_fails_with_target(self):
        self.write_eval("[Missing](../README.md#not-there)\n")

        self.assertEqual(
            ["evals/guide.md:1: anchor not found in README.md: #not-there"],
            check_documentation(self.root),
        )

    def test_external_links_are_ignored(self):
        self.write_eval(
            "[Web](https://example.com/missing)\n"
            "[Mail](mailto:test@example.com)\n"
            "[Host](//example.com/missing)\n"
        )

        self.assertEqual([], check_documentation(self.root))

    def test_code_and_images_are_ignored(self):
        content = (
            "`^[a-z0-9]([a-z0-9-]{0,62}[a-z0-9])?$`\n"
            "![Missing image](missing.png)\n"
            "```md\n[Missing](missing.md)\n```\n"
        )

        self.assertEqual([], extract_links(content))

    def test_duplicate_headings_receive_suffixes(self):
        anchors = heading_anchors("# Result\n## Result\n### Result\n")

        self.assertEqual({"result", "result-1", "result-2"}, anchors)

    def test_underscores_are_retained_in_heading_anchors(self):
        anchors = heading_anchors("## depends_on conditions\n")

        self.assertEqual({"depends_on-conditions"}, anchors)

    def test_code_span_text_is_retained_in_heading_anchors(self):
        anchors = heading_anchors("## `kits:` reference\n")

        self.assertEqual({"kits-reference"}, anchors)

    def test_encoded_fragment_matches_heading(self):
        self.write_eval("[Encoded](../README.md#install%61tion)\n")

        self.assertEqual([], check_documentation(self.root))

    def test_link_outside_repository_fails(self):
        source = self.write_eval("[Outside](../../outside.md)\n")

        self.assertEqual(
            "target escapes repository: ../../outside.md",
            check_link(source, 1, "../../outside.md", self.root),
        )


if __name__ == "__main__":
    unittest.main()

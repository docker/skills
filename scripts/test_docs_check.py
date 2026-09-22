import tempfile
import unittest
from pathlib import Path

from docs_check import (
    CANONICAL_BASE,
    expected_canonical,
    validate_built_site,
    validate_canonicals,
    validate_portable_links,
)


class DocsCheckTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        (self.root / "docs" / "guide").mkdir(parents=True)

    def tearDown(self):
        self.temp.cleanup()

    def write_page(self, relative: str, canonical: str | None = None, body: str = "") -> Path:
        path = self.root / "docs" / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        canonical_line = f"canonical: {canonical}\n" if canonical is not None else ""
        path.write_text(
            f"---\ntitle: {path.parent.name.title()}\n{canonical_line}---\n\n# Page\n\n{body}",
            encoding="utf-8",
        )
        return path

    def test_expected_canonical_maps_index_and_leaf_pages(self):
        docs = self.root / "docs"
        self.assertEqual(expected_canonical(docs / "index.md", docs), CANONICAL_BASE)
        self.assertEqual(
            expected_canonical(docs / "guide" / "index.md", docs),
            CANONICAL_BASE + "guide/",
        )
        self.assertEqual(
            expected_canonical(docs / "guide" / "advanced.md", docs),
            CANONICAL_BASE + "guide/advanced/",
        )

    def test_canonical_validation_accepts_path_derived_values(self):
        self.write_page("index.md", CANONICAL_BASE)
        self.write_page("guide/index.md", CANONICAL_BASE + "guide/")
        self.assertEqual(validate_canonicals(self.root), [])

    def test_canonical_validation_rejects_missing_and_stale_values(self):
        self.write_page("index.md")
        self.write_page("guide/index.md", CANONICAL_BASE + "copied/")
        errors = validate_canonicals(self.root)
        self.assertEqual(len(errors), 2)
        self.assertTrue(any("got None" in error for error in errors))
        self.assertTrue(
            any("got 'https://docs.docker.com/ai/skills/copied/'" in error for error in errors)
        )

    def test_portable_links_require_relative_markdown_destinations(self):
        self.write_page(
            "index.md",
            CANONICAL_BASE,
            "[Good](guide/index.md) [External](https://example.com) [Anchor](#page)\n",
        )
        self.write_page(
            "guide/index.md",
            CANONICAL_BASE + "guide/",
            "[Absolute](/guide/) [Rendered](../catalog/)\n",
        )
        errors = validate_portable_links(self.root)
        self.assertEqual(len(errors), 2)
        self.assertIn("use a relative Markdown link", errors[0])
        self.assertIn("must end in .md", errors[1])

    def test_built_output_requires_canonical_tags_and_complete_llms_entries(self):
        self.write_page("index.md", CANONICAL_BASE)
        self.write_page("guide/advanced.md", CANONICAL_BASE + "guide/advanced/")
        output = self.root / "public"
        (output / "guide" / "advanced").mkdir(parents=True)
        (output / "index.html").write_text(
            f'<link rel="canonical" href="{CANONICAL_BASE}">', encoding="utf-8"
        )
        (output / "guide" / "advanced" / "index.html").write_text(
            f'<link rel="canonical" href="{CANONICAL_BASE}guide/advanced/">', encoding="utf-8"
        )
        (output / "llms.txt").write_text(
            "# Docker Skills\n\n> Docker-authored knowledge skills for AI coding agents.\n\n"
            "- [Guide](https://docker.github.io/skills/guide/advanced/): Summary\n",
            encoding="utf-8",
        )
        self.assertEqual(validate_built_site(self.root, output), [])

        (output / "guide" / "advanced" / "index.html").write_text("missing", encoding="utf-8")
        (output / "llms.txt").write_text("# Broken\n", encoding="utf-8")
        errors = validate_built_site(self.root, output)
        self.assertTrue(any("canonical tag" in error for error in errors))
        self.assertTrue(any("expected title and summary" in error for error in errors))
        self.assertTrue(any("expected exactly one entry" in error for error in errors))

    def test_output_path_supports_index_and_leaf_pages(self):
        from docs_check import output_path

        docs = self.root / "docs"
        self.assertEqual(output_path(docs / "index.md", docs), Path("index.html"))
        self.assertEqual(output_path(docs / "guide" / "index.md", docs), Path("guide/index.html"))
        self.assertEqual(output_path(docs / "guide" / "advanced.md", docs), Path("guide/advanced/index.html"))


if __name__ == "__main__":
    unittest.main()

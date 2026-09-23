import tempfile
import unittest
from pathlib import Path

from docs_check import (
    CANONICAL_BASE,
    expected_canonical,
    validate_built_site,
    validate_canonicals,
    validate_install_model_sections,
    validate_navigation,
    validate_portable_links,
    validate_skill_references,
)


class DocsCheckTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        (self.root / "docs" / "guide").mkdir(parents=True)
        (self.root / "docs" / "layouts" / "_default").mkdir(parents=True)
        (self.root / "docs" / "layouts" / "_default" / "baseof.html").write_text(
            '{{ range slice "guide" }}<a>{{ .Title }}</a>{{ end }}\n', encoding="utf-8"
        )
        (self.root / "docs" / "hugo.yaml").write_text(
            "module:\n  mounts:\n    - source: index.md\n      target: content/_index.md\n"
            "    - source: guide\n      target: content/guide\n",
            encoding="utf-8",
        )
        (self.root / "catalog.yaml").write_text(
            "skills:\n  - id: docker-known\n", encoding="utf-8"
        )

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
            expected_canonical(docs / "guide" / "_index.md", docs),
            CANONICAL_BASE + "guide/",
        )
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

    def test_navigation_requires_every_page_source_to_be_mounted(self):
        self.write_page("index.md", CANONICAL_BASE)
        self.write_page("guide/index.md", CANONICAL_BASE + "guide/")
        self.assertEqual(validate_navigation(self.root), [])

        self.write_page("missing/index.md", CANONICAL_BASE + "missing/")
        errors = validate_navigation(self.root)
        self.assertEqual(len(errors), 2)
        self.assertTrue(any("missing docs/hugo.yaml module mount" in error for error in errors))
        self.assertTrue(any("missing from navigation" in error for error in errors))

    def test_navigation_rejects_page_missing_from_nav(self):
        self.write_page("index.md", CANONICAL_BASE)
        self.write_page("guide/index.md", CANONICAL_BASE + "guide/")
        layout = self.root / "docs" / "layouts" / "_default" / "baseof.html"
        layout.write_text("<nav></nav>\n", encoding="utf-8")
        errors = validate_navigation(self.root)
        self.assertEqual(len(errors), 1)
        self.assertIn("documentation page 'guide' is missing from navigation", errors[0])

    def test_navigation_rejects_entry_without_page(self):
        self.write_page("index.md", CANONICAL_BASE)
        layout = self.root / "docs" / "layouts" / "_default" / "baseof.html"
        layout.write_text('{{ range slice "missing" }}{{ end }}\n', encoding="utf-8")
        errors = validate_navigation(self.root)
        self.assertEqual(len(errors), 1)
        self.assertIn("navigation entry 'missing' has no documentation page", errors[0])

    def test_skill_references_must_exist_in_catalog(self):
        self.write_page(
            "index.md",
            CANONICAL_BASE,
            "Use `docker-known`, not `docker-missing`. The `docker-skills-docs` image and `docker-compose` product are allowed.\n",
        )
        errors = validate_skill_references(
            self.root, {"docker-known"}, {"docker-skills", "docker-compose"}
        )
        self.assertEqual(len(errors), 1)
        self.assertIn("unknown catalog skill reference `docker-missing`", errors[0])

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

    def test_install_model_pages_require_complete_section_contract(self):
        install = self.root / "docs" / "install"
        install.mkdir()
        required = (
            "Basic install",
            "Advanced install",
            "Update, pin, and scope",
            "Verification",
            "Troubleshooting",
            "Related links",
        )
        for name in ("native-marketplaces.md", "extensions.md", "skills-cli.md", "docker-products.md", "sources.md"):
            (install / name).write_text("\n".join("## " + section for section in required), encoding="utf-8")
        self.assertEqual(validate_install_model_sections(self.root), [])
        (install / "sources.md").write_text("## Basic install\n", encoding="utf-8")
        errors = validate_install_model_sections(self.root)
        self.assertEqual(len(errors), 5)
        self.assertTrue(any("Update, pin, and scope" in error for error in errors))

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

        (output / "llms.txt").write_text(
            "# Docker Skills\n\n> Docker-authored knowledge skills for AI coding agents.\n\n"
            "- [Docker Skills](https://docker.github.io/skills/): Summary\n"
            "- [Guide](https://docker.github.io/skills/guide/advanced/): Summary\n",
            encoding="utf-8",
        )
        self.assertTrue(any("must not list the home page" in error for error in validate_built_site(self.root, output)))

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
        self.assertEqual(output_path(docs / "guide" / "_index.md", docs), Path("guide/index.html"))
        self.assertEqual(output_path(docs / "guide" / "index.md", docs), Path("guide/index.html"))
        self.assertEqual(output_path(docs / "guide" / "advanced.md", docs), Path("guide/advanced/index.html"))


if __name__ == "__main__":
    unittest.main()

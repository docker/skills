import json
from pathlib import Path
import unittest
import xml.etree.ElementTree as ET

from manifests import (
    collect_descriptions,
    collect_versions,
    validate_claude_marketplace_controls,
    validate_codex_marketplace,
    validate_descriptions,
    validate_skills_index,
    validate_versions,
)


class ClaudeMarketplaceControlsTests(unittest.TestCase):
    classification = {
        "object_acted_on": "code",
        "work_department": "engineering",
        "industry": "software development",
        "life_area": "work",
        "subject": "container development",
    }

    def test_checked_in_manifests(self):
        root = Path(__file__).resolve().parent.parent / ".claude-plugin"
        marketplace = json.loads((root / "marketplace.json").read_text(encoding="utf-8"))
        plugin = json.loads((root / "plugin.json").read_text(encoding="utf-8"))
        self.assertEqual(validate_claude_marketplace_controls(marketplace, plugin), [])
        self.assertEqual(marketplace["plugins"][0]["classification"], self.classification)
        self.assertNotIn("category", marketplace["plugins"][0])
        self.assertNotIn("category", plugin)

    def test_each_entry_requires_five_non_empty_string_fields(self):
        marketplace = {"plugins": [{"classification": self.classification.copy()}, {"classification": {}}]}
        errors = validate_claude_marketplace_controls(marketplace, {})
        self.assertEqual(len(errors), 5)
        self.assertTrue(all("plugins[1].classification" in error for error in errors))
        marketplace["plugins"][1]["classification"] = self.classification | {"industry": "  ", "subject": 4}
        errors = validate_claude_marketplace_controls(marketplace, {})
        self.assertEqual(len(errors), 2)
        self.assertTrue(any(".industry" in error for error in errors))
        self.assertTrue(any(".subject" in error for error in errors))

    def test_missing_classification_and_deprecated_category(self):
        marketplace = {"plugins": [{"category": "workflow"}]}
        errors = validate_claude_marketplace_controls(marketplace, {"category": "workflow"})
        self.assertEqual(len(errors), 3)
        self.assertTrue(any("plugins[0].classification must be an object" in error for error in errors))
        self.assertTrue(any("plugin.json has deprecated field: category" in error for error in errors))
        self.assertTrue(any("plugins[0] has deprecated field: category" in error for error in errors))

    def test_marketplace_category_is_rejected_even_with_valid_classification(self):
        marketplace = {"plugins": [{"classification": self.classification, "category": "workflow"}]}
        self.assertEqual(
            validate_claude_marketplace_controls(marketplace, {}),
            [".claude-plugin/marketplace.json plugins[0] has deprecated field: category"],
        )


class ClaudePluginIconTests(unittest.TestCase):
    def test_checked_in_icon_is_plain_square_docker_mark(self):
        root = Path(__file__).resolve().parent.parent
        plugin = json.loads((root / ".claude-plugin/plugin.json").read_text(encoding="utf-8"))
        self.assertEqual(plugin["icon"], "./.claude-plugin/docker.svg")
        icon = root / plugin["icon"]
        content = icon.read_bytes()
        self.assertLess(len(content), 2 * 1024 * 1024)
        text = content.decode("utf-8")
        self.assertTrue(text.startswith("<svg "))
        self.assertNotRegex(text, r"(?i)<!|<\?|\b(?:xmlns:|xlink:|url\s*\(|(?:href|on[a-z]+)\s*=)")

        svg = ET.fromstring(content)
        self.assertEqual(svg.tag, "{http://www.w3.org/2000/svg}svg")
        self.assertEqual(svg.attrib, {"width": "340", "height": "340", "viewBox": "0 -36 340 340"})
        self.assertEqual(len(svg), 1)
        path = svg[0]
        self.assertEqual(path.tag, "{http://www.w3.org/2000/svg}path")
        self.assertEqual(len(path), 0)
        self.assertEqual(set(path.attrib), {"d", "fill"})
        self.assertEqual(path.attrib["fill"], "#2560ff")
        self.assertTrue(path.attrib["d"].startswith("M334,110.1"))
        self.assertFalse((svg.text or "").strip())
        self.assertFalse((path.text or "").strip())
        self.assertFalse((path.tail or "").strip())


class ClaudePluginListingLinkTests(unittest.TestCase):
    def test_directory_listing_links_are_declared(self):
        root = Path(__file__).resolve().parent.parent
        plugin = json.loads((root / ".claude-plugin/plugin.json").read_text(encoding="utf-8"))
        marketplace = json.loads((root / ".claude-plugin/marketplace.json").read_text(encoding="utf-8"))
        self.assertEqual(
            {key: plugin.get(key) for key in (
                "homepage", "repository", "documentationUrl", "supportUrl",
                "privacyPolicyUrl", "termsOfServiceUrl",
            )},
            {
                "homepage": "https://www.docker.com/",
                "repository": "https://github.com/docker/skills",
                "documentationUrl": "https://docs.docker.com/ai/skills/",
                "supportUrl": "https://github.com/docker/skills/issues",
                "privacyPolicyUrl": "https://www.docker.com/legal/privacy/",
                "termsOfServiceUrl": "https://www.docker.com/legal/docker-terms-use/",
            },
        )
        self.assertEqual(marketplace["plugins"][0]["homepage"], plugin["homepage"])


class SkillsIndexTests(unittest.TestCase):
    catalog = ["a", "b", "c"]

    def index(self, *groups, **extra):
        return {"groupings": [{"title": t, "skills": list(s)} for t, s in groups], **extra}

    def test_valid_index(self):
        self.assertEqual(validate_skills_index(self.index(("One", "ab"), ("Two", "c")), self.catalog), [])

    def test_every_catalog_skill_must_be_listed(self):
        errors = validate_skills_index(self.index(("One", "ab")), self.catalog)
        self.assertEqual(len(errors), 1)
        self.assertIn("does not list catalog skill 'c'", errors[0])

    def test_unknown_and_duplicate_skills(self):
        errors = validate_skills_index(self.index(("One", "abz"), ("Two", "ca")), self.catalog)
        self.assertTrue(any("unknown skill 'z'" in e for e in errors))
        self.assertTrue(any("lists 'a' twice" in e for e in errors))

    def test_structure_errors(self):
        self.assertTrue(validate_skills_index([], self.catalog))
        self.assertTrue(validate_skills_index({}, self.catalog))
        self.assertTrue(validate_skills_index({"groupings": [{"title": "", "skills": ["a"]}]}, ["a"]))
        self.assertTrue(validate_skills_index({"groupings": [{"title": "T", "skills": []}]}, ["a"]))
        self.assertTrue(validate_skills_index({"groupings": [{"title": "T", "skills": ["a"], "extra": 1}]}, ["a"]))
        self.assertTrue(validate_skills_index(self.index(("One", "abc"), notGrouped="middle"), self.catalog))
        self.assertTrue(
            validate_skills_index(
                {"groupings": [{"title": "T", "description": "d" * 501, "skills": ["a"]}]}, ["a"]
            )
        )


class CodexMarketplaceTests(unittest.TestCase):
    def manifest(self, **plugin_overrides):
        plugin = {
            "name": "p",
            "source": {"source": "url", "url": "https://example.com/repo.git"},
            "policy": {"installation": "AVAILABLE"},
        }
        plugin.update(plugin_overrides)
        return {"name": "m", "interface": {"displayName": "M"}, "plugins": [plugin]}

    def test_valid(self):
        self.assertEqual(validate_codex_marketplace(self.manifest(), "m.json"), [])
        local = self.manifest(source={"source": "local", "path": "./plugins/p"})
        self.assertEqual(validate_codex_marketplace(local, "m.json"), [])

    def test_missing_fields(self):
        self.assertTrue(validate_codex_marketplace({"plugins": []}, "m.json"))
        self.assertTrue(validate_codex_marketplace(self.manifest(source="./"), "m.json"))
        self.assertTrue(validate_codex_marketplace(self.manifest(source={"source": "local"}), "m.json"))
        self.assertTrue(validate_codex_marketplace(self.manifest(source={"source": "url"}), "m.json"))
        self.assertTrue(validate_codex_marketplace(self.manifest(policy={}), "m.json"))


class DescriptionTests(unittest.TestCase):
    def test_collects_top_level_and_plugin_descriptions(self):
        manifests = {
            "plugin.json": {"description": "Canonical"},
            "marketplace.json": {"plugins": [{"description": "Canonical"}]},
        }
        self.assertEqual(len(collect_descriptions(manifests)), 2)
        self.assertEqual(validate_descriptions(manifests, "Canonical"), [])

    def test_reports_stale_descriptions(self):
        errors = validate_descriptions(
            {"plugin.json": {"description": "Stale"}, "other.json": {}},
            "Canonical",
        )
        self.assertEqual(errors, ["plugin.json does not match catalog description"])


class VersionTests(unittest.TestCase):
    def test_collects_plugin_metadata_and_entry_versions(self):
        versions = collect_versions(
            {
                "plugin.json": {"version": "1.0.0"},
                "marketplace.json": {"metadata": {"version": "1.0.0"}, "plugins": [{"version": "1.0.0"}]},
                "codex.json": {"plugins": [{"name": "no-version"}]},
            }
        )
        self.assertEqual(len(versions), 3)
        self.assertEqual(set(versions.values()), {"1.0.0"})

    def test_agreeing_versions_pass_and_disagreeing_fail(self):
        self.assertEqual(validate_versions({"a": {"version": "1"}, "b": {"version": "1"}}), [])
        errors = validate_versions({"a": {"version": "1"}, "b": {"version": "2"}})
        self.assertEqual(len(errors), 1)
        self.assertIn("a=1", errors[0])
        self.assertIn("b=2", errors[0])


if __name__ == "__main__":
    unittest.main()

import copy
import json
import os
import tempfile
import unittest

import yaml

from catalog import (
    CATALOG_END,
    CATALOG_START,
    DISTRIBUTION_END,
    DISTRIBUTION_START,
    MANIFESTS,
    PUBLISHED_DISTRIBUTION_MANIFESTS,
    generated_files,
    release_tag,
    render_distribution_inventory,
    render_evals_table,
    render_manifest,
    render_manifest_version,
    render_readme_table,
    render_skills_index,
    replace_section,
    stale_files,
    validate_catalog,
    write_generated,
)

CATALOG = {
    "schema": "v1",
    "name": "test",
    "version": "1.2.3",
    "description": "Docker skills for tests.",
    "distributions": [
        {
            "id": "test-cli",
            "category": "skills-cli",
            "name": "Test CLI",
            "description": "Installs test skills.",
            "docs": "https://docs.docker.com/ai/skills/install/#skills-cli",
            "role": "installer",
            "manifests": list(PUBLISHED_DISTRIBUTION_MANIFESTS),
        }
    ],
    "overview": "docker",
    "products": [
        {"id": "build", "name": "Build", "description": "Images.", "docs": "https://example.com/build"},
        {"id": "agent", "name": "Agent", "description": "Agents.", "repo": "https://example.com/agent"},
    ],
    "skills": [
        {"id": "docker", "path": "skills/docker", "version": "0.1.0", "status": "stable"},
        {"id": "build-a", "product": "build", "path": "skills/build-a", "version": "0.1.0", "status": "stable"},
        {"id": "agent-a", "product": "agent", "path": "skills/agent-a", "version": "0.1.0", "status": "experimental"},
    ],
}
DESCRIPTIONS = {"docker": "Routes.", "build-a": "Builds.", "agent-a": "Agents."}


def catalog(**overrides):
    data = copy.deepcopy(CATALOG)
    data.update(overrides)
    return data


class ValidateCatalogTests(unittest.TestCase):
    def test_valid(self):
        self.assertEqual(validate_catalog(CATALOG), [])

    def test_catalog_version_must_be_strict_semver_string(self):
        for bad in (None, 1.2, "v1.2.3", "1.2", "1.2.3-rc.1", "01.2.3", " 1.2.3"):
            data = catalog(version=bad)
            self.assertTrue(any("'version' must be a string in X.Y.Z format" in e for e in validate_catalog(data)))

    def test_catalog_description_is_required_bounded_and_manifest_safe(self):
        for bad in (None, "", "   ", 1, "x" * 501, 'has "quotes"', "has\\slash", "has\nnewline"):
            data = catalog(description=bad)
            self.assertTrue(any("'description' must" in e for e in validate_catalog(data)))

    def test_skill_version_must_be_strict_semver_string(self):
        for bad in (None, 1.2, "v1.2.3", "1.2", "1.2.3-rc.1", "01.2.3", " 1.2.3"):
            data = catalog()
            data["skills"][1]["version"] = bad
            self.assertTrue(
                any(
                    "skill 'build-a' 'version' must be a string in X.Y.Z format" in error
                    for error in validate_catalog(data)
                )
            )

    def test_release_tag_prefixes_catalog_version(self):
        self.assertEqual(release_tag(CATALOG), "v1.2.3")

    def test_status_defaults_to_stable_when_omitted(self):
        data = catalog()
        del data["skills"][1]["status"]
        self.assertEqual(validate_catalog(data), [])

    def test_structure_errors(self):
        self.assertTrue(validate_catalog([]))
        self.assertTrue(validate_catalog({"skills": CATALOG["skills"]}))
        self.assertTrue(validate_catalog({"products": CATALOG["products"]}))

    def test_duplicate_ids_and_paths(self):
        data = catalog()
        data["skills"].append(dict(data["skills"][1]))
        errors = validate_catalog(data)
        self.assertTrue(any("lists skill 'build-a' twice" in e for e in errors))
        self.assertTrue(any("lists path 'skills/build-a' twice" in e for e in errors))
        data = catalog()
        data["products"].append(dict(data["products"][0]))
        self.assertTrue(any("product 'build' twice" in e for e in validate_catalog(data)))

    def test_path_must_end_with_id(self):
        data = catalog()
        data["skills"][1]["path"] = "skills/other"
        self.assertTrue(any("must end with the skill id" in e for e in validate_catalog(data)))

    def test_unknown_product_and_missing_product(self):
        data = catalog()
        data["skills"][1]["product"] = "nope"
        self.assertTrue(any("unknown product 'nope'" in e for e in validate_catalog(data)))
        data = catalog()
        del data["skills"][1]["product"]
        errors = validate_catalog(data)
        self.assertTrue(any("skill 'build-a' missing 'product'" in e for e in errors))
        self.assertTrue(any("product 'build' has no skills" in e for e in errors))

    def test_overview_rules(self):
        data = catalog()
        data["skills"][0]["product"] = "build"
        self.assertTrue(any("overview skill and must not declare a 'product'" in e for e in validate_catalog(data)))
        data = catalog(overview="missing")
        errors = validate_catalog(data)
        self.assertTrue(any("overview skill 'missing' is not listed" in e for e in errors))
        self.assertTrue(any("skill 'docker' missing 'product'" in e for e in errors))

    def test_distribution_manifest_mapping_must_be_exactly_once(self):
        data = catalog()
        self.assertEqual(validate_catalog(data), [])
        data["distributions"][0]["manifests"].pop()
        self.assertTrue(any("is not mapped" in error for error in validate_catalog(data)))
        data = catalog()
        data["distributions"].append(
            {
                "id": "duplicate",
                "category": "skills-cli",
                "name": "Duplicate",
                "description": "Duplicate.",
                "docs": "https://docs.docker.com/ai/skills/install/#skills-cli",
                "role": "installer",
                "manifests": [PUBLISHED_DISTRIBUTION_MANIFESTS[0]],
            }
        )
        self.assertTrue(any("is mapped by both" in error for error in validate_catalog(data)))

    def test_distribution_docs_requires_canonical_install_anchor(self):
        invalid_urls = (
            None,
            "docs/install/skills-cli.md",
            "http://docs.docker.com/ai/skills/install/#skills-cli",
            "https://example.com/ai/skills/install/#skills-cli",
            "https://docs.docker.com/ai/skills/install/#",
        )
        for bad in invalid_urls:
            data = catalog()
            data["distributions"][0]["docs"] = bad
            self.assertTrue(
                any("docs must be a https://docs.docker.com/ai/skills/install/" in error
                    for error in validate_catalog(data)),
                bad,
            )
        data = catalog()
        data["distributions"][0]["page"] = "docs/install/skills-cli.md"
        self.assertTrue(any("unsupported fields: page" in error for error in validate_catalog(data)))

    def test_bad_status_urls_and_unknown_fields(self):
        data = catalog()
        data["skills"][1]["status"] = "beta"
        self.assertTrue(any("status 'beta'" in e for e in validate_catalog(data)))
        data = catalog()
        data["products"][0]["docs"] = "docs.docker.com"
        self.assertTrue(any("'docs' must be an http(s) URL" in e for e in validate_catalog(data)))
        data = catalog()
        data["products"][0]["colour"] = "blue"
        data["skills"][1]["owner"] = "me"
        errors = validate_catalog(data)
        self.assertTrue(any("products[0] has unsupported fields: colour" in e for e in errors))
        self.assertTrue(any("skill 'build-a' has unsupported fields: owner" in e for e in errors))


class RenderTests(unittest.TestCase):
    def test_readme_table_groups_by_product_with_overview_first(self):
        table = render_readme_table(CATALOG, DESCRIPTIONS)
        lines = table.strip().splitlines()
        self.assertEqual(lines[0], "| Product | Description | Skills |")
        self.assertTrue(lines[2].startswith("| **Start here** |"))
        self.assertIn("[`docker`](skills/docker) — Routes.", lines[2])
        self.assertIn("**[Build](https://example.com/build)**", lines[3])
        self.assertIn("[`build-a`](skills/build-a) — Builds.", lines[3])
        self.assertIn("**Agent**<br>[source](https://example.com/agent)", lines[4])
        self.assertIn("[`agent-a`](skills/agent-a) *(experimental)* — Agents.", lines[4])
        self.assertEqual(len(lines), 5)

    def test_readme_table_without_overview(self):
        data = catalog()
        del data["overview"]
        data["skills"] = data["skills"][1:]
        table = render_readme_table(data, DESCRIPTIONS)
        self.assertNotIn("Start here", table)
        self.assertEqual(len(table.strip().splitlines()), 4)

    def test_distribution_inventory_groups_models_and_links_to_install_anchors(self):
        rendered = render_distribution_inventory(CATALOG)
        self.assertIn("### skills CLI", rendered)
        self.assertIn("[Test CLI](https://docs.docker.com/ai/skills/install/#skills-cli)", rendered)

    def test_evals_table_lists_every_skill_overview_first(self):
        table = render_evals_table(CATALOG)
        lines = table.strip().splitlines()
        self.assertEqual(lines[2], "| docker | [docker.md](docker.md) |")
        self.assertEqual(lines[3], "| build-a | [build-a.md](build-a.md) |")
        self.assertEqual(len(lines), 5)

    def test_skills_index_has_one_grouping_per_product_plus_start_here(self):
        index = json.loads(render_skills_index(CATALOG))
        self.assertEqual(index["$schema"], "https://skills.sh/schemas/skills.sh.schema.json")
        self.assertEqual(index["notGrouped"], "bottom")
        titles = [g["title"] for g in index["groupings"]]
        self.assertEqual(titles, ["Start here", "Build", "Agent"])
        listed = [s for g in index["groupings"] for s in g["skills"]]
        self.assertEqual(listed, ["docker", "build-a", "agent-a"])
        self.assertEqual(index["groupings"][1]["description"], "Images.")

    def test_manifest_rendering_replaces_versions_and_descriptions(self):
        content = '{\n  "version": "0.0.1",\n  "description": "Old",\n  "plugins": [{"version": "0.0.1", "description": "Stale"}]\n}\n'
        rendered = render_manifest(content, "1.2.3", "Docker skills for tests.")
        self.assertNotIn("0.0.1", rendered)
        self.assertNotIn("Old", rendered)
        self.assertNotIn("Stale", rendered)
        self.assertEqual(rendered.count("Docker skills for tests."), 2)

    def test_manifest_version_rendering_preserves_format_and_replaces_all_occurrences(self):
        content = '{\n\t"version" : "0.0.1",\n  "metadata": {"version":"2.0.0"},\n  "plugins": [{"version": "3.0.0"}]\n}\n'
        self.assertEqual(
            render_manifest_version(content, "1.2.3"),
            '{\n\t"version" : "1.2.3",\n  "metadata": {"version":"1.2.3"},\n  "plugins": [{"version": "1.2.3"}]\n}\n',
        )

    def test_versionless_manifest_is_unchanged(self):
        content = '{\n  "name": "plugin"\n}\n'
        self.assertEqual(render_manifest_version(content, "1.2.3"), content)

    def test_replace_section(self):
        content = "before\n" + CATALOG_START + "\nold\n" + CATALOG_END + "\nafter\n"
        self.assertEqual(
            replace_section(content, "new\n"),
            "before\n" + CATALOG_START + "\nnew\n" + CATALOG_END + "\nafter\n",
        )
        with self.assertRaises(ValueError):
            replace_section("no markers", "new\n")
        with self.assertRaises(ValueError):
            replace_section(CATALOG_END + "\n" + CATALOG_START, "new\n")


class GeneratedFilesTests(unittest.TestCase):
    def make_repo(self):
        root = tempfile.mkdtemp()
        with open(os.path.join(root, "catalog.yaml"), "w") as handle:
            yaml.safe_dump(CATALOG, handle)
        for skill in CATALOG["skills"]:
            os.makedirs(os.path.join(root, skill["path"]))
            with open(os.path.join(root, skill["path"], "skill.yaml"), "w") as handle:
                yaml.safe_dump({"description": DESCRIPTIONS[skill["id"]]}, handle)
        os.makedirs(os.path.join(root, "evals"))
        for rel in ("README.md", os.path.join("evals", "README.md")):
            with open(os.path.join(root, rel), "w") as handle:
                handle.write("# Title\n\n" + CATALOG_START + "\n" + CATALOG_END + "\n" + DISTRIBUTION_START + "\n" + DISTRIBUTION_END + "\n")
        for rel in MANIFESTS:
            path = os.path.join(root, rel)
            os.makedirs(os.path.dirname(path) or root, exist_ok=True)
            with open(path, "w") as handle:
                if "marketplace" in rel:
                    handle.write('{\n  "metadata": {"version": "0.0.1"},\n  "plugins": [{"version": "0.0.1", "description": "Stale"}]\n}\n')
                else:
                    handle.write('{\n  "version": "0.0.1",\n  "description": "Stale"\n}\n')
        return root

    def test_write_then_check_round_trip(self):
        root = self.make_repo()
        expected = sorted(["README.md", "evals/README.md", "skills.sh.json", *MANIFESTS])
        self.assertEqual(sorted(stale_files(root)), expected)
        changed = write_generated(root)
        self.assertEqual(sorted(changed), expected)
        self.assertEqual(stale_files(root), [])
        self.assertEqual(write_generated(root), [])
        readme = open(os.path.join(root, "README.md")).read()
        self.assertTrue(readme.startswith("# Title\n\n" + CATALOG_START + "\n| Product |"))
        self.assertIn("[`agent-a`](skills/agent-a) *(experimental)* — Agents.", readme)
        generated = generated_files(root)
        self.assertEqual(set(generated), {"README.md", "evals/README.md", "skills.sh.json", *MANIFESTS})
        for rel in MANIFESTS:
            manifest = open(os.path.join(root, rel)).read()
            self.assertNotIn("0.0.1", manifest)
            self.assertIn('"version": "1.2.3"', manifest)
            self.assertNotIn("Stale", manifest)
            if '"description"' in manifest:
                self.assertIn("Docker skills for tests.", manifest)

    def test_hand_edit_is_detected(self):
        root = self.make_repo()
        write_generated(root)
        with open(os.path.join(root, "skills.sh.json"), "a") as handle:
            handle.write("\n")
        self.assertEqual(stale_files(root), ["skills.sh.json"])

    def test_missing_skill_yaml_description_renders_link_only(self):
        root = self.make_repo()
        os.remove(os.path.join(root, "skills", "build-a", "skill.yaml"))
        write_generated(root)
        readme = open(os.path.join(root, "README.md")).read()
        self.assertIn("[`build-a`](skills/build-a) |", readme)


if __name__ == "__main__":
    unittest.main()

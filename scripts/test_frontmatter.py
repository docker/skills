import unittest

import yaml

from frontmatter import validate_frontmatter


class FrontmatterTests(unittest.TestCase):
    def document(self, **overrides):
        data = {"name": "test-skill", "description": "A test skill."}
        data.update(overrides)
        return "---\n" + yaml.safe_dump(data, allow_unicode=True) + "---\n# Body\n"

    def test_optional_compatibility(self):
        self.assertEqual(validate_frontmatter(self.document(), "test-skill"), [])

    def test_length_boundaries(self):
        for field, limit in (("description", 1024), ("compatibility", 500), ("name", 64)):
            for length in (limit, limit + 1):
                with self.subTest(field=field, length=length):
                    value = "a" * length
                    name = value if field == "name" else "test-skill"
                    errors = validate_frontmatter(self.document(**{field: value}), name)
                    self.assertEqual(bool(errors), length > limit)

    def test_invalid_field_types_and_empty_values(self):
        for field in ("name", "description", "compatibility"):
            for value in (None, True, 42, [], {}, "", " \n "):
                with self.subTest(field=field, value=value):
                    self.assertTrue(validate_frontmatter(self.document(**{field: value}), "test-skill"))

    def test_malformed_documents(self):
        for document in (
            "name: test-skill\n",
            "---\nname: test-skill\n",
            "---\nname: [\n---\n",
            "---\nname: test-skill\ndescription: Use kind: sandbox\n---\n",
            "---\n- list\n---\n",
            "---\n---\n",
            "---\nname: test-skill\n---\n",
        ):
            with self.subTest(document=document):
                self.assertTrue(validate_frontmatter(document, "test-skill"))

    def test_invalid_names(self):
        for name in ("Bad", "-bad", "bad-", "bad--name", "bad_name", "bad.name", "bad name"):
            with self.subTest(name=name):
                self.assertTrue(validate_frontmatter(self.document(name=name), name))
        self.assertTrue(validate_frontmatter(self.document(), "another-skill"))

    def test_unicode_character_lengths(self):
        self.assertEqual(
            validate_frontmatter(self.document(compatibility="é" * 500), "test-skill"), []
        )

    def test_optional_field_types(self):
        self.assertEqual(
            validate_frontmatter(
                self.document(license="Apache-2.0", metadata={"version": "1"}, **{"allowed-tools": "Read"}),
                "test-skill",
            ),
            [],
        )
        for field, value in (("license", []), ("allowed-tools", []), ("metadata", []), ("metadata", {"version": 1})):
            with self.subTest(field=field):
                self.assertTrue(validate_frontmatter(self.document(**{field: value}), "test-skill"))


if __name__ == "__main__":
    unittest.main()

from pathlib import Path
import re
import unittest

import yaml

from eval_check import CHECKS_FILE, FAIL, PASS, REPO_ROOT, run_check


class YAMLAssertionTests(unittest.TestCase):
    def check(self, kind, data, **fields):
        check = {"id": "test", "description": "test", "type": kind, "key": "field", **fields}
        return run_check(check, "", data, "fixture.yaml")["status"]

    def test_absent_is_not_null_or_false(self):
        self.assertEqual(self.check("yaml_key_absent", {}), PASS)
        for value in (None, False, "", [], {}):
            with self.subTest(value=value):
                self.assertEqual(self.check("yaml_key_absent", {"field": value}), FAIL)
        self.assertEqual(self.check("yaml_key_absent", {"parent": {}}, key="parent.child"), PASS)
        self.assertEqual(self.check("yaml_key_absent", {"parent": {"child": None}}, key="parent.child"), FAIL)

    def test_equals_preserves_scalar_types(self):
        for value in ("1", 1, True, None):
            with self.subTest(value=value):
                self.assertEqual(self.check("yaml_value_equals", {"field": value}, value=value), PASS)
        for actual, expected in ((1, "1"), (True, 1), (1, True), ("shell-extra", "shell")):
            with self.subTest(actual=actual, expected=expected):
                self.assertEqual(self.check("yaml_value_equals", {"field": actual}, value=expected), FAIL)
        self.assertEqual(self.check("yaml_value_equals", {}, value=None), FAIL)

    def test_invalid_or_nonmapping_yaml_fails_closed(self):
        for kind in ("yaml_key_absent", "yaml_value_equals"):
            for data in (None, [], "text", 1):
                with self.subTest(kind=kind, data=data):
                    self.assertEqual(self.check(kind, data, value="1"), FAIL)

    def test_unquoted_schema_version_fails(self):
        data = yaml.safe_load("schemaVersion: 2\n")
        self.assertEqual(self.check("yaml_value_equals", data, key="schemaVersion", value="2"), FAIL)


class SandboxPromptCoverageTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.groups = yaml.safe_load(Path(CHECKS_FILE).read_text(encoding="utf-8"))

    def test_each_prompt_has_one_check_group_or_explicit_skip(self):
        paths = sorted(Path(REPO_ROOT, "evals").glob("docker-sandboxes-*.md"))
        self.assertTrue(paths)
        for path in paths:
            with self.subTest(eval=path.stem):
                prompts = re.findall(r"^## (Prompt \d+: .+)$", path.read_text(encoding="utf-8"), re.MULTILINE)
                groups = [
                    group["prompt"] for group in self.groups
                    if group["eval"] == path.stem and group["prompt"].startswith("Prompt ")
                ]
                self.assertCountEqual(prompts, groups)

    def test_skipped_prompts_explain_why(self):
        for group in self.groups:
            if group.get("skip"):
                with self.subTest(eval=group["eval"], prompt=group["prompt"]):
                    self.assertIs(group["skip"], True)
                    reason = group.get("skip_reason")
                    self.assertIsInstance(reason, str)
                    self.assertTrue(reason.strip())


if __name__ == "__main__":
    unittest.main()

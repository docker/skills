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


class NpmCredentialCoverageTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        groups = yaml.safe_load(Path(CHECKS_FILE).read_text(encoding="utf-8"))
        group = next(group for group in groups if group["eval"] == "docker-project-foundations"
                     and "assets" in group)
        cls.checks = {check["id"]: check for check in group["checks"]}
        cls.dockerfile = Path(REPO_ROOT, group["assets"]["dockerfile"]).read_text(encoding="utf-8")
        cls.dockerignore = Path(REPO_ROOT, group["assets"]["dockerignore"]).read_text(encoding="utf-8")

    def status(self, check_id, content):
        return run_check(self.checks[check_id], content, None, "fixture")["status"]

    def test_starter_uses_secret_mounts_and_excludes_npmrc(self):
        for check_id, content in (
            ("fp-p1-secret-installs", self.dockerfile),
            ("fp-p1-no-copy-npmrc", self.dockerfile),
            ("fp-p1-ignore-npmrc", self.dockerignore),
        ):
            with self.subTest(check=check_id):
                self.assertEqual(self.status(check_id, content), PASS)

    def test_either_unmounted_install_fails(self):
        mount = "--mount=type=secret,id=npmrc,target=/root/.npmrc,required=false"
        self.assertEqual(self.dockerfile.count(mount), 2)
        for position in (self.dockerfile.index(mount), self.dockerfile.rindex(mount)):
            with self.subTest(position=position):
                content = self.dockerfile[:position] + self.dockerfile[position:].replace(mount, "", 1)
                self.assertEqual(self.status("fp-p1-secret-installs", content), FAIL)

    def test_required_secret_breaks_public_package_builds(self):
        content = self.dockerfile.replace("required=false", "required=true")
        self.assertEqual(self.status("fp-p1-secret-installs", content), FAIL)

    def test_copying_npmrc_fails(self):
        for instruction in ("COPY .npmrc .", 'COPY [".npmrc", "/app/"]', "add .npmrc /app/"):
            with self.subTest(instruction=instruction):
                content = self.dockerfile + "\n" + instruction + "\n"
                self.assertEqual(self.status("fp-p1-no-copy-npmrc", content), FAIL)

    def test_missing_or_root_only_exclusion_fails(self):
        for replacement in ("", ".npmrc", "# **/.npmrc"):
            with self.subTest(replacement=replacement):
                content = self.dockerignore.replace("**/.npmrc", replacement)
                self.assertEqual(self.status("fp-p1-ignore-npmrc", content), FAIL)


class ComposeDevelopmentDefaultCoverageTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        groups = yaml.safe_load(Path(CHECKS_FILE).read_text(encoding="utf-8"))
        group = next(
            group
            for group in groups
            if group["eval"] == "docker-project-foundations"
            and "assets" in group
        )
        cls.checks = {check["id"]: check for check in group["checks"]}
        cls.compose = Path(REPO_ROOT, group["assets"]["compose"]).read_text(
            encoding="utf-8"
        )
        cls.runbook = Path(REPO_ROOT, group["assets"]["runbook"]).read_text(
            encoding="utf-8"
        )

    def status(self, check_id, content, *, parse_yaml=False):
        data = yaml.safe_load(content) if parse_yaml else None
        return run_check(self.checks[check_id], content, data, "fixture")["status"]

    def test_checked_in_compose_and_runbook_pass(self):
        for check_id in (
            "fp-p1-app-loopback",
            "fp-p1-no-public-datastore",
            "fp-p1-postgres-loopback",
            "fp-p1-cache-port-absent",
            "fp-p1-password-fallback-note",
        ):
            with self.subTest(check=check_id):
                self.assertEqual(
                    self.status(check_id, self.compose, parse_yaml=True), PASS
                )
        for check_id in (
            "fp-p1-runbook-loopback",
            "fp-p1-runbook-no-redis-port",
            "fp-p1-runbook-postgres-loopback",
        ):
            with self.subTest(check=check_id):
                self.assertEqual(self.status(check_id, self.runbook), PASS)

    def test_app_wildcard_fixture_fails_loopback_check(self):
        fixture = self.compose.replace(
            "127.0.0.1:3000:3000", "0.0.0.0:3000:3000"
        )
        self.assertEqual(
            self.status("fp-p1-app-loopback", fixture, parse_yaml=True), FAIL
        )

    def test_public_datastore_fixture_fails(self):
        fixture = self.compose.replace(
            '"127.0.0.1:5432:5432"', '"5432:5432"'
        )
        self.assertEqual(
            self.status("fp-p1-no-public-datastore", fixture, parse_yaml=True), FAIL
        )

    def test_postgres_wildcard_fixture_fails_loopback_check(self):
        fixture = self.compose.replace(
            "127.0.0.1:5432:5432", "0.0.0.0:5432:5432"
        )
        self.assertEqual(
            self.status("fp-p1-postgres-loopback", fixture, parse_yaml=True), FAIL
        )

    def test_redis_port_fixture_fails_absence_check(self):
        fixture = self.compose.replace(
            "  cache:\n    image: redis:7\n",
            "  cache:\n    image: redis:7\n    ports:\n      - \"127.0.0.1:6379:6379\"\n",
        )
        self.assertEqual(
            self.status("fp-p1-cache-port-absent", fixture, parse_yaml=True), FAIL
        )

    def test_missing_password_override_note_fixture_fails(self):
        fixture = self.compose.replace(
            "# Set POSTGRES_PASSWORD in .env to override it for local development.\n",
            "",
        )
        self.assertEqual(
            self.status("fp-p1-password-fallback-note", fixture), FAIL
        )

    def test_missing_runbook_requirements_fail(self):
        for check_id, phrase in (
            (
                "fp-p1-runbook-loopback",
                "publishes the application port on loopback by default",
            ),
            (
                "fp-p1-runbook-no-redis-port",
                "does not publish unauthenticated Redis to the host",
            ),
            (
                "fp-p1-runbook-postgres-loopback",
                "publishes Postgres on loopback only for local development tools",
            ),
        ):
            with self.subTest(check=check_id):
                self.assertIn(phrase, self.runbook)
                self.assertEqual(
                    self.status(check_id, self.runbook.replace(phrase, "")), FAIL
                )


class AgentCredentialGuidanceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        groups = yaml.safe_load(Path(CHECKS_FILE).read_text(encoding="utf-8"))
        group = next(group for group in groups if group["eval"] == "docker-agent-config"
                     and group["prompt"].startswith("Prompt 4:"))
        cls.checks = {check["id"]: check for check in group["checks"]}
        cls.content = Path(REPO_ROOT, group["asset"]).read_text(encoding="utf-8")

    def status(self, check_id, content):
        return run_check(self.checks[check_id], content, None, "SKILL.md")["status"]

    def test_checked_in_guidance_passes(self):
        for check_id in self.checks:
            with self.subTest(check=check_id):
                self.assertEqual(self.status(check_id, self.content), PASS)

    def test_original_interpolation_advice_is_rejected(self):
        original = (
            "Do not put real credentials, tokens, or customer data directly in\n"
            "`instruction` or `commands` — use `${env.VAR}` interpolation instead, and\n"
            "keep the underlying secret in an env file, not the YAML."
        )
        self.assertEqual(self.status("ac-p4-no-unsafe-advice", original), FAIL)
        self.assertEqual(self.status("ac-p4-no-unsafe-advice", self.content + original), FAIL)

    def test_missing_safeguards_fail(self):
        for check_id, text in (
            ("ac-p4-prompt-disclosure", "expands values into prompt text sent to the model"),
            ("ac-p4-nonsensitive-context", "only for non-sensitive context"),
            ("ac-p4-authentication", "names the environment variable, not its value"),
            ("ac-p4-redaction-limits", "defense in depth, not a"),
        ):
            with self.subTest(check=check_id):
                self.assertIn(text, self.content)
                self.assertEqual(self.status(check_id, self.content.replace(text, "")), FAIL)

    def test_harmless_interpolation_is_not_prohibited(self):
        content = "Use `${env.PROJECT_NAME}` for non-sensitive project context."
        self.assertEqual(self.status("ac-p4-no-unsafe-advice", content), PASS)


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

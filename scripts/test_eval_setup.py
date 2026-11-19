"""Unit tests for eval_setup.py."""

import json
import pathlib
import re
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, str(pathlib.Path(__file__).parent))
import eval_setup

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent


def init_event(skills=None, plugins=None, servers=None):
    if skills is None:
        skills = [f"docker-skills:{s}" for s in sorted(eval_setup.expected_skills())]
    if plugins is None:
        plugins = [{"name": "docker-skills", "path": "/repo"}, {"name": "builtin-x", "path": "builtin"}]
    if servers is None:
        servers = [{"name": "plugin:docker-skills:docker-docs", "status": "connected"}]
    return {"type": "system", "subtype": "init", "skills": skills + ["update-config"],
            "plugins": plugins, "mcp_servers": servers}


class VersionTests(unittest.TestCase):
    def test_pins_are_exact_versions(self):
        versions = json.loads(eval_setup.CLI_VERSIONS_FILE.read_text())
        for agent, version in versions.items():
            self.assertRegex(version, r"^\d+\.\d+\.\d+$", agent)

    def test_marketplace_validation_uses_the_same_claude_pin(self):
        ci = (REPO_ROOT / ".github" / "workflows" / "ci.yml").read_text()
        pins = set(re.findall(r'CLAUDE_CODE_VERSION: "([^"]+)"', ci))
        self.assertEqual(pins, {eval_setup.pinned_version("claude")})

    def test_parse_version(self):
        self.assertEqual(eval_setup.parse_version("2.1.316 (Claude Code)\n"), (2, 1, 316))
        self.assertEqual(eval_setup.parse_version("codex-cli 0.166.0"), (0, 166, 0))
        with self.assertRaises(eval_setup.SetupError):
            eval_setup.parse_version("unknown")

    def test_resolve_version(self):
        self.assertEqual(eval_setup.resolve_version("claude", "pinned"), eval_setup.pinned_version("claude"))
        self.assertEqual(eval_setup.resolve_version("claude", "2.2.0"), "2.2.0")
        with mock.patch.object(eval_setup, "_run", return_value="2.9.1\n") as run:
            self.assertEqual(eval_setup.resolve_version("claude", "latest"), "2.9.1")
        run.assert_called_once_with(["npm", "view", "@anthropic-ai/claude-code", "version"])
        with self.assertRaises(eval_setup.SetupError):
            eval_setup.resolve_version("claude", "2.1")

    def test_min_version_compares_numerically(self):
        pinned = eval_setup.pinned_version("claude")
        major, minor, patch = eval_setup.parse_version(pinned)
        with mock.patch.object(eval_setup, "cli_version", return_value=f"{major}.{minor}.{patch + 10}"):
            eval_setup.check_min_version("claude", "claude")
        with mock.patch.object(eval_setup, "cli_version", return_value=f"{major}.{minor}.{max(patch - 1, 0)}"):
            if patch > 0:
                with self.assertRaises(eval_setup.SetupError):
                    eval_setup.check_min_version("claude", "claude")


class EnsureCliTests(unittest.TestCase):
    def test_reuses_an_installed_version(self):
        with tempfile.TemporaryDirectory() as tools:
            binary = pathlib.Path(tools) / "claude-1.2.3" / "node_modules" / ".bin" / "claude"
            binary.parent.mkdir(parents=True)
            binary.touch()
            with mock.patch.object(eval_setup, "_run") as run:
                self.assertEqual(eval_setup.ensure_cli("claude", "1.2.3", pathlib.Path(tools)), binary)
            run.assert_not_called()

    def test_installs_with_ignore_scripts_then_fetches_the_binary(self):
        with tempfile.TemporaryDirectory() as tools:
            prefix = pathlib.Path(tools) / "claude-1.2.3"

            def fake_run(cmd, env=None, timeout=0):
                if cmd[0] == "node":
                    binary = prefix / "node_modules" / ".bin" / "claude"
                    binary.parent.mkdir(parents=True)
                    binary.touch()
                return ""

            with mock.patch.object(eval_setup, "_run", side_effect=fake_run) as run:
                eval_setup.ensure_cli("claude", "1.2.3", pathlib.Path(tools))
            npm, node = (c.args[0] for c in run.call_args_list)
            self.assertEqual(npm[:4], ["npm", "install", "--prefix", str(prefix)])
            self.assertIn("--ignore-scripts", npm)
            self.assertEqual(npm[-1], "@anthropic-ai/claude-code@1.2.3")
            self.assertTrue(node[1].endswith("@anthropic-ai/claude-code/install.cjs"))


class ClaudeInitTests(unittest.TestCase):
    def test_expected_skills_match_the_checkout(self):
        skills = eval_setup.expected_skills()
        self.assertIn("docker-docs", skills)
        self.assertEqual(skills, {p.parent.name for p in (REPO_ROOT / "skills").glob("*/SKILL.md")})

    def test_complete_install_passes(self):
        self.assertEqual(eval_setup.check_claude_init(init_event(), eval_setup.expected_skills()), [])

    def test_missing_skill_fails(self):
        skills = [f"docker-skills:{s}" for s in sorted(eval_setup.expected_skills()) if s != "docker-docs"]
        errors = eval_setup.check_claude_init(init_event(skills=skills), eval_setup.expected_skills())
        self.assertTrue(any("docker-docs" in e for e in errors), errors)

    def test_other_user_plugins_fail(self):
        plugins = [{"name": "docker-skills", "path": "/repo"}, {"name": "someones-plugin", "path": "/p"}]
        errors = eval_setup.check_claude_init(init_event(plugins=plugins), eval_setup.expected_skills())
        self.assertTrue(any("someones-plugin" in e for e in errors), errors)

    def test_missing_mcp_server_fails(self):
        errors = eval_setup.check_claude_init(init_event(servers=[]), eval_setup.expected_skills())
        self.assertTrue(any("MCP server" in e for e in errors), errors)

    def test_session_init_never_sends_the_real_credentials(self):
        script = ("import json,os,sys;"
                  "print(json.dumps({'type':'system','subtype':'init',"
                  "'key':os.environ.get('ANTHROPIC_API_KEY'),'oauth':os.environ.get('CLAUDE_CODE_OAUTH_TOKEN'),"
                  "'cfg':os.environ.get('CLAUDE_CONFIG_DIR')}),flush=True)")
        with tempfile.TemporaryDirectory() as d:
            fake = pathlib.Path(d) / "claude"
            fake.write_text(f"#!{sys.executable}\n{script}\n")
            fake.chmod(0o755)
            with mock.patch.dict(eval_setup.os.environ, {"ANTHROPIC_API_KEY": "real", "CLAUDE_CODE_OAUTH_TOKEN": "t"}):
                event = eval_setup.claude_session_init(fake, {"CLAUDE_CONFIG_DIR": "/cfg"}, pathlib.Path(d))
        self.assertNotEqual(event["key"], "real")
        self.assertIsNone(event["oauth"])
        self.assertEqual(event["cfg"], "/cfg")

    def test_setup_raises_on_bad_install(self):
        with mock.patch.object(eval_setup, "install_claude_plugin", return_value={"CLAUDE_CONFIG_DIR": "/c"}), \
             mock.patch.object(eval_setup, "claude_session_init", return_value=init_event(servers=[])):
            with self.assertRaises(eval_setup.SetupError):
                eval_setup.setup_claude_plugin("claude", pathlib.Path("/c"), pathlib.Path("/w"))

    def test_install_isolates_config_dir_and_installs_from_checkout(self):
        with tempfile.TemporaryDirectory() as d, mock.patch.object(eval_setup, "_run") as run:
            overrides = eval_setup.install_claude_plugin("claude", pathlib.Path(d) / "cfg", pathlib.Path("/repo"))
        self.assertEqual(overrides, {"CLAUDE_CONFIG_DIR": str(pathlib.Path(d) / "cfg")})
        add, install = (c.args[0] for c in run.call_args_list)
        self.assertEqual(add, ["claude", "plugin", "marketplace", "add", "/repo"])
        self.assertEqual(install, ["claude", "plugin", "install", "docker-skills@docker"])
        for call in run.call_args_list:
            self.assertEqual(call.kwargs["env"]["CLAUDE_CONFIG_DIR"], str(pathlib.Path(d) / "cfg"))


if __name__ == "__main__":
    unittest.main()

import argparse
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, os.path.dirname(__file__))

import skill_eval  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parent.parent
SCENARIO = REPO_ROOT / "skills" / "docker-sandboxes-lifecycle" / "evals" / "mount-ls-delete.yaml"


def transcript_lines(skill: str | None, final: str, subtype: str = "success") -> list[str]:
    events = [{"type": "system", "subtype": "init", "skills": ["docker-sandboxes-lifecycle", "docker-docs"]}]
    if skill:
        events += [
            {"type": "assistant", "message": {"content": [
                {"type": "tool_use", "id": "t1", "name": "Skill", "input": {"skill": skill}}]}},
            {"type": "user", "message": {"content": [
                {"type": "tool_result", "tool_use_id": "t1", "content": f"Launching skill: {skill}"}]}},
        ]
    events += [
        {"type": "assistant", "message": {"content": [{"type": "text", "text": final}]}},
        {"type": "result", "subtype": subtype, "is_error": subtype != "success", "result": final, "num_turns": 3},
    ]
    return [json.dumps(e) for e in events]


def make_cli_config() -> skill_eval.CLIConfig:
    """Create the CLI config used by the docker-sandboxes scenario."""
    return skill_eval.CLIConfig(
        command="sbx",
        subcommand_index=1,
        name_flags=["--name"],
        name_positional_commands=["exec", "stop", "rm", "cp", "ports"],
    )


def make_calls(*specs: tuple) -> list[dict]:
    """Create call records from (subcommand, *args) tuples."""
    cli = make_cli_config()
    calls = []
    for spec in specs:
        argv = ["sbx"] + list(spec)
        call = skill_eval.enrich_call({"argv": argv, "command": " ".join(argv)}, cli)
        calls.append(call)
    return calls


class TranscriptParsingTests(unittest.TestCase):
    def test_parse_skill_invocation(self):
        transcript = skill_eval.parse_transcript(transcript_lines("docker-sandboxes-lifecycle", "done"))
        self.assertEqual(transcript.invoked_skills(), ["docker-sandboxes-lifecycle"])
        self.assertEqual(transcript.final_text, "done")
        self.assertEqual(transcript.result.get("subtype"), "success")

    def test_parse_no_skill(self):
        transcript = skill_eval.parse_transcript(transcript_lines(None, "done"))
        self.assertEqual(transcript.invoked_skills(), [])

    def test_extract_cli_calls_from_bash(self):
        events = [
            {"type": "system", "subtype": "init", "skills": []},
            {"type": "assistant", "message": {"content": [
                {"type": "tool_use", "id": "t1", "name": "Bash",
                 "input": {"command": "sbx run shell --name mybox -d ./notes 2>&1"}}
            ]}},
            {"type": "assistant", "message": {"content": [
                {"type": "tool_use", "id": "t2", "name": "Bash",
                 "input": {"command": "sbx exec mybox ls /workspace/notes"}}
            ]}},
            {"type": "assistant", "message": {"content": [
                {"type": "tool_use", "id": "t3", "name": "Bash",
                 "input": {"command": "sbx rm --force mybox 2>&1"}}
            ]}},
            {"type": "result", "subtype": "success", "result": "done"},
        ]
        transcript = skill_eval.parse_transcript([json.dumps(e) for e in events])
        cli = make_cli_config()
        calls = transcript.cli_calls(cli)
        self.assertEqual(len(calls), 3)
        self.assertEqual(calls[0]["subcommand"], "run")
        self.assertEqual(calls[0]["name"], "mybox")
        self.assertEqual(calls[1]["subcommand"], "exec")
        self.assertEqual(calls[2]["subcommand"], "rm")

    def test_parse_codex_transcript(self):
        """Test parsing Codex JSON events."""
        events = [
            {"type": "thread.started", "thread_id": "test-123"},
            {"type": "turn.started"},
            {"type": "item.completed", "item": {
                "id": "item_0", "type": "agent_message",
                "text": "I'll use the skill to help."}},
            {"type": "item.completed", "item": {
                "id": "item_1", "type": "command_execution",
                "command": "/bin/zsh -lc 'cat .agents/skills/docker-sandboxes-lifecycle/SKILL.md'",
                "aggregated_output": "# Test skill content", "exit_code": 0, "status": "completed"}},
            {"type": "item.completed", "item": {
                "id": "item_2", "type": "command_execution",
                "command": "/bin/zsh -lc 'sbx create --name mybox shell /workspace'",
                "aggregated_output": "Created sandbox mybox", "exit_code": 0, "status": "completed"}},
            {"type": "item.completed", "item": {
                "id": "item_3", "type": "agent_message",
                "text": "Done! Created the sandbox."}},
            {"type": "turn.completed", "usage": {"input_tokens": 1000, "output_tokens": 100}},
        ]
        transcript = skill_eval.parse_transcript([json.dumps(e) for e in events], agent="codex")
        self.assertEqual(transcript.agent, "codex")
        self.assertEqual(transcript.result.get("subtype"), "success")
        # final_text now includes all agent messages
        self.assertIn("Done! Created the sandbox.", transcript.final_text)
        self.assertIn("I'll use the skill to help.", transcript.final_text)
        self.assertIn("docker-sandboxes-lifecycle", transcript.skills_available)
        self.assertEqual(transcript.invoked_skills(), ["docker-sandboxes-lifecycle"])
        cli = make_cli_config()
        calls = transcript.cli_calls(cli)
        self.assertEqual(len(calls), 1)  # Only one sbx command
        self.assertEqual(calls[0]["subcommand"], "create")


class CallEnrichmentTests(unittest.TestCase):
    def test_enrich_create_with_name(self):
        cli = make_cli_config()
        call = skill_eval.enrich_call({"argv": ["sbx", "create", "--name", "mybox", "shell", "/path/to/workspace"]}, cli)
        self.assertEqual(call["subcommand"], "create")
        self.assertEqual(call["name"], "mybox")
        self.assertIn("/path/to/workspace", call["positionals"])

    def test_enrich_run_with_name(self):
        cli = make_cli_config()
        call = skill_eval.enrich_call({"argv": ["sbx", "run", "shell", "--name", "mybox", "-d", "/workspace/notes"]}, cli)
        self.assertEqual(call["subcommand"], "run")
        self.assertEqual(call["name"], "mybox")

    def test_enrich_exec(self):
        cli = make_cli_config()
        call = skill_eval.enrich_call({"argv": ["sbx", "exec", "mybox", "ls", "-la", "/workspace/notes"]}, cli)
        self.assertEqual(call["subcommand"], "exec")
        self.assertEqual(call["name"], "mybox")
        self.assertEqual(call["positionals"], ["mybox", "ls", "-la", "/workspace/notes"])

    def test_enrich_rm(self):
        cli = make_cli_config()
        call = skill_eval.enrich_call({"argv": ["sbx", "rm", "--force", "mybox"]}, cli)
        self.assertEqual(call["subcommand"], "rm")
        self.assertEqual(call["name"], "mybox")


class GradingTests(unittest.TestCase):
    def setUp(self):
        self.scenario = skill_eval.load_scenario(SCENARIO)
        self.workspace = "/workspace"

    def grade(self, calls, skill="docker-sandboxes-lifecycle", final="Found hello.txt and todo.md and hello from the host",
              subtype="success"):
        transcript = skill_eval.parse_transcript(transcript_lines(skill, final, subtype))
        return skill_eval.grade(self.scenario, transcript, calls, self.workspace)

    def failed(self, checks):
        return [c.name for c in checks if not c.passed]

    def happy_path_calls(self):
        return make_calls(
            ("run", "shell", "--name", "notes-box", "-d", "/workspace/notes"),
            ("ls", "--json"),
            ("exec", "notes-box", "ls", "/workspace/notes"),
            ("exec", "notes-box", "cat", "/workspace/notes/hello.txt"),
            ("rm", "--force", "notes-box"),
            ("ls", "--json"),
        )

    def test_scenario_passes_on_expected_behaviour(self):
        calls = self.happy_path_calls()
        self.assertEqual(self.failed(self.grade(calls)), [])

    def test_missing_skill_invocation_fails(self):
        calls = self.happy_path_calls()
        self.assertEqual(self.failed(self.grade(calls, skill=None)), ["skill docker-sandboxes-lifecycle invoked"])

    def test_create_without_workspace_fails_step(self):
        calls = make_calls(
            ("create", "--name", "mybox", "shell"),  # no workspace path
            ("ls",),
            ("exec", "mybox", "ls"),
            ("exec", "mybox", "cat", "hello.txt"),
            ("rm", "--force", "mybox"),
            ("ls"),
        )
        failed = self.failed(self.grade(calls))
        self.assertIn("step 1: creates a sandbox with ./notes as workspace", failed)

    def test_exec_on_another_sandbox_fails(self):
        calls = make_calls(
            ("create", "--name", "notes-box", "shell", "/workspace/notes"),
            ("ls",),
            ("exec", "other-box", "ls", "/workspace/notes"),  # wrong sandbox
            ("exec", "notes-box", "cat", "hello.txt"),
            ("rm", "--force", "notes-box"),
            ("ls"),
        )
        failed = self.failed(self.grade(calls))
        self.assertIn("step 3: lists the mounted directory from inside the sandbox", failed)

    def test_missing_rm_fails(self):
        calls = make_calls(
            ("run", "shell", "--name", "notes-box", "-d", "/workspace/notes"),
            ("ls",),
            ("exec", "notes-box", "ls", "/workspace/notes"),
            ("exec", "notes-box", "cat", "hello.txt"),
            ("ls"),  # no rm
        )
        failed = self.failed(self.grade(calls))
        self.assertIn("step 5: removes the sandbox", failed)

    def test_forbidden_bulk_removal_fails(self):
        calls = make_calls(
            ("run", "shell", "--name", "notes-box", "-d", "/workspace/notes"),
            ("ls",),
            ("exec", "notes-box", "ls", "/workspace/notes"),
            ("exec", "notes-box", "cat", "hello.txt"),
            ("rm", "--all", "--force"),  # forbidden
            ("ls"),
        )
        failed = self.failed(self.grade(calls))
        self.assertIn("forbidden: no bulk removal of every sandbox", failed)

    def test_unfinished_agent_fails(self):
        calls = self.happy_path_calls()
        failed = self.failed(self.grade(calls, final="done", subtype="error_max_turns"))
        self.assertIn("agent finished successfully", failed)

    def test_wrong_answer_fails(self):
        calls = self.happy_path_calls()
        failed = self.failed(self.grade(calls, final="I ran the commands"))
        self.assertIn("answer mentions 'hello.txt'", failed)


class HarnessTests(unittest.TestCase):
    def test_every_scenario_loads(self):
        scenarios = skill_eval.discover([], None)
        self.assertTrue(scenarios)
        for scenario in scenarios:
            self.assertTrue(scenario.expect.get("steps"), scenario.path)

    def test_invalid_scenarios_are_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            # Create a fake skill structure
            skill_dir = Path(tmp) / "skills" / "docker-sandboxes-lifecycle"
            evals_dir = skill_dir / "evals"
            evals_dir.mkdir(parents=True)
            (skill_dir / "SKILL.md").write_text("# Test")
            bad = evals_dir / "bad.yaml"
            base = "id: x\nskill: docker-sandboxes-lifecycle\nprompt: hi\n"
            
            # Temporarily patch SKILLS_ROOT
            original_skills_root = skill_eval.SKILLS_ROOT
            skill_eval.SKILLS_ROOT = Path(tmp) / "skills"
            try:
                for body in ("id: x\n", base + "expect:\n  steps:\n    - typo: 1\n",
                             base + "fixtures:\n  ../escape: x\nexpect:\n  steps: []\n"):
                    bad.write_text(body)
                    with self.assertRaises(skill_eval.ScenarioError, msg=body):
                        skill_eval.load_scenario(bad)
            finally:
                skill_eval.SKILLS_ROOT = original_skills_root

    def test_workspace_preparation(self):
        scenario = skill_eval.load_scenario(SCENARIO)
        with tempfile.TemporaryDirectory() as tmp:
            # Test Claude workspace
            paths = skill_eval.prepare_workspace(scenario, Path(tmp), only_target_skill=True, agent="claude")
            try:
                skills = sorted(p.name for p in (paths["workspace"] / ".claude" / "skills").iterdir())
                self.assertEqual(skills, ["docker-sandboxes-lifecycle"])
                self.assertTrue((paths["workspace"] / "notes" / "hello.txt").is_file())
            finally:
                import shutil
                shutil.rmtree(paths["root"], ignore_errors=True)

    def test_workspace_preparation_codex(self):
        scenario = skill_eval.load_scenario(SCENARIO)
        with tempfile.TemporaryDirectory() as tmp:
            # Test Codex workspace
            paths = skill_eval.prepare_workspace(scenario, Path(tmp), only_target_skill=True, agent="codex")
            try:
                skills = sorted(p.name for p in (paths["workspace"] / ".agents" / "skills").iterdir())
                self.assertEqual(skills, ["docker-sandboxes-lifecycle"])
                self.assertTrue((paths["workspace"] / "notes" / "hello.txt").is_file())
            finally:
                import shutil
                shutil.rmtree(paths["root"], ignore_errors=True)

    def test_agent_command_structure_claude(self):
        scenario = skill_eval.load_scenario(SCENARIO)
        args = argparse.Namespace(agent_bin="claude", agent="claude", model="sonnet")
        # Test with API key (isolated)
        command = skill_eval.agent_command(scenario, args, use_host_config=False)
        self.assertIn("stream-json", command)
        self.assertIn("Bash", command)  # Scenario allows all Bash commands
        self.assertIn("--setting-sources", command)
        self.assertEqual(command[command.index("--setting-sources") + 1], "project")
        self.assertEqual(command[command.index("--permission-mode") + 1], "dontAsk")
        # Test with host config (subscription login) - no --setting-sources
        command_host = skill_eval.agent_command(scenario, args, use_host_config=True)
        self.assertNotIn("--setting-sources", command_host)

    def test_agent_command_structure_codex(self):
        scenario = skill_eval.load_scenario(SCENARIO)
        args = argparse.Namespace(agent_bin="codex", agent="codex", model=None)
        command = skill_eval.agent_command(scenario, args, use_host_config=False)
        self.assertIn("exec", command)
        self.assertIn("--json", command)
        self.assertIn("--dangerously-bypass-approvals-and-sandbox", command)
        self.assertIn("--ephemeral", command)

    def test_pass_rate_threshold(self):
        ok = [skill_eval.Check("c", True)]
        bad = [skill_eval.Check("c", False)]
        results = [("s/a #1", Path("."), ok), ("s/a #2", Path("."), bad), ("s/a #3", Path("."), ok)]
        with open(os.devnull, "w") as devnull:
            stdout, sys.stdout = sys.stdout, devnull
            try:
                self.assertEqual(skill_eval.summarize(results, 0.6, Path("."), "claude"), 0)
                self.assertEqual(skill_eval.summarize(results, 1.0, Path("."), "claude"), 1)
            finally:
                sys.stdout = stdout


if __name__ == "__main__":
    unittest.main()

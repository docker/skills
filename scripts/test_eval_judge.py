"""Unit tests for eval_judge.py."""

import sys
import unittest
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import eval_judge


SAMPLE_EVAL_MD = """\
# Eval: docker-sandboxes-lifecycle

Test skill description.

---

## Prompt 1: simple question

**Prompt to agent:**

> What is the difference between create and run?

### Expected behaviors
- [ ] Explains the difference clearly.
- [ ] Recommends the correct command.

### Must not
- [ ] Must NOT give incorrect information.

### Verification commands
```bash
echo "test"
```

---

## Prompt 2: multi-line criteria

**Prompt to agent:**

> How do I clean up sandboxes?

### Expected behaviors
- [ ] Recommends `sbx prune` with `--filter until=DURATION` (current
      pinned-source flag; e.g. `until=168h`) and `--dry-run` first.
- [ ] States that `sbx prune` never removes a running sandbox.

### Must not
- [ ] Must NOT recommend `sbx rm --all` as the routine cleanup.
- [ ] Must NOT describe `sbx prune` as "safe to run habitually"
      without qualification.

### Verification commands
```bash
sbx prune --dry-run
```
"""


class ParseEvalMarkdownTests(unittest.TestCase):
    def setUp(self):
        self.tmpfile = tempfile.NamedTemporaryFile(mode='w', suffix='.md', delete=False)
        self.tmpfile.write(SAMPLE_EVAL_MD)
        self.tmpfile.flush()
        self.path = Path(self.tmpfile.name)

    def tearDown(self):
        self.tmpfile.close()
        self.path.unlink(missing_ok=True)

    def test_parses_skill_name(self):
        prompts = eval_judge.parse_eval_markdown(self.path)
        self.assertTrue(all(p.skill == "docker-sandboxes-lifecycle" for p in prompts))

    def test_parses_two_prompts(self):
        prompts = eval_judge.parse_eval_markdown(self.path)
        self.assertEqual(len(prompts), 2)

    def test_parses_prompt_text(self):
        prompts = eval_judge.parse_eval_markdown(self.path)
        self.assertEqual(prompts[0].prompt, "What is the difference between create and run?")
        self.assertEqual(prompts[1].prompt, "How do I clean up sandboxes?")

    def test_parses_expected_behaviors(self):
        prompts = eval_judge.parse_eval_markdown(self.path)
        self.assertEqual(len(prompts[0].expected_behaviors), 2)
        self.assertEqual(len(prompts[1].expected_behaviors), 2)

    def test_parses_must_not(self):
        prompts = eval_judge.parse_eval_markdown(self.path)
        self.assertEqual(len(prompts[0].must_not), 1)
        self.assertEqual(len(prompts[1].must_not), 2)

    def test_handles_multiline_criteria(self):
        prompts = eval_judge.parse_eval_markdown(self.path)
        # Check multi-line criterion is joined
        self.assertIn("until=168h", prompts[1].expected_behaviors[0])
        self.assertIn("dry-run", prompts[1].expected_behaviors[0])


class ParsePromptTextTests(unittest.TestCase):
    def _parse(self, body):
        md = "# Eval: s\n\n## Prompt 1: t\n\n**Prompt to agent:**\n\n" + body + \
             "\n### Expected behaviors\n- [ ] x\n"
        with tempfile.NamedTemporaryFile("w", suffix=".md", delete=False) as f:
            f.write(md)
        return eval_judge.parse_eval_markdown(Path(f.name))[0].prompt

    def test_includes_quote_after_blank_line(self):
        prompt = self._parse("> Do the thing.\n\n> (AUTOMATED EVAL: no questions.)\n")
        self.assertEqual(prompt, "Do the thing.\n\n(AUTOMATED EVAL: no questions.)")

    def test_includes_quote_after_empty_quote_line(self):
        prompt = self._parse("> Do the thing.\n>\n> (AUTOMATED EVAL: no questions.)\n")
        self.assertIn("AUTOMATED EVAL", prompt)

    def test_preserves_code_indentation(self):
        prompt = self._parse("> Fix this:\n>\n> ```yaml\n> services:\n>   web:\n>     image: x\n> ```\n")
        self.assertIn("services:\n  web:\n    image: x", prompt)

    def test_stops_before_next_section(self):
        prompt = self._parse("> Do the thing.\n")
        self.assertNotIn("Expected", prompt)


class SkipInCiTests(unittest.TestCase):
    MD = ("# Eval: s\n\n## Prompt 1: real server\n\n**Prompt to agent:**\n\n> Add notion.\n\n"
          "**Skip in CI:** needs a real MCP server\n\n### Expected behaviors\n- [ ] x\n\n"
          "## Prompt 2: qa\n\n**Prompt to agent:**\n\n> Why?\n\n### Expected behaviors\n- [ ] y\n")

    def _write(self):
        f = tempfile.NamedTemporaryFile("w", suffix=".md", delete=False)
        f.write(self.MD)
        f.close()
        return Path(f.name)

    def test_parses_skip_reason(self):
        prompts = eval_judge.parse_eval_markdown(self._write())
        self.assertEqual(prompts[0].skip_reason, "needs a real MCP server")
        self.assertIsNone(prompts[1].skip_reason)
        self.assertNotIn("Skip in CI", prompts[0].prompt)

    def _run_main(self, extra):
        from unittest import mock
        prompts = eval_judge.parse_eval_markdown(self._write())
        ran = []
        def fake_run(ep, args, run_dir):
            ran.append(ep.prompt_num)
            return [eval_judge.JudgeResult("y", True, "")]
        with mock.patch.object(eval_judge, "discover_evals", return_value=prompts), \
             mock.patch.object(eval_judge, "run_and_grade", side_effect=fake_run), \
             mock.patch.object(eval_judge.shutil, "which", return_value="/usr/bin/claude"), \
             mock.patch.dict(eval_judge.os.environ, {"ANTHROPIC_API_KEY": "k"}), \
             tempfile.TemporaryDirectory() as out:
            rc = eval_judge.main(["--out", out] + extra)
        return rc, ran

    def test_skipped_by_default(self):
        rc, ran = self._run_main([])
        self.assertEqual(ran, [2])
        self.assertEqual(rc, 0)

    def test_include_skipped_runs_all(self):
        rc, ran = self._run_main(["--include-skipped"])
        self.assertEqual(ran, [1, 2])
        self.assertEqual(rc, 0)


class DiscoverEvalsTests(unittest.TestCase):
    def test_discovers_real_evals(self):
        # Should find evals in skills/ and evals/ directories
        prompts = eval_judge.discover_evals(None, None)
        self.assertTrue(len(prompts) > 0)

    def test_filters_by_skill_name(self):
        prompts = eval_judge.discover_evals("docker-sandboxes-lifecycle", None)
        self.assertTrue(all(p.skill == "docker-sandboxes-lifecycle" for p in prompts))

    def test_filters_by_prompt_num(self):
        prompts = eval_judge.discover_evals("docker-sandboxes-lifecycle", 1)
        self.assertTrue(all(p.prompt_num == 1 for p in prompts))
    
    def test_prefers_skills_dir_over_evals_dir(self):
        # If <skill>.md exists in skills/<skill>/evals/, it should be used over evals/<skill>.md
        # We can test this by checking that docker-sandboxes-lifecycle is found
        # (it exists in both places now)
        prompts = eval_judge.discover_evals("docker-sandboxes-lifecycle", None)
        self.assertTrue(len(prompts) > 0)
        # All prompts should come from the same file
        eval_files = set(p.eval_file for p in prompts)
        self.assertEqual(len(eval_files), 1)
        # Should be from the skills directory
        self.assertIn("skills/docker-sandboxes-lifecycle/evals", str(list(eval_files)[0]))


class TranscriptToTextTests(unittest.TestCase):
    def test_converts_assistant_text(self):
        with tempfile.NamedTemporaryFile(mode='w', suffix='.jsonl', delete=False) as f:
            f.write('{"type":"assistant","message":{"content":[{"type":"text","text":"Hello"}]}}\n')
            f.flush()
            text = eval_judge.transcript_to_text(Path(f.name))
        self.assertIn("ASSISTANT: Hello", text)

    def test_converts_tool_calls(self):
        with tempfile.NamedTemporaryFile(mode='w', suffix='.jsonl', delete=False) as f:
            f.write('{"type":"assistant","message":{"content":[{"type":"tool_use","name":"Bash","input":{"command":"ls"}}]}}\n')
            f.flush()
            text = eval_judge.transcript_to_text(Path(f.name))
        self.assertIn("TOOL CALL [Bash]", text)
        self.assertIn("ls", text)


class CodexTranscriptToTextTests(unittest.TestCase):
    def test_converts_agent_message(self):
        with tempfile.NamedTemporaryFile(mode='w', suffix='.jsonl', delete=False) as f:
            f.write('{"type":"item.completed","item":{"type":"agent_message","text":"Hello from Codex"}}\n')
            f.flush()
            text = eval_judge.codex_transcript_to_text(Path(f.name))
        self.assertIn("ASSISTANT: Hello from Codex", text)

    def test_converts_command_execution(self):
        with tempfile.NamedTemporaryFile(mode='w', suffix='.jsonl', delete=False) as f:
            f.write('{"type":"item.completed","item":{"type":"command_execution","command":"/bin/zsh -lc \'ls -la\'","aggregated_output":"file1 file2"}}\n')
            f.flush()
            text = eval_judge.codex_transcript_to_text(Path(f.name))
        self.assertIn("TOOL CALL [Bash]", text)
        self.assertIn("ls -la", text)
        self.assertIn("TOOL RESULT: file1 file2", text)

    def test_converts_skill_read(self):
        with tempfile.NamedTemporaryFile(mode='w', suffix='.jsonl', delete=False) as f:
            f.write('{"type":"item.completed","item":{"type":"skill_read","skill_path":"/path/to/.agents/skills/docker-sandboxes-lifecycle/SKILL.md"}}\n')
            f.flush()
            text = eval_judge.codex_transcript_to_text(Path(f.name))
        self.assertIn("TOOL CALL [Skill]", text)
        self.assertIn("docker-sandboxes-lifecycle", text)


class JudgeVerdictMappingTests(unittest.TestCase):
    """must_not items use a direct 'violated' verdict to avoid double negation."""

    EXPECTED_OK = {"criterion_number": 1, "criterion_type": "expected", "passed": True}

    def _judge(self, evaluations):
        from unittest import mock
        with mock.patch.object(eval_judge, "call_judge", return_value={"evaluations": evaluations}):
            return eval_judge.judge_transcript("t", ["do A"], ["Must NOT do B"], "m")

    def _must_not(self, results):
        return [r for r in results if r.is_must_not][0]

    def test_must_not_not_violated_passes(self):
        results = self._judge([
            self.EXPECTED_OK,
            {"criterion_number": 1, "criterion_type": "must_not", "violated": False},
        ])
        self.assertTrue(all(r.passed for r in results))

    def test_must_not_violated_fails(self):
        results = self._judge([
            self.EXPECTED_OK,
            {"criterion_number": 1, "criterion_type": "must_not", "violated": True},
        ])
        self.assertFalse(self._must_not(results).passed)

    def test_violated_takes_precedence_over_passed(self):
        results = self._judge([
            self.EXPECTED_OK,
            {"criterion_number": 1, "criterion_type": "must_not", "violated": False, "passed": False},
        ])
        self.assertTrue(self._must_not(results).passed)

    def test_must_not_falls_back_to_passed(self):
        results = self._judge([
            self.EXPECTED_OK,
            {"criterion_number": 1, "criterion_type": "must_not", "passed": True},
        ])
        self.assertTrue(self._must_not(results).passed)


class AgentCompletionTests(unittest.TestCase):
    """A run the agent did not finish never passes."""

    def _check(self, agent, events, exit_code=0, timed_out=False):
        import json
        d = Path(tempfile.mkdtemp())
        self.addCleanup(eval_judge.shutil.rmtree, d, True)
        path = d / "transcript.jsonl"
        path.write_text("".join(json.dumps(e) + "\n" for e in events) + "not json\n")
        result = eval_judge.AgentRunResult("", {}, d, exit_code=None if timed_out else exit_code,
                                           timed_out=timed_out)
        return eval_judge.agent_completion_error(result, path, agent)

    def test_claude_success(self):
        self.assertIsNone(self._check("claude", [{"type": "system", "subtype": "init"},
                                                 {"type": "result", "subtype": "success"}]))

    def test_claude_error_result(self):
        err = self._check("claude", [{"type": "result", "subtype": "success", "is_error": True}])
        self.assertIn("error", err)

    def test_claude_max_turns(self):
        self.assertIn("error_max_turns", self._check("claude", [{"type": "result", "subtype": "error_max_turns"}]))

    def test_claude_crashed_after_init(self):
        self.assertIn("no result event", self._check("claude", [{"type": "system", "subtype": "init"}]))

    def test_codex_success(self):
        self.assertIsNone(self._check("codex", [{"type": "turn.started"}, {"type": "turn.completed"}]))

    def test_codex_never_completed(self):
        self.assertIn("turn.completed", self._check("codex", [{"type": "turn.started"}]))

    def test_codex_turn_failed(self):
        err = self._check("codex", [{"type": "turn.failed"}, {"type": "turn.completed"}])
        self.assertIn("failed", err)

    def test_timeout(self):
        err = self._check("claude", [{"type": "result", "subtype": "success"}], timed_out=True)
        self.assertIn("timed out", err)

    def test_nonzero_exit(self):
        err = self._check("codex", [{"type": "turn.completed"}], exit_code=1)
        self.assertIn("code 1", err)

    def test_failed_run_adds_failing_result(self):
        from unittest import mock
        import argparse
        d = Path(tempfile.mkdtemp())
        self.addCleanup(eval_judge.shutil.rmtree, d, True)
        (d / "run.json").write_text("{}")
        (d / "transcript.jsonl").write_text('{"type": "turn.started"}\n')
        agent = eval_judge.AgentRunResult("partial", {}, d / "ws", exit_code=None, timed_out=True)
        ok = [eval_judge.JudgeResult("do A", True, "")]
        args = argparse.Namespace(agent="codex", keep=True, judge_model="m")
        with mock.patch.object(eval_judge, "run_agent", return_value=agent), \
             mock.patch.object(eval_judge, "grade", return_value=ok):
            results = eval_judge.run_and_grade(mock.Mock(), args, d)
        self.assertFalse(all(r.passed for r in results))
        self.assertEqual(results[-1].criterion, eval_judge.AGENT_COMPLETION_CRITERION)
        import json
        report = json.loads((d / "report.json").read_text())
        self.assertTrue(report["agent_timed_out"])
        self.assertFalse(report["passed"])


class FixtureTests(unittest.TestCase):
    def _parse(self, fixtures_block):
        md = ("# Eval: s\n\n## Prompt 1: t\n\n**Prompt to agent:**\n\n> Do it.\n\n"
              + fixtures_block + "\n### Expected behaviors\n- [ ] x\n")
        f = tempfile.NamedTemporaryFile("w", suffix=".md", delete=False)
        f.write(md)
        f.close()
        return eval_judge.parse_eval_markdown(Path(f.name))[0]

    def test_parses_files_and_keeps_indentation(self):
        ep = self._parse(
            "**Fixtures:**\n\n`app/Taskfile.yaml`:\n```yaml\nversion: \"3\"\ntasks:\n  build:\n    cmds:\n      - echo hi\n```\n\n"
            "`app/README.md`:\n```markdown\n# app\n```\n")
        self.assertEqual(sorted(ep.fixtures), ["app/README.md", "app/Taskfile.yaml"])
        self.assertIn("tasks:\n  build:\n    cmds:\n      - echo hi\n", ep.fixtures["app/Taskfile.yaml"])
        self.assertEqual(ep.fixtures["app/README.md"], "# app\n")

    def test_no_fixtures_by_default(self):
        self.assertEqual(self._parse("").fixtures, {})

    def test_rejects_path_traversal(self):
        for bad in ("../evil.txt", "/etc/passwd", "a/../../b"):
            with self.assertRaises(eval_judge.EvalError, msg=bad):
                self._parse(f"**Fixtures:**\n\n`{bad}`:\n```\nx\n```\n")

    def test_rejects_empty_block(self):
        with self.assertRaises(eval_judge.EvalError):
            self._parse("**Fixtures:**\n\nnothing here\n")

    def test_written_into_workspace_without_generic_readme(self):
        ep = self._parse("**Fixtures:**\n\n`app/Taskfile.yaml`:\n```yaml\nversion: \"3\"\n```\n")
        root = eval_judge.prepare_workspace(ep, "codex")
        self.addCleanup(eval_judge.shutil.rmtree, root, True)
        ws = root / "workspace"
        self.assertEqual((ws / "app" / "Taskfile.yaml").read_text(), 'version: "3"\n')
        self.assertFalse((ws / "README.md").exists())

    def test_generic_readme_without_fixtures(self):
        root = eval_judge.prepare_workspace(self._parse(""), "claude")
        self.addCleanup(eval_judge.shutil.rmtree, root, True)
        self.assertTrue((root / "workspace" / "README.md").exists())


class RegradeTests(unittest.TestCase):
    def _run_dir(self, previous_report):
        import json
        d = Path(tempfile.mkdtemp())
        self.addCleanup(eval_judge.shutil.rmtree, d, True)
        (d / "run.json").write_text(json.dumps({
            "eval_file": "x.md", "skill": "s", "prompt_num": 1, "title": "t",
            "prompt": "p", "expected_behaviors": ["do A"], "must_not": []}))
        (d / "transcript.txt").write_text("ASSISTANT: done")
        (d / "workspace_files" / "sub").mkdir(parents=True)
        (d / "workspace_files" / "Dockerfile").write_text("FROM node:22-slim\n")
        (d / "workspace_files" / "sub" / "compose.yaml").write_text("services: {}\n")
        if previous_report is not None:
            (d / "report.json").write_text(json.dumps(previous_report))
        return d

    def _regrade(self, d):
        import argparse
        from unittest import mock
        ok = [eval_judge.JudgeResult("do A", True, "")]
        with mock.patch.object(eval_judge, "grade", return_value=ok) as g:
            results = eval_judge.regrade(d, argparse.Namespace(judge_model="m"))
        return results, g

    def test_passes_saved_workspace_files_to_judge(self):
        d = self._run_dir({"passed": True})
        _, g = self._regrade(d)
        files = g.call_args.args[3]
        self.assertEqual(files, {"Dockerfile": "FROM node:22-slim\n", "sub/compose.yaml": "services: {}\n"})

    def test_keeps_original_completion_failure(self):
        import json
        d = self._run_dir({"agent_completion_error": "agent timed out after 300s", "agent_timed_out": True})
        results, _ = self._regrade(d)
        self.assertFalse(all(r.passed for r in results))
        report = json.loads((d / "report.json").read_text())
        self.assertFalse(report["passed"])
        self.assertTrue(report["agent_timed_out"])

    def test_works_without_previous_report(self):
        results, _ = self._regrade(self._run_dir(None))
        self.assertTrue(all(r.passed for r in results))


class IncompleteJudgeVerdictTests(unittest.TestCase):
    """Every criterion must get exactly one verdict; missing ones never pass."""

    def _judge(self, replies, expected=("do A", "do B"), must_not=("Must NOT do C",)):
        from unittest import mock
        with mock.patch.object(eval_judge, "call_judge", side_effect=replies) as m:
            results = eval_judge.judge_transcript("t", list(expected), list(must_not), "m")
        return results, m.call_count

    @staticmethod
    def _ev(kind, num, **verdict):
        return {"criterion_type": kind, "criterion_number": num, **verdict}

    def test_empty_evaluations_fail_every_criterion(self):
        results, calls = self._judge([{"evaluations": []}] * 3)
        self.assertEqual(calls, eval_judge.JUDGE_ATTEMPTS)
        self.assertEqual(len(results), 3)
        self.assertFalse(any(r.passed for r in results))
        self.assertIn("No judge verdict", results[0].reasoning)

    def test_partial_reply_is_retried_then_completed(self):
        partial = {"evaluations": [self._ev("expected", 1, passed=True)]}
        full = {"evaluations": [self._ev("expected", 1, passed=True), self._ev("expected", 2, passed=True),
                                 self._ev("must_not", 1, violated=False)]}
        results, calls = self._judge([partial, full])
        self.assertEqual(calls, 2)
        self.assertTrue(all(r.passed for r in results))

    def test_still_partial_fails_only_missing_criteria(self):
        partial = {"evaluations": [self._ev("expected", 1, passed=True), self._ev("must_not", 1, violated=False)]}
        results, calls = self._judge([partial] * 3)
        self.assertEqual(calls, eval_judge.JUDGE_ATTEMPTS)
        self.assertEqual([r.passed for r in results], [True, False, True])
        self.assertEqual([r.criterion for r in results], ["do A", "do B", "Must NOT do C"])

    def test_duplicates_and_bad_entries_do_not_fill_gaps(self):
        reply = {"evaluations": [
            self._ev("expected", 1, passed=True),
            self._ev("expected", 1, passed=False),          # duplicate: first wins
            self._ev("expected", 9, passed=True),           # out of range
            self._ev("bogus", 2, passed=True),              # unknown type
            {"criterion_number": 2, "passed": True},        # no type
            self._ev("expected", 2),                        # no verdict field
            self._ev("must_not", 1, violated=False),
        ]}
        results, _ = self._judge([reply] * 3)
        self.assertEqual([r.passed for r in results], [True, False, True])

    def test_non_list_evaluations(self):
        results, _ = self._judge([{"evaluations": "oops"}] * 3)
        self.assertFalse(any(r.passed for r in results))


class PrunePassingTests(unittest.TestCase):
    PASSING = "## Prompt 1: ok\n\n**Prompt to agent:**\n\n> A\n\n### Expected behaviors\n- [ ] x\n\n"
    FAILING = "## Prompt 2: bad\n\n**Prompt to agent:**\n\n> B\n\n### Expected behaviors\n- [ ] y\n"

    def _run(self, md_body, extra):
        from unittest import mock
        f = tempfile.NamedTemporaryFile("w", suffix=".md", delete=False)
        f.write("# Eval: s\n\n" + md_body)
        f.close()
        prompts = eval_judge.parse_eval_markdown(Path(f.name))

        def fake_run(ep, args, run_dir):
            run_dir.mkdir(parents=True, exist_ok=True)
            (run_dir / "transcript.txt").write_text("t")
            return [eval_judge.JudgeResult("c", ep.prompt_num == 1, "")]

        out = Path(tempfile.mkdtemp())
        self.addCleanup(eval_judge.shutil.rmtree, out, True)
        with mock.patch.object(eval_judge, "discover_evals", return_value=prompts), \
             mock.patch.object(eval_judge, "run_and_grade", side_effect=fake_run), \
             mock.patch.object(eval_judge.shutil, "which", return_value="/usr/bin/claude"), \
             mock.patch.dict(eval_judge.os.environ, {"ANTHROPIC_API_KEY": "k"}):
            rc = eval_judge.main(["--out", str(out)] + extra)
        files = sorted(p.relative_to(out).as_posix() for p in out.rglob("*") if p.is_file())
        return rc, out, files

    def test_prune_keeps_only_failures(self):
        rc, _, files = self._run(self.PASSING + self.FAILING, ["--prune-passing"])
        self.assertEqual(rc, 1)
        self.assertEqual(len(files), 1)
        self.assertTrue(files[0].endswith("/s/prompt-2/1/transcript.txt"), files)

    def test_prune_leaves_no_empty_dirs(self):
        rc, out, files = self._run(self.PASSING, ["--prune-passing"])
        self.assertEqual(rc, 0)
        self.assertEqual(files, [])
        self.assertEqual(list(out.iterdir()), [])  # stamp/skill dirs removed too
        self.assertTrue(out.exists())             # but never the output root

    def test_no_prune_by_default(self):
        _, _, files = self._run(self.PASSING + self.FAILING, [])
        self.assertEqual(len(files), 2)


class GatewayTokenRefreshTests(unittest.TestCase):
    def setUp(self):
        from unittest import mock
        eval_judge._gateway_token_minted_at = None
        self.env = mock.patch.dict(eval_judge.os.environ, {
            "DOCKERPUBLICBOT_USERNAME": "bot", "DOCKERPUBLICBOT_READ_PAT": "pat",
            "DOCKER_GATEWAY_TOKEN": "old",
        })
        self.env.start()
        self.addCleanup(self.env.stop)

    def _mock_login(self, token):
        import io, json
        from unittest import mock
        resp = mock.MagicMock()
        resp.__enter__.return_value = io.BytesIO(json.dumps({"token": token}).encode())
        return mock.patch("urllib.request.urlopen", return_value=resp)

    def test_mints_then_reuses_until_max_age(self):
        from unittest import mock
        with self._mock_login("fresh") as login, mock.patch("time.monotonic", side_effect=[0, 60, 700]):
            eval_judge.refresh_docker_gateway_token()   # t=0: first mint
            eval_judge.refresh_docker_gateway_token()   # t=60s: still fresh
            eval_judge.refresh_docker_gateway_token()   # t=700s: > 10 min, re-mint
        self.assertEqual(login.call_count, 2)
        self.assertEqual(eval_judge.os.environ["DOCKER_GATEWAY_TOKEN"], "fresh")

    def test_noop_without_hub_credentials(self):
        del eval_judge.os.environ["DOCKERPUBLICBOT_READ_PAT"]
        with self._mock_login("fresh") as login:
            eval_judge.refresh_docker_gateway_token()
        login.assert_not_called()
        self.assertEqual(eval_judge.os.environ["DOCKER_GATEWAY_TOKEN"], "old")

    def test_hub_credentials_not_in_agent_env_filter(self):
        env = {k: v for k, v in eval_judge.os.environ.items()
               if v and k not in eval_judge.HUB_CREDENTIAL_VARS}
        self.assertNotIn("DOCKERPUBLICBOT_READ_PAT", env)
        self.assertIn("DOCKER_GATEWAY_TOKEN", env)


class ParseJudgeJsonTests(unittest.TestCase):
    def test_plain_json(self):
        self.assertEqual(eval_judge.parse_judge_json('{"evaluations": []}'), {"evaluations": []})

    def test_fenced_json(self):
        text = 'Here you go:\n```json\n{"evaluations": [{"criterion_number": 1}]}\n```'
        self.assertEqual(len(eval_judge.parse_judge_json(text)["evaluations"]), 1)

    def test_trailing_commas(self):
        text = '{"evaluations": [\n  {"criterion_number": 1, "passed": true,},\n  ],\n}'
        self.assertEqual(eval_judge.parse_judge_json(text)["evaluations"][0]["passed"], True)

    def test_ellipsis_placeholder_line(self):
        text = '{"evaluations": [\n  {"criterion_number": 1, "passed": true},\n  ...\n]}'
        self.assertEqual(len(eval_judge.parse_judge_json(text)["evaluations"]), 1)

    def test_prose_around_object(self):
        text = 'Evaluation:\n{"evaluations": [{"criterion_number": 2}]}\nDone.'
        self.assertEqual(eval_judge.parse_judge_json(text)["evaluations"][0]["criterion_number"], 2)

    def test_unrecoverable_raises(self):
        import json
        with self.assertRaises(json.JSONDecodeError):
            eval_judge.parse_judge_json('not json at all {')


class JudgeRetryTests(unittest.TestCase):
    def test_empty_reply_error_includes_stop_reason(self):
        import io, json
        from unittest import mock
        resp = mock.MagicMock()
        resp.__enter__.return_value = io.BytesIO(json.dumps(
            {"content": [], "stop_reason": "max_tokens"}).encode())
        with mock.patch("urllib.request.urlopen", return_value=resp), \
             mock.patch.dict(eval_judge.os.environ, {"ANTHROPIC_API_KEY": "k"}):
            with self.assertRaises(json.JSONDecodeError) as ctx:
                eval_judge.call_judge("p", "claude-sonnet-4-5")
        self.assertIn("stop_reason=max_tokens", str(ctx.exception))
        self.assertIn("reply_chars=0", str(ctx.exception))
    def test_retries_after_malformed_json(self):
        import json
        from unittest import mock
        good = {"evaluations": [{"criterion_number": 1, "criterion_type": "expected", "passed": True}]}
        bad = json.JSONDecodeError("Expecting property name", "{,}", 1)
        with mock.patch.object(eval_judge, "call_judge", side_effect=[bad, good]) as m:
            results = eval_judge.judge_transcript("t", ["do A"], [], "m")
        self.assertEqual(m.call_count, 2)
        self.assertTrue(results[0].passed)

    def test_gives_up_after_max_attempts(self):
        from unittest import mock
        err = eval_judge.JudgeAPIError(500, "server error")
        with mock.patch.object(eval_judge, "call_judge", side_effect=err) as m:
            results = eval_judge.judge_transcript("t", ["do A"], ["Must NOT do B"], "m")
        self.assertEqual(m.call_count, eval_judge.JUDGE_ATTEMPTS)
        self.assertTrue(all(not r.passed for r in results))
        self.assertIn("after 3 attempt(s)", results[0].reasoning)

    def test_does_not_retry_auth_errors(self):
        from unittest import mock
        err = eval_judge.JudgeAPIError(401, "unauthorized")
        with mock.patch.object(eval_judge, "call_judge", side_effect=err) as m:
            results = eval_judge.judge_transcript("t", ["do A"], [], "m")
        self.assertEqual(m.call_count, 1)
        self.assertIn("401", results[0].reasoning)

    def test_retries_rate_limit(self):
        from unittest import mock
        good = {"evaluations": [{"criterion_number": 1, "criterion_type": "expected", "passed": True}]}
        with mock.patch.object(eval_judge, "call_judge",
                               side_effect=[eval_judge.JudgeAPIError(429, "slow down"), good]) as m:
            results = eval_judge.judge_transcript("t", ["do A"], [], "m")
        self.assertEqual(m.call_count, 2)
        self.assertTrue(results[0].passed)


if __name__ == "__main__":
    unittest.main()

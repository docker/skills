"""Unit tests for check_sbx_drift.py and its workflow (offline: fake sbx, no model)."""

import json
import os
import re
import stat
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).parent))
import check_sbx_drift as drift


REPO_ROOT = Path(__file__).resolve().parent.parent
WORKFLOW = (REPO_ROOT / ".github" / "workflows" / "sbx-drift.yml").read_text()
CI_SCRIPT = (REPO_ROOT / "scripts" / "ci.sh").read_text()

ROOT_HELP = """\
Description:
  Docker Sandboxes.

Usage:
  sbx COMMAND

Sandbox Commands:
  port        Manage sandbox port publishing
  run         Run an agent in a sandbox

Other Commands:
  completion  Generate the autocompletion script for the specified shell
  help        Help about any command

Flags:
      --cloud   Dispatch to Docker Cloud Sandboxes API
  -h, --help    help for sbx
"""

PORT_HELP = """\
Usage:
  sbx port COMMAND

Available Commands:
  ls          List published ports

Flags:
  -h, --help   help for port

Global Flags:
      --cloud   Dispatch to Docker Cloud Sandboxes API
  -D, --debug   Enable debug logging

Use "sbx port COMMAND --help" for more information about a command.
"""

# A fake sbx: a tiny command tree, a hidden `events` command, a hidden deprecated
# `ports` command, a hidden `--model` flag on `run`, and a sign-in-gated `port ls --help`.
FAKE_SBX = r"""#!/bin/sh
if [ -n "$DOCKERPUBLICBOT_READ_PAT$DOCKER_GATEWAY_TOKEN" ]; then echo "secret leaked" >&2; exit 3; fi
[ "$1" = "--cloud" ] && shift
case "$*" in
  "version") echo "sbx version v9.8.7 abcdef" ;;
  "--help") cat <<'EOF'
__ROOT__
EOF
  ;;
  "port --help") cat <<'EOF'
__PORT__
EOF
  ;;
  "port ls --help") echo "error: not signed in to Docker" >&2; exit 1 ;;
  "help port ls") printf 'Usage:\n  sbx port ls SANDBOX\n' ;;
  "run --help") printf 'Usage:\n  sbx run [flags] AGENT\n\nFlags:\n  -d, --detach   Detach\n' ;;
  "run --model=1 --help") printf 'Usage:\n  sbx run [flags] AGENT\n' ;;
  "run --"*"=1 --help") echo "Error: unknown flag: ${1%%=*}" >&2; exit 1 ;;
  "events --help") printf 'Usage:\n  sbx events [flags]\n' ;;
  "ports --help") printf 'Description:\n  Deprecated: use "sbx port ls".\n\nUsage:\n  sbx ports SANDBOX\n' ;;
  *) printf 'Usage:\n  sbx COMMAND\n' ;;
esac
""".replace("__ROOT__", ROOT_HELP.rstrip()).replace("__PORT__", PORT_HELP.rstrip())


def make_fake_sbx(directory: str) -> str:
    path = Path(directory) / "sbx"
    path.write_text(FAKE_SBX)
    path.chmod(path.stat().st_mode | stat.S_IXUSR)
    return str(path)


class HelpTreeTests(unittest.TestCase):
    def test_parse_subcommands_reads_every_commands_section(self):
        self.assertEqual(drift.parse_subcommands(ROOT_HELP), ["port", "run"])
        self.assertEqual(drift.parse_subcommands(PORT_HELP), ["ls"])
        self.assertEqual(drift.parse_subcommands("Usage:\n  sbx ls\n\nFlags:\n  -q  quiet\n"), [])

    def test_strip_global_flags(self):
        stripped = drift.strip_global_flags(PORT_HELP)
        self.assertNotIn("Global Flags", stripped)
        self.assertNotIn("--debug", stripped)
        self.assertIn('Use "sbx port COMMAND --help"', stripped)
        self.assertIn("help for port", stripped)

    def test_merge_help_keeps_only_cloud_pages_that_differ(self):
        local = {"sbx": "root\n", "sbx run": "run local\n"}
        cloud = {"sbx --cloud": "root\n", "sbx --cloud run": "run cloud\n"}
        self.assertEqual(drift.merge_help(local, cloud),
                         {"sbx": "root\n", "sbx run": "run local\n", "sbx --cloud run": "run cloud\n"})

    def test_collect_help_walks_tree_with_sign_in_fallback_and_no_secrets(self):
        with tempfile.TemporaryDirectory() as tmp:
            sbx = make_fake_sbx(tmp)
            env = {"DOCKERPUBLICBOT_READ_PAT": "pat", "DOCKER_GATEWAY_TOKEN": "tok"}
            with mock.patch.dict(os.environ, env):
                pages = drift.collect_help(sbx)
                self.assertEqual(drift.sbx_version(sbx), "v9.8.7")
        self.assertEqual(list(pages), ["sbx", "sbx port", "sbx run", "sbx port ls"])
        self.assertIn("sbx port ls SANDBOX", pages["sbx port ls"])
        self.assertIn("$ sbx run --help\nUsage:", drift.render_help(pages))


class SourceTests(unittest.TestCase):
    def test_docs_page_urls_filters_prefix_and_release_notes(self):
        sitemap = textwrap.dedent("""\
            <?xml version="1.0" encoding="utf-8"?>
            <urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
              <url><loc>https://docs.docker.com/ai/sandboxes/</loc></url>
              <url><loc>https://docs.docker.com/ai/sandboxes/usage/</loc></url>
              <url><loc>https://docs.docker.com/ai/sandboxes/release-notes/</loc></url>
              <url><loc>https://docs.docker.com/ai/sandboxes-api/</loc></url>
              <url><loc>https://docs.docker.com/reference/cli/sbx/</loc></url>
            </urlset>""")
        self.assertEqual(drift.docs_page_urls(sitemap),
                         ["https://docs.docker.com/ai/sandboxes/", "https://docs.docker.com/ai/sandboxes/usage/"])
        self.assertEqual(drift.markdown_url("https://docs.docker.com/ai/sandboxes/usage/"),
                         "https://docs.docker.com/ai/sandboxes/usage.md")

    def test_skill_documents_cover_sandbox_skills_without_evals(self):
        sources = [d.source for d in drift.load_skill_documents()]
        self.assertIn("skills/docker-sandboxes-lifecycle/SKILL.md", sources)
        self.assertTrue(all(s.startswith("skills/docker-sandboxes-") for s in sources))
        self.assertFalse(any("/evals/" in s for s in sources))

    def test_batch_documents_groups_and_splits(self):
        docs = [drift.Document("a", "x" * 40), drift.Document("b", "y" * 40), drift.Document("c", "z" * 130)]
        batches = drift.batch_documents(docs, max_chars=100)
        self.assertEqual([[d.source for d in b] for b in batches],
                         [["a", "b"], ["c (part 1)"], ["c (part 2)"]])
        self.assertTrue(all(sum(len(d.text) for d in b) <= 100 for b in batches))


class FindingTests(unittest.TestCase):
    HELP = "$ sbx port --help\nUsage:\n  sbx port COMMAND\n"
    BATCH = [drift.Document("skills/x/SKILL.md", "Run `sbx ports SANDBOX --publish 8080`\nto publish.")]

    def finding(self, **overrides):
        raw = {"source": "skills/x/SKILL.md", "kind": "missing_command", "command": "sbx ports",
               "document_quote": "Run sbx ports SANDBOX --publish 8080 to publish.",
               "help_quote": "Usage: sbx port COMMAND", "problem": "renamed"}
        raw.update(overrides)
        return drift.verify_findings({"findings": [raw]}, self.HELP, self.BATCH)[0]

    def test_quotes_are_matched_modulo_markdown_and_whitespace(self):
        f = self.finding()
        self.assertTrue(f.verified, f.unverified_reason)
        self.assertEqual((f.kind, f.command), ("missing_command", "sbx ports"))

    def test_ungrounded_findings_are_not_verified(self):
        self.assertEqual(self.finding(source="other.md").unverified_reason, "unknown source")
        self.assertIn("document quote", self.finding(document_quote="sbx portz").unverified_reason)
        self.assertIn("document quote", self.finding(document_quote="").unverified_reason)
        self.assertIn("help quote", self.finding(help_quote="sbx ports COMMAND").unverified_reason)
        self.assertTrue(self.finding(help_quote="").verified)

    def test_parse_command(self):
        self.assertEqual(drift.parse_command("sbx --cloud schedule ls"), (["--cloud"], ["schedule", "ls"]))
        self.assertEqual(drift.parse_command("sbx run / sbx create"), ([], ["run"]))
        self.assertEqual(drift.parse_command("sbx (global flags)"), ([], []))
        self.assertEqual(drift.parse_command("sbx"), ([], []))
        self.assertIsNone(drift.parse_command("docker sandbox ls"))

    def test_hidden_commands_and_flags_are_ignored_unless_deprecated(self):
        def reason(kind, command, flag=""):
            return drift.hidden_reason(sbx, drift.Finding("s", command, "", "", "", kind=kind, flag=flag))

        with tempfile.TemporaryDirectory() as tmp:
            sbx = make_fake_sbx(tmp)
            self.assertIn("hidden command", reason("missing_command", "sbx events"))
            self.assertIn("hidden command", reason("missing_command", "sbx --cloud events"))
            self.assertIsNone(reason("missing_command", "sbx start"))  # falls back to root help
            self.assertIsNone(reason("missing_command", "sbx ports"))  # deprecated
            self.assertIsNone(reason("missing_command", "sbx rm"))  # never probed
            self.assertIn("hidden flag", reason("missing_flag", "sbx run", "--model"))
            self.assertIsNone(reason("missing_flag", "sbx run", "--detached"))
            self.assertIsNone(reason("missing_flag", "sbx run", "--x; rm -rf /"))
            self.assertIsNone(reason("other", "sbx run"))

    def test_report_counts_verified_findings_and_annotates(self):
        verified = drift.Finding("skills/x/SKILL.md", "sbx ports", "q", "", "renamed 100%")
        ignored = drift.Finding("https://docs.docker.com/ai/sandboxes/", "sbx run", "q", "", "p",
                                verified=False, unverified_reason="hidden")
        with mock.patch.dict(os.environ, {"GITHUB_ACTIONS": "true"}), \
                mock.patch("sys.stdout") as out:
            self.assertEqual(drift.report([verified, ignored]), 1)
        printed = "".join(call.args[0] for call in out.write.call_args_list)
        self.assertIn("::error file=skills/x/SKILL.md,title=sbx drift (sbx ports)::", printed)
        self.assertIn("renamed 100%25", printed)
        self.assertIn("(ignored, hidden)", printed)


class StreamTests(unittest.TestCase):
    @staticmethod
    def events(*events):
        return [f"data: {json.dumps(e)}\n".encode() for e in events]

    def test_read_stream_keeps_text_and_skips_thinking(self):
        lines = [b"event: message_start\n"] + self.events(
            {"type": "content_block_delta", "delta": {"type": "thinking_delta", "thinking": "hmm"}},
            {"type": "content_block_delta", "delta": {"type": "text_delta", "text": '{"findings": '}},
            {"type": "content_block_delta", "delta": {"type": "text_delta", "text": "[]}"}},
            {"type": "message_delta", "delta": {"stop_reason": "end_turn"}},
        )
        self.assertEqual(drift.read_stream(lines), '{"findings": []}')

    def test_read_stream_errors(self):
        with self.assertRaises(drift.DriftError):
            drift.read_stream(self.events({"type": "message_delta", "delta": {"stop_reason": "max_tokens"}}))
        with self.assertRaises(drift.eval_judge.JudgeAPIError) as ctx:
            drift.read_stream(self.events({"type": "error", "error": {"type": "overloaded_error"}}))
        self.assertTrue(ctx.exception.retryable)


class MainTests(unittest.TestCase):
    def test_dry_run_collects_sources_offline(self):
        with tempfile.TemporaryDirectory() as tmp, mock.patch("sys.stdout") as out:
            self.assertEqual(drift.main(["--sbx", make_fake_sbx(tmp), "--no-docs", "--dry-run"]), 0)
        printed = "".join(call.args[0] for call in out.write.call_args_list)
        self.assertIn("sbx: v9.8.7", printed)
        self.assertIn("batches:", printed)

    def test_model_errors_fail_the_run_and_keep_other_results(self):
        finding = drift.Finding("skills/x/SKILL.md", "sbx ports", "q", "", "renamed")

        def fake_check(sbx, help_text, version, batch, model):
            if batch[0].source == "bad":
                raise drift.DriftError("boom")
            return [finding]

        docs = [drift.Document("good", "a"), drift.Document("bad", "b")]
        with tempfile.TemporaryDirectory() as tmp, \
                mock.patch.object(drift, "load_skill_documents", return_value=docs), \
                mock.patch.object(drift, "batch_documents", side_effect=lambda d: [[x] for x in d]), \
                mock.patch.object(drift.eval_judge, "get_docker_gateway_token", return_value="t"), \
                mock.patch.object(drift, "check_batch", side_effect=fake_check), \
                mock.patch("sys.stdout"), mock.patch("sys.stderr"):
            sbx = make_fake_sbx(tmp)
            self.assertEqual(drift.main(["--sbx", sbx, "--no-docs"]), 1)

            def always_fails(*args):
                raise drift.DriftError("boom")

            with mock.patch.object(drift, "check_batch", side_effect=always_fails):
                self.assertEqual(drift.main(["--sbx", sbx, "--no-docs"]), 2)


class WorkflowTests(unittest.TestCase):
    def test_daily_and_manual_triggers_only(self):
        self.assertRegex(WORKFLOW, r'schedule:\n    - cron: "\d+ \d+ \* \* \*"')
        self.assertIn("  workflow_dispatch:", WORKFLOW)
        self.assertNotIn("pull_request", WORKFLOW)
        self.assertIn("permissions:\n  contents: read", WORKFLOW)
        self.assertIn("persist-credentials: false", WORKFLOW)

    def test_actions_are_pinned_and_inputs_go_through_env(self):
        for ref in re.findall(r"uses: \S+@(\S+)", WORKFLOW):
            self.assertRegex(ref, r"^[0-9a-f]{40}$")
        self.assertIn("INPUT_SBX_VERSION: ${{ inputs.sbx_version }}", WORKFLOW)
        run_blocks = re.findall(r"run: (?:\|\n(?:          .*\n|\n)+|.*\n)", WORKFLOW)
        self.assertTrue(run_blocks)
        for block in run_blocks:
            self.assertNotIn("${{", block)

    def test_latest_release_and_gateway_credentials(self):
        self.assertIn("gh release view --repo docker/sbx-releases", WORKFLOW)
        self.assertIn("DockerSandboxes-linux-amd64.tar.gz", WORKFLOW)
        self.assertIn("DOCKERPUBLICBOT_READ_PAT: ${{ secrets.DOCKERPUBLICBOT_READ_PAT }}", WORKFLOW)
        self.assertIn('python3 scripts/check_sbx_drift.py --sbx "$SBX_BIN"', WORKFLOW)

    def test_live_check_stays_out_of_offline_ci(self):
        self.assertNotIn("check_sbx_drift.py", CI_SCRIPT)


if __name__ == "__main__":
    unittest.main()

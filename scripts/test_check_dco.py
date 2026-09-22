import contextlib
import io
import os
import pathlib
import subprocess
import tempfile
import unittest

from check_dco import check_dco, main


class CheckDCOTests(unittest.TestCase):
    def setUp(self):
        self.root = tempfile.mkdtemp()
        self.run_command("git", "init", "-q")
        self.run_command("git", "config", "user.name", "Test User")
        self.run_command("git", "config", "user.email", "test@example.com")
        self.write("tracked.txt", "base\n")
        self.commit("base", signed=True)
        self.base = self.run_command("git", "rev-parse", "HEAD").stdout.strip()
        self.default_branch = self.run_command("git", "branch", "--show-current").stdout.strip()

    def run_command(self, *args):
        return subprocess.run(args, cwd=self.root, check=True, text=True, capture_output=True)

    def write(self, path, content):
        target = pathlib.Path(self.root, path)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content)

    def commit(self, subject, *, signed, trailer="Signed-off-by: Test User <test@example.com>"):
        self.run_command("git", "add", ".")
        message = subject + (f"\n\n{trailer}" if signed else "")
        self.run_command("git", "commit", "-qm", message)

    def test_accepts_valid_signoff_without_requiring_author_match(self):
        self.write("tracked.txt", "changed\n")
        self.commit("change", signed=True, trailer="Signed-off-by: Another Person <other@example.net>")
        self.assertEqual(check_dco(self.base, self.root), [])

    def test_rejects_missing_and_malformed_signoffs_without_echoing_messages(self):
        secret_subject = "do not print TOKEN_VALUE_123"
        self.write("tracked.txt", "one\n")
        self.commit(secret_subject, signed=False)
        self.write("tracked.txt", "two\n")
        self.commit("malformed", signed=True, trailer="Signed-off-by: bot")

        errors = check_dco(self.base, self.root)

        self.assertEqual(len(errors), 2)
        self.assertTrue(all("Signed-off-by: Name <email>" in error for error in errors))
        self.assertTrue(all("TOKEN_VALUE_123" not in error for error in errors))

    def test_reports_the_full_sha_for_each_offending_commit(self):
        expected_shas = []
        for number in range(3):
            self.write("tracked.txt", f"{number}\n")
            self.commit(f"unsigned {number}", signed=False)
            expected_shas.append(self.run_command("git", "rev-parse", "HEAD").stdout.strip())

        errors = check_dco(self.base, self.root)

        self.assertEqual({error.split()[1] for error in errors}, set(expected_shas))

    def test_rejects_signoff_outside_trailer_block(self):
        self.write("tracked.txt", "changed\n")
        self.commit("Signed-off-by: Test User <test@example.com>\n\nbody", signed=False)
        self.assertEqual(len(check_dco(self.base, self.root)), 1)

    def test_checks_only_non_merge_commits_after_base(self):
        self.run_command("git", "checkout", "-qb", "topic")
        self.write("topic.txt", "topic\n")
        self.commit("topic", signed=True)
        self.run_command("git", "checkout", "-q", self.default_branch)
        self.write("main.txt", "main\n")
        self.commit("main", signed=True)
        self.run_command("git", "merge", "--no-ff", "-qm", "unsigned merge", "topic")
        self.assertEqual(check_dco(self.base, self.root), [])

    def test_unavailable_base_is_actionable(self):
        self.assertIn("unavailable", check_dco("missing", self.root)[0])

    def test_cli_skips_without_base_and_reports_remediation_on_failure(self):
        previous = os.environ.pop("VERSION_CHECK_BASE_SHA", None)
        try:
            output = io.StringIO()
            with contextlib.redirect_stdout(output):
                self.assertEqual(main(["--root", self.root]), 0)
            self.assertIn("SKIP", output.getvalue())
        finally:
            if previous is not None:
                os.environ["VERSION_CHECK_BASE_SHA"] = previous

        self.write("tracked.txt", "unsigned\n")
        self.commit("unsigned", signed=False)
        stderr = io.StringIO()
        with contextlib.redirect_stderr(stderr):
            self.assertEqual(main([self.base, "--root", self.root]), 1)
        self.assertIn("git rebase --signoff <base>", stderr.getvalue())


if __name__ == "__main__":
    unittest.main()

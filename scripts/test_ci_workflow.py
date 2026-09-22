import pathlib
import unittest


REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
WORKFLOW = (REPO_ROOT / ".github" / "workflows" / "ci.yml").read_text()
CI_SCRIPT = (REPO_ROOT / "scripts" / "ci.sh").read_text()


class CIWorkflowTests(unittest.TestCase):
    def test_pull_requests_checkout_history_and_pass_base_sha(self):
        self.assertIn("persist-credentials: false", WORKFLOW)
        self.assertIn("fetch-depth: 0", WORKFLOW)
        self.assertIn("VERSION_CHECK_BASE_SHA: ${{ github.event.pull_request.base.sha }}", WORKFLOW)

    def test_ci_runs_pr_comparison_checks_without_requiring_a_base(self):
        self.assertIn('-e VERSION_CHECK_BASE_SHA="${VERSION_CHECK_BASE_SHA:-}"', CI_SCRIPT)
        self.assertIn('-e VALIDATION_HEAD_SHA="${VALIDATION_HEAD_SHA:-HEAD}"', CI_SCRIPT)
        self.assertIn(
            'python3 scripts/check_version_bumps.py "${VERSION_CHECK_BASE_SHA:-}" --head "${VALIDATION_HEAD_SHA:-HEAD}"',
            CI_SCRIPT,
        )
        self.assertIn(
            'python3 scripts/check_dco.py "${VERSION_CHECK_BASE_SHA:-}" --head "${VALIDATION_HEAD_SHA:-HEAD}"',
            CI_SCRIPT,
        )
        self.assertLess(
            CI_SCRIPT.index("python3 scripts/check_version_bumps.py"),
            CI_SCRIPT.index("python3 scripts/check_dco.py"),
        )
        self.assertIn('-v "$REPO_ROOT/.git:/work/.git:ro"', CI_SCRIPT)

    def test_python_dependency_is_fully_pinned(self):
        requirements_in = (REPO_ROOT / "scripts" / "requirements.in").read_text()
        requirements = (REPO_ROOT / "scripts" / "requirements.txt").read_text()
        taskfile = (REPO_ROOT / "Taskfile.yml").read_text()
        install = "pip install -q --require-hashes -r scripts/requirements.txt"

        self.assertEqual(requirements_in, "PyYAML==6.0.3\n")
        self.assertIn("pyyaml==6.0.3", requirements)
        self.assertIn("--hash=sha256:", requirements)
        self.assertIn(install, CI_SCRIPT)
        self.assertEqual(taskfile.count(install), 4)
        self.assertNotIn("pip install -q pyyaml", CI_SCRIPT + taskfile)


if __name__ == "__main__":
    unittest.main()

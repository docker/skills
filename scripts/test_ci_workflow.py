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

    def test_ci_runs_version_check_without_requiring_a_base(self):
        self.assertIn('-e VERSION_CHECK_BASE_SHA="${VERSION_CHECK_BASE_SHA:-}"', CI_SCRIPT)
        self.assertIn("python3 scripts/check_version_bumps.py", CI_SCRIPT)
        self.assertIn('-v "$REPO_ROOT/.git:/work/.git:ro"', CI_SCRIPT)


if __name__ == "__main__":
    unittest.main()

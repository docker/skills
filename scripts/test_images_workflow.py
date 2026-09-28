"""Guard the image workflow's advisory and read-only execution contract."""

from pathlib import Path
import unittest


WORKFLOW = (Path(__file__).resolve().parent.parent / ".github/workflows/images.yml").read_text()


class ImageWorkflowTests(unittest.TestCase):
    def test_read_only_pr_advisory_and_full_schedule(self):
        self.assertIn("  pull_request:", WORKFLOW)
        self.assertNotIn("pull_request_target", WORKFLOW)
        self.assertIn("  schedule:", WORKFLOW)
        self.assertIn("  workflow_dispatch:", WORKFLOW)
        self.assertIn("  contents: read", WORKFLOW)
        self.assertIn("continue-on-error: ${{ github.event_name == 'pull_request' }}", WORKFLOW)
        self.assertIn("persist-credentials: false", WORKFLOW)
        self.assertIn("fetch-depth: 0", WORKFLOW)
        self.assertIn("IMAGE_CHECK_BASE_SHA: ${{ github.event.pull_request.base.sha }}", WORKFLOW)
        self.assertIn('python3 scripts/check_images.py --base "$IMAGE_CHECK_BASE_SHA"', WORKFLOW)
        self.assertIn("          python3 scripts/check_images.py\n", WORKFLOW)
        self.assertNotIn("${{ github.event.pull_request.head", WORKFLOW)


if __name__ == "__main__":
    unittest.main()

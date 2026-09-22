import pathlib
import unittest

import yaml


REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
WORKFLOW_PATH = REPO_ROOT / ".github" / "workflows" / "scorecard.yml"


class ScorecardWorkflowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.workflow_text = WORKFLOW_PATH.read_text(encoding="utf-8")
        cls.workflow = yaml.safe_load(cls.workflow_text)
        cls.scorecard_job = cls.workflow["jobs"]["scorecard"]

    def test_permissions_are_read_only_except_required_publication_writes(self):
        self.assertEqual("read-all", self.workflow["permissions"])
        self.assertEqual(
            {"security-events": "write", "id-token": "write"},
            self.scorecard_job["permissions"],
        )

    def test_scorecard_results_are_published(self):
        analysis_step = next(
            step for step in self.scorecard_job["steps"] if step.get("name") == "Run analysis"
        )
        self.assertEqual(True, analysis_step["with"]["publish_results"])

    def test_checkout_does_not_persist_credentials(self):
        checkout_step = next(
            step for step in self.scorecard_job["steps"] if step.get("name") == "Checkout repository"
        )
        self.assertEqual(False, checkout_step["with"]["persist-credentials"])

    def test_actions_are_pinned_to_full_commit_shas(self):
        for step in self.scorecard_job["steps"]:
            if action := step.get("uses"):
                self.assertRegex(action, r"^[^@]+@[0-9a-f]{40}$")

    def test_workflow_has_no_ambient_execution_configuration(self):
        for key in ("env", "defaults"):
            self.assertNotIn(key, self.workflow)
            self.assertNotIn(key, self.scorecard_job)
        for key in ("container", "services"):
            self.assertNotIn(key, self.scorecard_job)


if __name__ == "__main__":
    unittest.main()

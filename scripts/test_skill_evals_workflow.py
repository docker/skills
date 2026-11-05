import pathlib
import re
import unittest


REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
WORKFLOW = (REPO_ROOT / ".github" / "workflows" / "skill-evals.yml").read_text()
CI_SCRIPT = (REPO_ROOT / "scripts" / "ci.sh").read_text()


class SkillEvalsWorkflowTests(unittest.TestCase):
    def test_live_evals_stay_out_of_offline_ci(self):
        self.assertNotIn("skill_eval.py", CI_SCRIPT)
        self.assertIn("python3 -m unittest discover", CI_SCRIPT)

    def test_triggers_and_least_privilege(self):
        for trigger in ("pull_request:", "schedule:", "workflow_dispatch:"):
            self.assertIn(trigger, WORKFLOW)
        self.assertIn("permissions:\n  contents: read", WORKFLOW)
        self.assertIn("persist-credentials: false", WORKFLOW)
        self.assertIn("github.event.pull_request.head.repo.full_name == github.repository", WORKFLOW)

    def test_actions_and_tools_are_pinned(self):
        for ref in re.findall(r"uses: \S+@(\S+)", WORKFLOW):
            self.assertRegex(ref, r"^[0-9a-f]{40}$")
        self.assertRegex(WORKFLOW, r'CLAUDE_CODE_VERSION: "\d+\.\d+\.\d+"')
        self.assertRegex(WORKFLOW, r'SBX_VERSION: "\d+\.\d+\.\d+"')
        self.assertIn("--ignore-scripts", WORKFLOW)
        self.assertIn("pip install -q --require-hashes -r scripts/requirements.txt", WORKFLOW)

    def test_inputs_reach_the_shell_only_through_env(self):
        run_lines = [line for line in WORKFLOW.splitlines() if line.strip().startswith("run:")]
        for line in run_lines:
            self.assertNotIn("${{", line)
        self.assertIn("INPUT_SKILL: ${{ inputs.skill }}", WORKFLOW)

    def test_artifacts_are_uploaded_even_on_failure(self):
        self.assertIn("if: always()", WORKFLOW)
        self.assertIn("path: .skill-evals/", WORKFLOW)


if __name__ == "__main__":
    unittest.main()

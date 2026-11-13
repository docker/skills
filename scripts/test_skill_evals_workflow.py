import pathlib
import re
import unittest


REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
WORKFLOW = (REPO_ROOT / ".github" / "workflows" / "skill-evals.yml").read_text()
CI_SCRIPT = (REPO_ROOT / "scripts" / "ci.sh").read_text()


class SkillEvalsWorkflowTests(unittest.TestCase):
    def test_live_evals_stay_out_of_offline_ci(self):
        # eval_judge.py should not be in offline CI (it calls live models)
        self.assertNotIn("eval_judge.py", CI_SCRIPT)
        self.assertIn("python3 -m unittest discover", CI_SCRIPT)

    def test_triggers_and_least_privilege(self):
        for trigger in ("pull_request:", "schedule:", "workflow_dispatch:"):
            self.assertIn(trigger, WORKFLOW)
        self.assertIn("permissions:\n  contents: read", WORKFLOW)
        self.assertIn("persist-credentials: false", WORKFLOW)
        # Fork PRs now run and fail explicitly if secrets are missing (no skip condition)

    def test_actions_and_tools_are_pinned(self):
        for ref in re.findall(r"uses: \S+@(\S+)", WORKFLOW):
            self.assertRegex(ref, r"^[0-9a-f]{40}$")
        self.assertRegex(WORKFLOW, r'CLAUDE_CODE_VERSION: "\d+\.\d+\.\d+"')
        self.assertRegex(WORKFLOW, r'SBX_VERSION: "\d+\.\d+\.\d+"')
        self.assertIn("--ignore-scripts", WORKFLOW)
        self.assertIn("pip install -q --require-hashes -r scripts/requirements.txt", WORKFLOW)

    def test_inputs_reach_the_shell_only_through_env(self):
        # Check that run: lines don't have direct ${{ }} interpolation
        # (except for matrix.skill which is safe as it comes from our own detect-changes)
        run_lines = [line for line in WORKFLOW.splitlines() if line.strip().startswith("run:")]
        for line in run_lines:
            self.assertNotIn("${{ inputs", line)
        # Model and repeat inputs should go through env vars
        self.assertIn("INPUT_MODEL: ${{ inputs.model", WORKFLOW)
        self.assertIn("INPUT_REPEAT: ${{ inputs.repeat", WORKFLOW)

    def test_artifacts_are_uploaded_even_on_failure(self):
        self.assertIn("if: always()", WORKFLOW)
        self.assertIn("path: .eval-judge/", WORKFLOW)

    def test_per_skill_matrix_jobs(self):
        # Verify the workflow uses matrix strategy for per-skill parallelism
        self.assertIn("strategy:", WORKFLOW)
        self.assertIn("fail-fast: false", WORKFLOW)
        self.assertIn("matrix:", WORKFLOW)
        self.assertIn("skill: ${{ fromJson(needs.detect-changes.outputs.skills) }}", WORKFLOW)

    def test_guardrails_excluded_from_ci(self):
        # docker-destructive-guardrails should not be in the ALL_SKILLS list
        self.assertNotIn('"docker-destructive-guardrails"', WORKFLOW)

    def test_untrusted_values_not_interpolated_into_shell(self):
        # matrix.skill comes from PR directory names and inputs.skill from users:
        # they must reach run: scripts only through env vars, never ${{ }} in shell
        for line in WORKFLOW.splitlines():
            stripped = line.strip()
            if stripped.startswith(("- name:", "name:", "skill:", "SKILL:", "INPUT_SKILL:")):
                continue
            self.assertNotIn("${{ matrix.skill }}", stripped, line)
            self.assertNotIn("${{ inputs.skill }}", stripped, line)
        self.assertIn("SKILL_ID_RE='^[a-z0-9][a-z0-9-]*$'", WORKFLOW)

    def test_kits_excluded_from_ci(self):
        # docker-sandboxes-kits is excluded until its signing guidance matches docs.docker.com
        self.assertNotIn('"docker-sandboxes-kits"', WORKFLOW)
        self.assertIn("docker-destructive-guardrails|docker-sandboxes-kits", WORKFLOW)


if __name__ == "__main__":
    unittest.main()

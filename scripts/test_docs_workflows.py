import pathlib
import unittest

import yaml


REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
DOCS_WORKFLOW = REPO_ROOT / ".github" / "workflows" / "docs.yml"
DEPLOY_WORKFLOW = REPO_ROOT / ".github" / "workflows" / "docs-deploy.yml"


class DocsWorkflowTests(unittest.TestCase):
    def load(self, path):
        return yaml.safe_load(path.read_text(encoding="utf-8"))

    def test_validation_workflow_is_path_filtered_and_read_only(self):
        workflow = self.load(DOCS_WORKFLOW)
        self.assertEqual(workflow["permissions"], {"contents": "read"})
        triggers = workflow["on"]
        for event in ("push", "pull_request"):
            paths = triggers[event]["paths"]
            self.assertIn("docs/**", paths)
            self.assertIn("catalog.yaml", paths)
            self.assertIn("skills/*/skill.yaml", paths)
            self.assertIn("scripts/requirements.txt", paths)
            self.assertIn("Taskfile.yml", paths)
        steps = workflow["jobs"]["validate"]["steps"]
        serialized = str(steps)
        self.assertIn("markdownlint-cli2@0.22.1", serialized)
        self.assertIn("render_catalog.py --check", serialized)
        self.assertIn("hugo --gc --panicOnWarning", serialized)
        self.assertIn("docs_check.py --built-output docs/public", serialized)
        self.assertIn("--destination /tmp/hugo-public --cacheDir /tmp/hugo-cache --noBuildLock", (REPO_ROOT / "Taskfile.yml").read_text(encoding="utf-8"))

    def test_deploy_uses_pages_permissions_only_in_deploy_job(self):
        workflow = self.load(DEPLOY_WORKFLOW)
        self.assertEqual(workflow["permissions"], {"contents": "read"})
        jobs = workflow["jobs"]
        self.assertEqual(jobs["build"]["permissions"], {"contents": "read", "pages": "write"})
        self.assertEqual(
            jobs["deploy"]["permissions"],
            {"pages": "write", "id-token": "write"},
        )
        self.assertEqual(jobs["deploy"]["needs"], "build")
        serialized = str(workflow)
        self.assertIn("actions/configure-pages@", serialized)
        self.assertIn("actions/upload-pages-artifact@", serialized)
        self.assertIn("actions/deploy-pages@", serialized)
        self.assertIn('${BASE_URL}/', serialized)

    def test_docs_container_hugo_metadata_matches_ci_action(self):
        dockerfile = (REPO_ROOT / "docs" / "Dockerfile").read_text(encoding="utf-8")
        action = self.load(REPO_ROOT / ".github" / "actions" / "setup-hugo" / "action.yml")
        environment = action["runs"]["steps"][0]["env"]
        self.assertIn(f"ARG HUGO_VERSION={environment['HUGO_VERSION']}", dockerfile)
        self.assertIn(f"ARG HUGO_SHA256_AMD64={environment['HUGO_SHA256']}", dockerfile)

    def test_all_external_actions_are_pinned_to_full_shas(self):
        for path in (DOCS_WORKFLOW, DEPLOY_WORKFLOW):
            workflow = self.load(path)
            for job in workflow["jobs"].values():
                for step in job.get("steps", []):
                    uses = step.get("uses", "")
                    if not uses or uses.startswith("./"):
                        continue
                    ref = uses.rsplit("@", 1)[-1].split()[0]
                    self.assertRegex(ref, r"^[0-9a-f]{40}$", uses)


if __name__ == "__main__":
    unittest.main()

import pathlib
import unittest


REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
WORKFLOW = REPO_ROOT / ".github" / "workflows" / "release.yml"
STEP_NAME = "      - name: Create or refresh draft GitHub release\n"


class ReleaseWorkflowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        workflow = WORKFLOW.read_text()
        cls.release_step = workflow.split(STEP_NAME, maxsplit=1)[1]

    def test_mutation_responses_drive_asset_upload(self):
        self.assertIn(
            'refreshed_release="$(gh api --method PATCH \\\n'
            '              "repos/$GITHUB_REPOSITORY/releases/$release_id"',
            self.release_step,
        )
        self.assertIn(
            'refreshed_release="$(gh api --method POST \\\n'
            '              "repos/$GITHUB_REPOSITORY/releases"',
            self.release_step,
        )
        mutation_section, asset_section = self.release_step.split(
            '          if [[ "$(jq -r \'.draft\' <<<"$refreshed_release")" != true ]]; then\n',
            maxsplit=1,
        )
        mutation_section = mutation_section.split(
            '          if [[ "$release_exists" == true ]]; then\n',
            maxsplit=1,
        )[1]
        self.assertNotIn("releases?per_page=100", mutation_section)
        self.assertIn("release_id=", asset_section)
        self.assertIn("upload_url=", asset_section)

    def test_release_safety_and_asset_integrity_guards_remain(self):
        self.assertIn("already published; it will not be modified", self.release_step)
        self.assertIn("is no longer a draft; refusing to upload assets", self.release_step)
        self.assertIn(
            'repos/$GITHUB_REPOSITORY/releases/$release_id/assets',
            self.release_step,
        )
        self.assertIn("refusing to overwrite it", self.release_step)
        self.assertIn('gh api --method POST "$upload_url?name=$name"', self.release_step)


if __name__ == "__main__":
    unittest.main()

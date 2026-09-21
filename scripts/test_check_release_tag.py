import os
import tempfile
import unittest

import yaml

from check_release_tag import check_release_tag, main


class CheckReleaseTagTests(unittest.TestCase):
    def make_repo(self, version="1.2.3"):
        root = tempfile.mkdtemp()
        catalog = {
            "schema": "v1",
            "name": "test",
            "version": version,
            "products": [{"id": "build", "name": "Build", "description": "Images."}],
            "skills": [
                {
                    "id": "build-a",
                    "product": "build",
                    "path": "skills/build-a",
                    "version": "0.1.0",
                    "status": "stable",
                }
            ],
        }
        with open(os.path.join(root, "catalog.yaml"), "w") as handle:
            yaml.safe_dump(catalog, handle)
        return root

    def test_match(self):
        root = self.make_repo()
        self.assertEqual(check_release_tag("v1.2.3", root), [])
        self.assertEqual(main(["v1.2.3", "--root", root]), 0)

    def test_mismatch_is_clear(self):
        errors = check_release_tag("v1.2.4", self.make_repo())
        self.assertEqual(
            errors,
            ["release tag 'v1.2.4' does not match catalog distribution version; expected 'v1.2.3'"],
        )

    def test_invalid_catalog_version_fails(self):
        errors = check_release_tag("v1.2", self.make_repo("1.2"))
        self.assertTrue(any("'version' must be a string in X.Y.Z format" in error for error in errors))


if __name__ == "__main__":
    unittest.main()

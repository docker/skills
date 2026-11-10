"""Exercise the sbxenv kit helper's release selection and failure reporting offline."""

import contextlib
import importlib.util
import io
import json
from pathlib import Path
import sys
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parent.parent
HELPER = ROOT / "skills/docker-sandboxes-env/scripts/kits.py"
DIGEST_OLD = "sha256:" + "1" * 64
DIGEST_NEW = "sha256:" + "2" * 64


def load_helper():
    # Never leave __pycache__ inside the skill: content checks scan every file there.
    previous = sys.dont_write_bytecode
    sys.dont_write_bytecode = True
    try:
        spec = importlib.util.spec_from_file_location("sbxenv_kits", HELPER)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
    finally:
        sys.dont_write_bytecode = previous
    return module


kits = load_helper()


def tags(*names):
    # Hub returns tags newest-pushed first; selection must ignore this order.
    return [{"tag": name, "digest": DIGEST_NEW} for name in names]


class ReleaseSelectionTests(unittest.TestCase):
    def newest(self, names, like=None):
        found = kits._newest_release(tags(*names), like)
        return found[0] if found else None

    def test_numeric_order_beats_push_order_and_moving_tags(self):
        self.assertEqual(self.newest(["latest", "1.9.0", "edge", "1.10.0", "1.8.2"]), "1.10.0")

    def test_prereleases_only_when_current_tag_is_one(self):
        self.assertEqual(self.newest(["2.0.0-rc.1", "1.4.0"]), "1.4.0")
        self.assertEqual(self.newest(["2.0.0-rc.1", "1.4.0"], like="2.0.0-rc.0"), "2.0.0-rc.1")
        self.assertEqual(self.newest(["1.10.0-rc.1", "1.10.0"], like="1.10.0-rc.0"), "1.10.0")

    def test_moving_tags_only_yield_no_release(self):
        self.assertIsNone(self.newest(["latest", "edge", "main"]))

    def test_registry_and_local_sources_are_classified(self):
        for local in ("./kits/tool", "../tool", ".", "..", "/abs/kit", "dist/tool.zip",
                      "git+https://github.com/org/repo.git#dir=kits/tool"):
            self.assertFalse(kits.is_oci_reference(local), local)
        for remote in ("sbx/playwright", "sbx/playwright:1.61.1", "docker.io/sbx/claude"):
            self.assertTrue(kits.is_oci_reference(remote), remote)


class UpdateAndPinTests(unittest.TestCase):
    def patch_registry(self, names):
        stack = contextlib.ExitStack()
        self.addCleanup(stack.close)
        stack.enter_context(mock.patch.object(kits, "list_tags", return_value=tags(*names)))
        stack.enter_context(mock.patch.object(kits, "manifest", return_value=(DIGEST_NEW, None)))

    def test_update_moves_to_highest_release_and_keeps_digest_pin(self):
        self.patch_registry(["latest", "1.9.0", "1.10.0"])
        result = kits.update_one("sbx/example:1.9.0@" + DIGEST_OLD, False)
        self.assertEqual(result["suggested"], "sbx/example:1.10.0@" + DIGEST_NEW)
        self.assertEqual(result["newestRelease"], "1.10.0")
        self.assertTrue(result["changed"])

    def test_update_never_downgrades_a_newer_current_tag(self):
        self.patch_registry(["1.9.0", "1.10.0"])
        result = kits.update_one("sbx/example:1.10.0", False)
        self.assertEqual(result["suggested"], "sbx/example:1.10.0")
        self.assertFalse(result["changed"])

    def test_update_flags_major_version_change(self):
        self.patch_registry(["1.9.0", "2.0.0"])
        result = kits.update_one("sbx/example:1.9.0", False)
        self.assertEqual(result["suggested"], "sbx/example:2.0.0")
        self.assertIn("major version change", result["note"])

    def test_pin_keeps_the_written_release(self):
        self.patch_registry(["1.9.0", "1.10.0"])
        result = kits.pin_one("sbx/example:1.9.0")
        self.assertEqual(result["suggested"], "sbx/example:1.9.0@" + DIGEST_NEW)


class FailureReportingTests(unittest.TestCase):
    def run_main(self, *argv):
        out = io.StringIO()
        with mock.patch.object(sys, "argv", ["kits.py", *argv]), \
                contextlib.redirect_stdout(out), contextlib.redirect_stderr(io.StringIO()):
            code = kits.main()
        return code, out.getvalue()

    def test_one_failed_lookup_exits_nonzero_and_keeps_other_results(self):
        def fake_update(text, pin):
            if "missing" in text:
                raise kits.Fail(text + ": repository not found or private")
            return {"ref": text, "suggested": text}

        with mock.patch.object(kits, "update_one", side_effect=fake_update):
            code, out = self.run_main("update", "sbx/good:1.0.0", "sbx/missing")
        entries = json.loads(out)
        self.assertEqual(code, 1)
        self.assertEqual(entries[0], {"ref": "sbx/good:1.0.0", "suggested": "sbx/good:1.0.0"})
        self.assertIn("repository not found", entries[1]["error"])

    def test_search_network_failure_exits_nonzero_without_results(self):
        with mock.patch.object(kits, "search", side_effect=kits.Fail("connection refused")):
            code, out = self.run_main("search", "claude")
        self.assertEqual(code, 1)
        self.assertEqual(out, "")

    def test_local_sources_are_skipped_not_failed(self):
        code, out = self.run_main("update", "./kits/tool")
        self.assertEqual(code, 0)
        self.assertIn("skipped", json.loads(out)[0])


if __name__ == "__main__":
    unittest.main()

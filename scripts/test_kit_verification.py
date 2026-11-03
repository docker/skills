"""Exercise kit verification examples without Docker, credentials or network."""

import hashlib
import io
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tarfile
import tempfile
import unittest

ROOT = Path(__file__).resolve().parent.parent
SKILL = ROOT / "skills/docker-sandboxes-kits"
AUDIT = SKILL / "scripts/audit-layer-owners.py"
INDEX = "application/vnd.oci.image.index.v1+json"
MANIFEST = "application/vnd.oci.image.manifest.v1+json"
LAYER = "application/vnd.oci.image.layer.v1.tar"


def blocks(path, language):
    return re.findall(r"```" + language + r"\n(.*?)\n```", path.read_text(), re.S)


class OwnershipAuditTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        (self.root / "blobs/sha256").mkdir(parents=True)

    def blob(self, content, media, **extra):
        if isinstance(content, dict):
            content = json.dumps(content).encode()
        digest = hashlib.sha256(content).hexdigest()
        (self.root / "blobs/sha256" / digest).write_bytes(content)
        return {"digest": "sha256:" + digest, "mediaType": media, "size": len(content), **extra}

    def layer(self, owners=((0, 0), (1000, 1000)), gzip=False):
        data = io.BytesIO()
        with tarfile.open(fileobj=data, mode="w:gz" if gzip else "w") as archive:
            for number, (uid, gid) in enumerate(owners):
                entry = tarfile.TarInfo(f"item-{number}")
                entry.uid, entry.gid = uid, gid
                archive.addfile(entry)
        return self.blob(data.getvalue(), LAYER + ("+gzip" if gzip else ""))

    def layout(self, layers, nested=False):
        manifest = self.blob({"layers": layers, "config": {"digest": "not-a-layer"}}, MANIFEST)
        if nested:
            attestation = {"annotations": {"vnd.docker.reference.type": "attestation-manifest"}}
            manifest = self.blob({"manifests": [manifest, attestation]}, INDEX)
        manifest["annotations"] = {"org.opencontainers.image.ref.name": "0.0.0"}
        (self.root / "index.json").write_text(json.dumps({"manifests": [manifest]}))
        (self.root / "blobs/sha256/unreferenced").write_text("not a tar")

    def run_audit(self, tag="0.0.0"):
        return subprocess.run([sys.executable, str(AUDIT), str(self.root), tag], capture_output=True, text=True)

    def test_gzip_plain_layers_nested_index_and_config_exclusion(self):
        self.layout([self.layer(), self.layer(gzip=True)], nested=True)
        result = self.run_audit()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.split(), ["2", "0/0", "2", "1000/1000"])

    def test_foreign_owner_fails(self):
        self.layout([self.layer(owners=((501, 20),))])
        result = self.run_audit()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("501/20", result.stdout)
        self.assertIn("unexpected numeric owner", result.stderr)

    def test_unreadable_layers_never_print_partial_counts(self):
        for failure in ("missing", "corrupt", "digest", "compression", "truncated"):
            with self.subTest(failure=failure):
                good = self.layer()
                bad = self.layer(gzip=True)
                path = self.root / "blobs/sha256" / bad["digest"].split(":")[1]
                if failure == "missing":
                    path.unlink()
                elif failure == "digest":
                    path.write_bytes(b"changed")
                elif failure == "corrupt":
                    bad = self.blob(b"not a tar archive", LAYER)
                elif failure == "truncated":
                    bad = self.blob(path.read_bytes()[:20], LAYER + "+gzip")
                else:
                    bad = self.blob(b"unsupported", LAYER + "+zstd")
                self.layout([good, bad])
                result = self.run_audit()
                self.assertNotEqual(result.returncode, 0)
                self.assertEqual(result.stdout, "")
                self.assertIn("ownership audit failed", result.stderr)

    def test_truncated_regular_file_payload_fails(self):
        entry = tarfile.TarInfo("payload")
        entry.size = 4096
        bad = self.blob(entry.tobuf() + b"short payload", LAYER)
        self.layout([self.layer(), bad])
        result = self.run_audit()
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(result.stdout, "")
        self.assertIn("cannot read layer", result.stderr)

    def test_missing_tag_and_empty_manifest_fail(self):
        self.layout([])
        for tag in ("missing", "0.0.0"):
            result = self.run_audit(tag)
            self.assertNotEqual(result.returncode, 0)
            self.assertEqual(result.stdout, "")


class ShellExampleTests(unittest.TestCase):
    def test_version_check_requires_exact_literal_output_and_success(self):
        recipe = blocks(SKILL / "references/v3-recipes.md", "dockerfile")[0]
        check = recipe[recipe.index("reported=$(tool --version)"):recipe.index("# The runtime contract")]
        check = check.replace("\\\n", "\n").strip()
        for reported, code, valid in [("tool 1.2.3", 0, True), ("tool 1.2.30", 0, False),
                                      ("tool 1x2x3", 0, False), ("tool 1.2.3-beta", 0, False),
                                      ("tool 1.2.3", 1, False), ("", 0, False)]:
            with self.subTest(reported=reported, code=code):
                env = dict(os.environ, TOOL_VERSION="1.2.3", REPORTED=reported, CODE=str(code))
                result = subprocess.run(["sh", "-ec", 'tool() { printf "%s\\n" "$REPORTED"; return "$CODE"; };\n' + check], env=env)
                self.assertEqual(result.returncode == 0, valid)

    def test_build_sequence_keeps_parent_for_sbx(self):
        sequence = next(b for b in blocks(SKILL / "SKILL.md", "sh") if "# 1. validate" in b)
        sequence = sequence.replace("<kit>", "sample").replace("<workload>", "workload").replace("<version>", "0.0.0")
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "sample").mkdir()
            (root / "workload").mkdir()
            stub = '''docker() { test "$PWD" = "$BASE/sample"; }
kit_tck() { test "$PWD" = "$BASE"; }
sbx() { test "$PWD" = "$BASE"; if [ "$1" = kit ]; then test -d "$3"; else test -d "$2"; fi; }
'''
            result = subprocess.run(["sh", "-ec", stub + sequence.replace("kit-tck", "kit_tck") + '\ntest "$PWD" = "$BASE"'], cwd=root,
                                    env=dict(os.environ, BASE=str(root)), capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)

    def test_builder_cleanup_requires_successful_create(self):
        runbook = blocks(SKILL / "checks/verification.md", "bash")
        setup = runbook[0]
        cleanup = next(b for b in runbook if 'BUILDER_CREATED:-false' in b)
        for create, bootstrap, expected in [(0, 0, True), (1, 0, False), (0, 1, True)]:
            with self.subTest(create=create, bootstrap=bootstrap), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                (root / "assets").mkdir()
                (root / "assets/v3-mixin-egress.yaml").write_text("schemaVersion: '3'\n")
                log = root / "docker.log"
                stub = '''python3() { printf '%s\\n' 0123456789abcdef0123456789abcdef; }
mktemp() { mkdir "$BASE/work"; printf '%s\\n' "$BASE/work"; }
docker() {
  printf '%s\\n' "$*" >> "$LOG"
  case "$2" in create) return "$CREATE" ;; inspect) return "$BOOTSTRAP" ;; esac
}
sbx() { :; }
'''
                result = subprocess.run(["bash", "-c", stub + setup + "\n" + cleanup], cwd=root,
                                        env=dict(os.environ, BASE=str(root), LOG=str(log), CREATE=str(create), BOOTSTRAP=str(bootstrap)),
                                        capture_output=True, text=True)
                self.assertEqual(result.returncode, 0, result.stderr)
                calls = log.read_text()
                self.assertEqual("buildx rm " in calls, expected)
                self.assertNotIn("--bootstrap", next(line for line in calls.splitlines() if "buildx create" in line))
                self.assertEqual("buildx inspect" in calls, create == 0)
                self.assertFalse((root / "work").exists())

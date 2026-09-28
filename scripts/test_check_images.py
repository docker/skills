"""Offline tests for container-image extraction, PR selection, and registry verification."""

import io
import json
from pathlib import Path
import socket
import subprocess
import tempfile
import unittest
from unittest import mock

import check_images as checker
import image_inventory as inventory

DIGEST = "sha256:" + "a" * 64


class InventoryTests(unittest.TestCase):
    def test_dockerfile_stages_copy_syntax_and_templates(self):
        text = ("# syntax=docker/dockerfile:1\nFROM --platform=$BUILDPLATFORM golang:1.23 AS build\n"
                "FROM build AS compiled\nCOPY --from=build /app /app\n"
                "COPY --link --from=busybox:1 /bin/sh /sh\nFROM <base> AS template\n"
                "FROM scratch\nFROM gcr.io/distroless/static:nonroot\n")
        self.assertEqual([(o.line, o.image) for o in inventory.extract("skills/s/assets/Dockerfile", text)], [
            (1, "docker/dockerfile:1"), (2, "golang:1.23"), (5, "busybox:1"),
            (8, "gcr.io/distroless/static:nonroot")])

    def test_compose_quotes_fences_blockquotes_and_local_examples(self):
        text = ("image: redis:7\n```yaml\nservices:\n  db:\n    image: 'postgres:17' # stable\n"
                "    image: myapp:1.0\n    image: ${IMAGE}\n```\n"
                "> image: nginx:1.27\n> image: redis\n"
                "Read `image: redis:7` and use image: redis:7.\n")
        found = inventory.extract("evals/example.md", text)
        self.assertEqual([(x.line, x.image) for x in found], [(5, "postgres:17"), (9, "nginx:1.27"), (10, "redis")])
        self.assertEqual([x.image for x in inventory.extract("skills/s/assets/compose.yaml", "services:\n  db:\n    image: redis:7\n")], ["redis:7"])

    def test_bare_eval_images_and_non_pulled_names(self):
        path = "evals/docker-compose-patterns.md"
        content = (inventory.ROOT / path).read_text(encoding="utf-8")
        self.assertEqual([item.image for item in inventory.extract(path, content)
                          if item.image in {"postgres", "redis"}], ["postgres", "redis"])
        text = ("```dockerfile\nFROM scratch AS empty\nFROM golang AS build\n"
                "FROM build AS runtime\nCOPY --from=build /src /src\n"
                "FROM <base>\nFROM ${BASE}\n```\n"
                "```yaml\nimage: myapp\nimage: example/foo\nimage: ${IMAGE}\n"
                "image: localhost/app\nimage: redis\n```")
        self.assertEqual([item.image for item in inventory.extract(path, text)], ["golang", "redis"])

    def test_dockerfile_stage_alias_case_and_numeric_index(self):
        text = ("```dockerfile\nFROM golang:1.23 as Builder\nFROM builder AS Runtime\n"
                "COPY --from=BUILDER /src /src\nCOPY --from=0 /src /src\n"
                "from alpine:3.20 as Final\nFROM final\n```")
        self.assertEqual([item.image for item in inventory.extract("evals/example.md", text)],
                         ["golang:1.23", "alpine:3.20"])

    def test_scope_and_full_inventory(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for name in ("skills/s/SKILL.md", "skills/s/assets/compose.yaml", "evals/s.md", "evals/README.md", "skills/s/scripts/x.py"):
                path = root / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text("```dockerfile\nFROM node:22\n```\n")
            self.assertEqual(inventory.files(root), ["evals/s.md", "skills/s/SKILL.md", "skills/s/assets/compose.yaml"])
            self.assertEqual(len(inventory.occurrences(root)), 3)

    def test_pr_added_occurrences_and_head_content(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            def git(*args):
                return subprocess.run(["git", *args], cwd=root, check=True, capture_output=True, text=True).stdout.strip()
            git("init", "-q")
            git("config", "user.name", "Test")
            git("config", "user.email", "test@example.com")
            git("config", "commit.gpgsign", "false")
            file = root / "skills/s/SKILL.md"
            file.parent.mkdir(parents=True)
            file.write_text("```dockerfile\nFROM node:20\n```\n")
            git("add", ".")
            git("commit", "-qm", "base")
            base = git("rev-parse", "HEAD")
            file.write_text("New line\n```dockerfile\nFROM node:20\nFROM node:22\nFROM node:22\n```\n")
            git("add", ".")
            git("commit", "-qm", "change")
            file.write_text("Uncommitted change\n" + file.read_text())
            self.assertEqual([(o.line, o.image) for o in inventory.occurrences(root, base)], [
                (4, "node:22"), (5, "node:22")])
            with self.assertRaises(ValueError):
                inventory.occurrences(root, "invalid-base")


class NetworkTests(unittest.TestCase):
    def test_target_and_unsupported_hosts(self):
        self.assertEqual(checker.target("postgres"), ("registry-1.docker.io", "library/postgres", "latest"))
        self.assertEqual(checker.target("redis"), ("registry-1.docker.io", "library/redis", "latest"))
        self.assertEqual(checker.target("docker.io/team/app"), ("registry-1.docker.io", "team/app", "latest"))
        self.assertEqual(checker.target("gcr.io/distroless/static"), ("gcr.io", "distroless/static", "latest"))
        self.assertEqual(checker.target("node:22"), ("registry-1.docker.io", "library/node", "22"))
        self.assertEqual(checker.target("docker.io/team/app:1"), ("registry-1.docker.io", "team/app", "1"))
        self.assertEqual(checker.target("gcr.io/distroless/static:nonroot"), ("gcr.io", "distroless/static", "nonroot"))
        self.assertIsNone(checker.target("ghcr.io/team/app:1"))
        self.assertEqual(checker.verify("ghcr.io/team/app:1")[0], "notice")
        for challenge in ('Bearer realm="https://evil.example/token",scope="repository:library/node:pull"',
                          'Bearer realm="http://auth.docker.io/token",scope="repository:library/node:pull"',
                          'Bearer realm="https://auth.docker.io/token",scope="repository:other:pull"'):
            with self.subTest(challenge=challenge), self.assertRaises(checker.Uncertain):
                checker.bearer(challenge, "registry-1.docker.io", "library/node")
        self.assertEqual(checker.bearer('Bearer realm="https://auth.docker.io/token",service="registry.docker.io",scope="repository:library/node:pull"', "registry-1.docker.io", "library/node"),
                         ("auth.docker.io", "/token?service=registry.docker.io&scope=repository%3Alibrary%2Fnode%3Apull"))

    def test_bare_name_probes_implicit_latest(self):
        with mock.patch.object(checker, "request", return_value=(404, {}, b"")) as requests:
            self.assertEqual(checker.verify("postgres"), ("error", "manifest not found (HTTP 404)"))
        self.assertEqual(requests.call_args.args[:2],
                         ("registry-1.docker.io", "/v2/library/postgres/manifests/latest"))

    def test_dns_rejects_private_and_nat64(self):
        with mock.patch.object(checker.socket, "getaddrinfo", return_value=[
            (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("1.1.1.1", 443)),
            (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("127.0.0.1", 443))]):
            with self.assertRaises(checker.Uncertain):
                checker.public_addresses("gcr.io")
        with mock.patch.object(checker.socket, "getaddrinfo", return_value=[
            (socket.AF_INET6, socket.SOCK_STREAM, 6, "", ("64:ff9b::7f00:1", 443, 0, 0))]):
            with self.assertRaises(checker.Uncertain):
                checker.public_addresses("gcr.io")

    def test_pinned_connection_uses_vetted_address(self):
        address = [(socket.AF_INET, socket.SOCK_STREAM, 6, ("1.1.1.1", 443))]
        with mock.patch.object(checker.socket, "socket") as sock, mock.patch.object(checker.socket, "getaddrinfo", side_effect=AssertionError("rebind")):
            checker.PinnedHTTPS("gcr.io", address).connect_pinned(("gcr.io", 443), 8, None)
        sock.return_value.connect.assert_called_once_with(("1.1.1.1", 443))

    def test_auth_index_platforms_missing_and_uncertainty(self):
        index = {"mediaType": next(iter(checker.INDEX_TYPES)), "manifests": [
            {"platform": {"os": "linux", "architecture": arch}, "digest": DIGEST} for arch in ("amd64", "arm64")]}
        def response(host, path, token="", accept=checker.ACCEPT, method="GET"):
            if not token:
                return 401, {"www-authenticate": 'Bearer realm="https://auth.docker.io/token",service="registry.docker.io",scope="repository:library/node:pull"'}, b""
            if path.endswith("/22"):
                return 200, {"content-type": index["mediaType"]}, json.dumps(index).encode()
            return 200, {"content-type": next(iter(checker.MANIFEST_TYPES))}, b'{"config":{"digest":"sha256:' + b'a'*64 + b'"}}'
        def authenticated(host, path, token="", accept=checker.ACCEPT, method="GET"):
            if host == "auth.docker.io":
                return 200, {}, b'{"token":"anonymous"}'
            return response(host, path, token, accept, method)
        with mock.patch.object(checker, "request", side_effect=authenticated) as requests:
            self.assertEqual(checker.verify("node:22")[0], "ok")
            self.assertEqual(requests.call_count, 5)
            self.assertEqual([call.args[-1] for call in requests.call_args_list if len(call.args) == 5], ["GET", "GET", "HEAD", "HEAD"])
        index["manifests"].pop()
        with mock.patch.object(checker, "request", side_effect=authenticated):
            self.assertEqual(checker.verify("node:22"), ("error", "missing linux/arm64"))
        with mock.patch.object(checker, "request", return_value=(404, {}, b"")):
            self.assertEqual(checker.verify("node:missing")[0], "error")
        index["manifests"].append({"platform": {"os": "linux", "architecture": "arm64"}, "digest": DIGEST})
        def missing_child(host, path, token="", accept=checker.ACCEPT, method="GET"):
            if method == "HEAD":
                return 404, {}, b""
            return authenticated(host, path, token, accept, method)
        with mock.patch.object(checker, "request", side_effect=missing_child):
            self.assertEqual(checker.verify("node:22"), ("error", "manifest not found (HTTP 404)"))
        with mock.patch.object(checker, "request", return_value=(429, {}, b"")):
            self.assertEqual(checker.verify("node:22")[0], "warning")
        with mock.patch.object(checker, "request", side_effect=checker.Uncertain("timeout")):
            self.assertEqual(checker.verify("node:22")[0], "warning")

    def test_private_docker_hub_repository_after_anonymous_token(self):
        def reply(host, path, token="", accept=checker.ACCEPT, method="GET"):
            if host == "auth.docker.io":
                return 200, {}, b'{"token":"anonymous"}'
            if not token:
                return 401, {"www-authenticate": 'Bearer realm="https://auth.docker.io/token",service="registry.docker.io",scope="repository:library/postgress:pull"'}, b""
            return 401, {}, b""
        with mock.patch.object(checker, "request", side_effect=reply):
            self.assertEqual(checker.verify("postgress:17"),
                             ("error", "public manifest inaccessible after anonymous pull authorization (HTTP 401)"))
        with mock.patch.object(checker, "request", return_value=(401, {}, b"")):
            self.assertEqual(checker.verify("postgress:17")[0], "warning")

    def test_full_sweep_with_no_verified_results_alerts(self):
        item = inventory.Occurrence("skills/s/SKILL.md", 2, "node:22")
        with mock.patch("sys.stdout", new_callable=io.StringIO):
            self.assertTrue(checker.emit([item], {item.image: ("warning", "manifest HTTP 429")}, full_sweep=True))
            self.assertFalse(checker.emit([item], {item.image: ("warning", "manifest HTTP 429")}))
            self.assertFalse(checker.emit([item], {item.image: ("ok", "available")}, full_sweep=True))
            self.assertFalse(checker.emit([], {}, full_sweep=True))

    def test_child_unavailable_status_is_indeterminate(self):
        index_media = next(iter(checker.INDEX_TYPES))
        index = {"mediaType": index_media, "manifests": [
            {"platform": {"os": "linux", "architecture": arch}, "digest": DIGEST} for arch in ("amd64", "arm64")]}
        def reply(host, path, token="", accept=checker.ACCEPT, method="GET"):
            if method == "HEAD":
                return status, {}, b""
            return 200, {"content-type": index_media}, json.dumps(index).encode()
        for status in (429, 500):
            with self.subTest(status=status), mock.patch.object(checker, "request", side_effect=reply):
                self.assertEqual(checker.verify("node:22"), ("warning", f"manifest HTTP {status}"))

    def test_single_platform_manifest_and_output(self):
        media = next(iter(checker.MANIFEST_TYPES))
        def reply(host, path, token="", accept=checker.ACCEPT, method="GET"):
            if "/blobs/" in path:
                return 307, {"location": "https://redirect.example.invalid/blob"}, b""
            return 200, {"content-type": media}, json.dumps({"mediaType": media, "config": {"digest": DIGEST}}).encode()
        with mock.patch.object(checker, "request", side_effect=reply) as requests:
            self.assertEqual(checker.verify("node:22"), ("error", "single-platform manifest cannot provide both linux/amd64 and linux/arm64"))
            self.assertEqual(requests.call_count, 1)
        with mock.patch.object(checker, "request", return_value=(200, {"content-type": media},
                                                                         json.dumps({"mediaType": media, "config": "bad"}).encode())):
            self.assertEqual(checker.verify("node:22")[0], "warning")
        index_media = next(iter(checker.INDEX_TYPES))
        bad_index = {"mediaType": index_media, "manifests": [
            {"platform": {"os": "linux", "architecture": "amd64"}, "digest": DIGEST},
            {"platform": {"os": "linux", "architecture": "arm64"}, "digest": DIGEST}, "bad"]}
        with mock.patch.object(checker, "request", return_value=(200, {"content-type": index_media}, json.dumps(bad_index).encode())):
            self.assertEqual(checker.verify("node:22")[0], "warning")
        items = [inventory.Occurrence("skills/s/SKILL.md", 2, "node:22")] * 2
        with mock.patch.dict("os.environ", {"GITHUB_ACTIONS": "true"}), mock.patch("sys.stdout", new_callable=io.StringIO) as output:
            self.assertTrue(checker.emit(items, {"node:22": ("error", "missing linux/arm64")}))
            self.assertIn("2 occurrences, 1 unique references", output.getvalue())
            self.assertIn("::error file=skills/s/SKILL.md,line=2::", output.getvalue())


if __name__ == "__main__":
    unittest.main()

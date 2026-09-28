"""Offline tests for the opt-in external HTTPS checker."""

import io
import http.client
import socket
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest import mock
from email.message import Message
from urllib import error, request

import check_external_links as links


class ExtractionTests(unittest.TestCase):
    def test_prose_reference_bare_and_metadata_with_line_numbers(self):
        text = ('[Docker](https://docs.docker.com/ai/skills/install/#cursor)\n'
                '[d]: <https://docs.docker.com/ai/skills/install/#codex>\n'
                'See https://docs.docker.com/ai/skills/install/.\n'
                '**[Docs](https://docs.docker.com/build/)**\n'
                '`https://invalid.example.net/inline`\n'
                '```yaml\nhttps://invalid.example.net/fenced\n```\n'
                '![icon](https://cdn.docker.com/logo.png)\n'
                'https://api.example.com/foo\n')
        found = links.extract("README.md", text)
        self.assertEqual([(x.line, x.url) for x in found], [
            (1, "https://docs.docker.com/ai/skills/install/#cursor"),
            (2, "https://docs.docker.com/ai/skills/install/#codex"),
            (3, "https://docs.docker.com/ai/skills/install/"),
            (4, "https://docs.docker.com/build/")])
        self.assertEqual(links.extract("catalog.yaml", "docs: https://docs.docker.com/ai/skills/install/#cursor\n")[0].line, 1)
        self.assertEqual(links.extract(".claude-plugin/plugin.json", '{"homepage":"https://docker.com"}')[0].url, "https://docker.com")
        self.assertEqual(links.extract(".github/ISSUE_TEMPLATE/config.yml", "url: https://dockr.ly/slack\n"), [])

    def test_scope_does_not_include_example_assets_and_fixtures(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for path in ("README.md", "catalog.yaml", "skills/s/SKILL.md", "skills/s/assets/example.md", "skills/s/checks/a.md", "evals/s.md", ".github/plugin/plugin.json", ".github/ISSUE_TEMPLATE/config.yml", "CODE_OF_CONDUCT.md", "scripts/example.md"):
                target = root / path
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text("https://docs.docker.com/test")
            self.assertEqual(links.files(root), [".github/ISSUE_TEMPLATE/config.yml", ".github/plugin/plugin.json", "CODE_OF_CONDUCT.md", "README.md", "catalog.yaml", "evals/s.md", "skills/s/SKILL.md"])

    def test_pr_delta_added_modified_and_deleted_urls(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            def git(*args):
                subprocess.run(["git", *args], cwd=root, check=True, capture_output=True)
            git("init", "-q")
            git("config", "user.name", "Test")
            git("config", "user.email", "test@example.com")
            git("config", "commit.gpgsign", "false")
            (root / "README.md").write_text("https://docker.com/unchanged\nhttps://docker.com/removed\n")
            (root / "catalog.yaml").write_text("docs: https://docker.com/old\n")
            git("add", ".")
            git("commit", "-qm", "base")
            base = subprocess.run(["git", "rev-parse", "HEAD"], cwd=root, capture_output=True, check=True, text=True).stdout.strip()
            (root / "README.md").write_text("https://docker.com/unchanged\nhttps://docker.com/new\n")
            (root / "catalog.yaml").write_text("docs: https://docker.com/replacement\n")
            (root / "skills").mkdir()
            (root / "skills" / "added.md").write_text("https://docker.com/added\n")
            git("add", ".")
            git("commit", "-qm", "change")
            self.assertEqual([(item.path, item.line, item.url) for item in links.occurrences(root, base)], [
                ("README.md", 2, "https://docker.com/new"),
                ("catalog.yaml", 1, "https://docker.com/replacement"),
                ("skills/added.md", 1, "https://docker.com/added"),
            ])
            with self.assertRaises(ValueError):
                links.occurrences(root, "unknown-ref")

    def test_pr_delta_unicode_line_separator_does_not_shift_git_lines(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            def git(*args):
                return subprocess.run(["git", *args], cwd=root, check=True, capture_output=True, text=True).stdout.strip()
            git("init", "-q")
            git("config", "user.name", "Test")
            git("config", "user.email", "test@example.com")
            (root / "README.md").write_text("intro\nhttps://docker.com/old\n")
            git("add", "README.md")
            git("-c", "commit.gpgsign=false", "commit", "-qm", "base")
            base = git("rev-parse", "HEAD")
            (root / "README.md").write_text(
                "intro\u2028x\nhttps://docker.com/old\nhttps://docker.com/added\n")
            git("add", "README.md")
            git("-c", "commit.gpgsign=false", "commit", "-qm", "change")
            self.assertEqual([(item.line, item.url) for item in links.occurrences(root, base)], [
                (3, "https://docker.com/added"),
            ])

    def test_pr_delta_duplicates_shifts_and_markdown_code(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            def git(*args):
                return subprocess.run(["git", *args], cwd=root, check=True, capture_output=True, text=True).stdout.strip()
            git("init", "-q")
            git("config", "user.name", "Test")
            git("config", "user.email", "test@example.com")
            (root / "README.md").write_text("https://docker.com/repeated\nhttps://docker.com/stays\n```\nold\n```\n")
            git("add", "README.md")
            git("-c", "commit.gpgsign=false", "commit", "-qm", "base")
            base = git("rev-parse", "HEAD")
            (root / "README.md").write_text(
                "A new first line\nhttps://docker.com/repeated\nhttps://docker.com/stays\n"
                "https://docker.com/repeated\nhttps://docker.com/repeated\n"
                "```\nhttps://docker.com/inside-code\n```\nhttps://docker.com/new\n")
            git("add", "README.md")
            git("-c", "commit.gpgsign=false", "commit", "-qm", "change")
            # The uncommitted file is not the PR head and must not shift patch line numbers.
            (root / "README.md").write_text("uncommitted\n" + (root / "README.md").read_text())
            self.assertEqual([(item.line, item.url) for item in links.occurrences(root, base)], [
                (4, "https://docker.com/repeated"), (5, "https://docker.com/repeated"),
                (9, "https://docker.com/new"),
            ])


class FakeResponse:
    def __init__(self, url, body=b"<html><main><h2 id='exists'>hi</h2></main></html>", content_type="text/html"):
        self.url = url
        self.body = io.BytesIO(body)
        self.headers = {"Content-Type": content_type}

    def geturl(self):
        return self.url

    def read(self, limit):
        return self.body.read(limit)

    def __enter__(self):
        return self

    def __exit__(self, *_):
        pass


def http_error(url, code, location=None):
    headers = Message()
    if location:
        headers["Location"] = location
    return error.HTTPError(url, code, "error", headers, io.BytesIO())


class NetworkTests(unittest.TestCase):
    def setUp(self):
        self.real_public_https = links.public_https
        patcher = mock.patch.object(links, "public_https", return_value=((socket.AF_INET, socket.SOCK_STREAM, 6, ("1.1.1.1", 443)),))
        self.mock_public = patcher.start()
        self.addCleanup(patcher.stop)

    def test_http_errors_and_redirects(self):
        for code, level in ((404, "error"), (410, "error"), (401, "warning"), (403, "warning"), (429, "warning"), (503, "warning")):
            with self.subTest(code=code), mock.patch.object(links, "open_pinned", side_effect=http_error("https://docker.com/a", code)):
                self.assertEqual(links.fetch("https://docker.com/a").level, level)
        with mock.patch.object(links, "open_pinned", side_effect=[
            http_error("https://docker.com/a", 301, "/b"), FakeResponse("https://docker.com/b")]):
            result = links.fetch("https://docker.com/a")
            self.assertEqual((result.level, result.final_url), ("notice", "https://docker.com/b"))
        with mock.patch.object(links, "public_https", side_effect=[((socket.AF_INET, socket.SOCK_STREAM, 6, ("1.1.1.1", 443)),), None]), mock.patch.object(links, "open_pinned", side_effect=http_error("https://docker.com/a", 302, "http://localhost/")):
            self.assertEqual(links.fetch("https://docker.com/a").level, "warning")

    def test_anchor_evidence_and_uncertain_anchors(self):
        for url, level in (("https://docs.docker.com/foo/#exists", "ok"),
                           ("https://docs.docker.com/foo/#missing", "error"),
                           ("https://elsewhere.com/foo/#missing", "warning")):
            with self.subTest(url=url), mock.patch.object(links, "open_pinned", return_value=FakeResponse(url)):
                self.assertEqual(links.fetch(url).level, level)
        with mock.patch.object(links, "open_pinned", return_value=FakeResponse("https://docs.docker.com/foo/#missing", b"x" * (links.MAX_BYTES + 1))):
            self.assertEqual(links.fetch("https://docs.docker.com/foo/#missing").level, "warning")
        with mock.patch.object(links, "open_pinned", return_value=FakeResponse("https://docs.docker.com/foo/#description", b'<html><meta name="description"></html>')):
            self.assertEqual(links.fetch("https://docs.docker.com/foo/#description").level, "error")

    @mock.patch.object(links.time, "sleep")
    def test_retry_and_network_errors(self, sleep):
        with mock.patch.object(links, "fetch", side_effect=[links.Result("warning", "HTTP 503"), links.Result("error", "HTTP 404")]) as fetch:
            self.assertEqual(links.check("https://docker.com/a").level, "error")
            self.assertEqual(fetch.call_count, 2)
        with mock.patch.object(links, "open_pinned", side_effect=error.URLError("timeout")):
            self.assertEqual(links.fetch("https://docker.com/a").level, "warning")

    def test_protocol_and_body_read_timeouts_warn_without_hiding_other_errors(self):
        with mock.patch.object(links, "open_pinned", side_effect=http.client.BadStatusLine("bad")):
            self.assertEqual(links.fetch("https://docker.com/a").level, "warning")
        url = "https://docs.docker.com/guide/#topic"
        response = FakeResponse(url)
        response.read = mock.Mock(side_effect=socket.timeout("timed out"))
        with mock.patch.object(links, "open_pinned", return_value=response):
            self.assertIn("network error", links.fetch(url).message)
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "README.md").write_text(url + "\nhttps://docker.com/missing\n")
            def fake_check(current):
                if current == url:
                    return links.Result("warning", "network error: timed out")
                return links.Result("error", "HTTP 404")
            with mock.patch.object(links, "check", side_effect=fake_check), mock.patch("sys.stdout", new_callable=io.StringIO) as output:
                self.assertEqual(links.main(["--root", str(root)]), 1)
            self.assertIn("1 error, 1 warning", output.getvalue())

    def test_public_https_rejects_private_targets_and_nondefault_ports(self):
        self.mock_public.side_effect = self.real_public_https
        self.assertIsNone(links.public_https("http://docker.com/foo"))
        self.assertIsNone(links.public_https("https://user:password@docker.com/foo"))
        self.assertIsNone(links.public_https("https://docker.com:8443/foo"))
        with mock.patch.object(links.socket, "getaddrinfo", return_value=[(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("127.0.0.1", 443))]):
            self.assertIsNone(links.public_https("https://private.example/foo"))
        with mock.patch.object(links.socket, "getaddrinfo", return_value=[(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("1.1.1.1", 443))]):
            self.assertEqual(links.public_https("https://public.example/foo")[0][3], ("1.1.1.1", 443))
        with mock.patch.object(links.socket, "getaddrinfo", return_value=[
            (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("1.1.1.1", 443)),
            (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("127.0.0.1", 443))]):
            self.assertIsNone(links.public_https("https://mixed.example/foo"))
        with mock.patch.object(links.socket, "getaddrinfo", return_value=[
            (socket.AF_INET6, socket.SOCK_STREAM, 6, "", ("64:ff9b::7f00:1", 443, 0, 0))]):
            self.assertIsNone(links.public_https("https://nat64.example/foo"))

    def test_pinned_socket_preserves_hostname_and_blocks_rebinding(self):
        address = (socket.AF_INET, socket.SOCK_STREAM, 6, ("1.1.1.1", 443))
        sock = mock.Mock()
        wrapped = mock.Mock()
        context = mock.Mock()
        context.wrap_socket.return_value = wrapped
        with mock.patch.object(links.socket, "socket", return_value=sock), \
             mock.patch.object(links.socket, "getaddrinfo", side_effect=AssertionError("second DNS lookup")):
            connection = links._PinnedConnection("public.example", (address,), context=context)
            connection.connect()
        sock.connect.assert_called_once_with(("1.1.1.1", 443))
        context.wrap_socket.assert_called_once_with(sock, server_hostname="public.example")
        self.assertEqual(connection.host, "public.example")
        req = request.Request("https://public.example/path")
        with mock.patch.object(links.request, "build_opener") as build:
            links.open_pinned(req, (address,))
        handler = next(arg for arg in build.call_args.args if isinstance(arg, links._PinnedHTTPSHandler))
        with mock.patch.object(handler, "do_open", return_value=None) as do_open:
            handler.https_open(req)
        conn = do_open.call_args.args[0]("public.example", context=context)
        self.assertEqual((conn.host, conn._addresses), ("public.example", (address,)))
        with mock.patch.object(handler, "do_open") as do_open:
            req.set_proxy("proxy.example:3128", "https")
            with self.assertRaisesRegex(ValueError, "proxy"):
                handler.https_open(req)
            do_open.assert_not_called()

    def test_pinned_connection_falls_back_only_to_other_vetted_addresses(self):
        first = (socket.AF_INET, socket.SOCK_STREAM, 6, ("1.1.1.1", 443))
        second = (socket.AF_INET, socket.SOCK_STREAM, 6, ("8.8.8.8", 443))
        failed, successful = mock.Mock(), mock.Mock()
        failed.connect.side_effect = OSError("first address unavailable")
        with mock.patch.object(links.socket, "socket", side_effect=[failed, successful]), \
             mock.patch.object(links.socket, "getaddrinfo", side_effect=AssertionError("second DNS lookup")):
            connection = links._PinnedConnection("public.example", (first, second), context=mock.Mock())
            result = connection._connect_pinned(("public.example", 443), links.TIMEOUT, None)
        self.assertIs(result, successful)
        failed.close.assert_called_once()
        successful.connect.assert_called_once_with(("8.8.8.8", 443))

    def test_redirect_repins_and_rejects_nonpublic_destination(self):
        address = (socket.AF_INET, socket.SOCK_STREAM, 6, ("1.1.1.1", 443))
        other = (socket.AF_INET, socket.SOCK_STREAM, 6, ("8.8.8.8", 443))
        with mock.patch.object(links, "public_https", side_effect=[(address,), (other,)]), \
             mock.patch.object(links, "open_pinned", side_effect=[
                 http_error("https://public.example/a", 302, "https://next.example/b"),
                 FakeResponse("https://next.example/b")]) as open_pinned:
            result = links.fetch("https://public.example/a")
        self.assertEqual(result.level, "notice")
        self.assertEqual([call.args[1] for call in open_pinned.call_args_list], [(address,), (other,)])
        with mock.patch.object(links, "public_https", side_effect=[(address,), None]), \
             mock.patch.object(links, "open_pinned", side_effect=http_error(
                 "https://public.example/a", 302, "https://private.example/b")) as open_pinned:
            self.assertEqual(links.fetch("https://public.example/a").level, "warning")
            self.assertEqual(open_pinned.call_count, 1)

    def test_deduplicated_fetch_annotations_summary_and_failure_exit(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "README.md").write_text("https://docker.com/missing\nhttps://docker.com/missing\n")
            summary = root / "summary"
            with mock.patch.object(links, "check", return_value=links.Result("error", "HTTP 404")) as check, \
                 mock.patch.dict("os.environ", {"GITHUB_ACTIONS": "true", "GITHUB_STEP_SUMMARY": str(summary)}), \
                 mock.patch("sys.stdout", new_callable=io.StringIO) as output:
                self.assertEqual(links.main(["--root", str(root)]), 1)
            self.assertEqual(check.call_count, 1)
            self.assertIn("::error file=README.md,line=1::", output.getvalue())
            self.assertIn("2 occurrences, 1 unique URLs", summary.read_text())
            with mock.patch.object(links, "check", return_value=links.Result("warning", "HTTP 403")), mock.patch("sys.stdout", new_callable=io.StringIO):
                self.assertEqual(links.main(["--root", str(root)]), 0)


if __name__ == "__main__":
    unittest.main()

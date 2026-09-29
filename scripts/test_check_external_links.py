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
from prepare_release import rotate_changelog


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


class ReleaseLinkTests(unittest.TestCase):
    ORIGIN = "https://github.com/docker/skills"

    def test_expected_urls_are_exactly_the_head_release_links(self):
        self.assertEqual(links.expected_release_urls("1.2.3", "1.3.0"), {
            f"{self.ORIGIN}/compare/v1.3.0...HEAD",
            f"{self.ORIGIN}/releases/tag/v1.3.0",
        })
        self.assertEqual(links.expected_release_urls("1.2.3", "1.2.3"), set())

    def test_downgrade_release_links_remain_errors(self):
        release = f"{self.ORIGIN}/releases/tag/v0.2.0"
        self.assertEqual(links.expected_release_urls("0.3.0", "0.2.0"), set())
        # Version components must be ordered numerically, not as strings.
        self.assertEqual(links.expected_release_urls("0.10.0", "0.9.0"), set())
        with mock.patch("sys.stdout", new_callable=io.StringIO) as output:
            self.assertTrue(links.emit(
                [links.Occurrence("CHANGELOG.md", 1, release)],
                {release: links.Result("error", "HTTP 404", release)},
                expected=links.expected_release_urls("0.3.0", "0.2.0"),
            ))
        self.assertIn("1 error, 0 warning, 0 notice", output.getvalue())

    def test_pr_release_rotation_fetches_and_reports_notice_per_occurrence(self):
        old = ("## [Unreleased]\n\n### Fixed\n\n- A link check.\n\n"
               "## [1.2.3] - 2026-01-02\n\n### Added\n\n- First release.\n\n"
               f"[Unreleased]: {self.ORIGIN}/compare/v1.2.3...HEAD\n"
               f"[1.2.3]: {self.ORIGIN}/releases/tag/v1.2.3\n")
        rotated = rotate_changelog(old, "1.2.3", "1.3.0", "2026-09-29")
        expected = links.expected_release_urls("1.2.3", "1.3.0")
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)

            def git(*args):
                return subprocess.run(["git", *args], cwd=root, check=True, capture_output=True, text=True).stdout.strip()

            git("init", "-q")
            git("config", "user.name", "Test")
            git("config", "user.email", "test@example.com")
            (root / "catalog.yaml").write_text("schema: v1\nversion: 1.2.3\n")
            (root / "CHANGELOG.md").write_text(old)
            git("add", ".")
            git("-c", "commit.gpgsign=false", "commit", "-qm", "base")
            base = git("rev-parse", "HEAD")
            (root / "catalog.yaml").write_text("schema: v1\nversion: 1.3.0\n")
            (root / "CHANGELOG.md").write_text(rotated)
            # An added repeat in a different file must remain an error even after URL deduplication.
            (root / "README.md").write_text(f"{self.ORIGIN}/releases/tag/v1.3.0\n")
            git("add", ".")
            git("-c", "commit.gpgsign=false", "commit", "-qm", "release")
            (root / "CHANGELOG.md").write_text("uncommitted text\n")
            found = links.occurrences(root, base)
            self.assertEqual({item.url for item in found if item.path == "CHANGELOG.md"}, expected)
            self.assertEqual(links._expected_pr_release_urls(root, base), expected)
            summary = root / "summary"
            def missing(current):
                return links.Result("error", "HTTP 404", current)

            with mock.patch.object(links, "check", side_effect=missing) as check, \
                 mock.patch.dict("os.environ", {"GITHUB_ACTIONS": "true", "GITHUB_STEP_SUMMARY": str(summary)}), \
                 mock.patch("sys.stdout", new_callable=io.StringIO) as output:
                self.assertEqual(links.main(["--root", str(root), "--base", base]), 1)
            self.assertEqual(check.call_count, 2)
            self.assertIn("2 notice", output.getvalue())
            self.assertIn("1 error", output.getvalue())
            self.assertIn("::notice file=CHANGELOG.md", output.getvalue())
            self.assertIn("::error file=README.md", output.getvalue())
            self.assertIn("**notice** `CHANGELOG.md:", summary.read_text())
            self.assertIn("**error** `README.md:", summary.read_text())

    def test_only_exact_unredirected_404_in_changelog_is_notice(self):
        expected = links.expected_release_urls("1.2.3", "1.3.0")
        release = f"{self.ORIGIN}/releases/tag/v1.3.0"
        near = [f"{release}/", f"{release}?query=1", f"{self.ORIGIN}/releases/tag/v1.3.1"]
        found = [links.Occurrence("CHANGELOG.md", 1, release),
                 links.Occurrence("CHANGELOG.md", 2, release),
                 links.Occurrence("README.md", 3, release)]
        found.extend(links.Occurrence("CHANGELOG.md", index + 4, url) for index, url in enumerate(near))
        results = {url: links.Result("error", "HTTP 404", url) for url in [release, *near]}
        with mock.patch("sys.stdout", new_callable=io.StringIO) as output:
            self.assertTrue(links.emit(found, results, expected=expected))
        self.assertIn("4 error, 0 warning, 2 notice", output.getvalue())
        with mock.patch("sys.stdout", new_callable=io.StringIO) as output:
            self.assertFalse(links.emit(found[:2], {release: results[release]}, expected=expected))
            self.assertIn("2 notice", output.getvalue())
        for result in (links.Result("error", "HTTP 410", release),
                       links.Result("error", "HTTP 404", release, True),
                       links.Result("error", "HTTP 404", release + "/destination", True),
                       links.Result("warning", "network error: timeout", release)):
            with self.subTest(result=result), mock.patch("sys.stdout", new_callable=io.StringIO) as output:
                failed = links.emit([found[0]], {release: result}, expected=expected)
                self.assertEqual(failed, result.level == "error")
                self.assertIn(f"1 {result.level}", output.getvalue())
        with mock.patch("sys.stdout", new_callable=io.StringIO) as output:
            self.assertTrue(links.emit([found[0]], {release: results[release]}))
            self.assertIn("1 error", output.getvalue())

    def test_redirect_to_expected_url_ending_in_404_remains_error(self):
        release = f"{self.ORIGIN}/releases/tag/v1.3.0"
        with mock.patch.object(links, "public_https", return_value=((socket.AF_INET, socket.SOCK_STREAM, 6, ("1.1.1.1", 443)),)), \
             mock.patch.object(links, "open_pinned", side_effect=[
                 http_error(release, 302, "/releases/tag/v1.3.0"), http_error(release, 404)]):
            result = links.fetch(release)
        self.assertTrue(result.redirected)
        with mock.patch("sys.stdout", new_callable=io.StringIO):
            self.assertTrue(links.emit([links.Occurrence("CHANGELOG.md", 1, release)],
                                       {release: result}, expected={release}))

    def test_pr_catalog_version_must_be_present_and_strict_at_both_revisions(self):
        for invalid in ("schema: v1\n", "version: 1.2.3\nversion: 1.2.3\n",
                        "version: 01.2.3\n", "version: 1.2\n", "version: v1.2.3\n",
                        "version: 1.2.3-beta\n"):
            with self.subTest(invalid=invalid):
                with self.assertRaisesRegex(ValueError, "catalog.yaml"):
                    links._catalog_version(invalid)
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)

            def git(*args):
                return subprocess.run(["git", *args], cwd=root, check=True, capture_output=True, text=True).stdout.strip()

            git("init", "-q")
            git("config", "user.name", "Test")
            git("config", "user.email", "test@example.com")
            (root / "catalog.yaml").write_text("version: 1.2.3\n")
            git("add", ".")
            git("-c", "commit.gpgsign=false", "commit", "-qm", "base")
            base = git("rev-parse", "HEAD")
            (root / "catalog.yaml").write_text("version: invalid\n")
            git("add", ".")
            git("-c", "commit.gpgsign=false", "commit", "-qm", "head")
            with mock.patch.object(links, "check") as check, mock.patch("sys.stderr", new_callable=io.StringIO) as err:
                self.assertEqual(links.main(["--root", str(root), "--base", base]), 2)
                self.assertIn("catalog.yaml", err.getvalue())
                check.assert_not_called()
            self.assertEqual(links._catalog_version("# version: no\nversion: '1.2.3' # comment\n"), "1.2.3")
            with mock.patch.object(links, "_git", side_effect=[b"base\n", b"version: invalid\n"]):
                with self.assertRaisesRegex(ValueError, "catalog.yaml"):
                    links._expected_pr_release_urls(root, base)

    def test_unchanged_version_pr_and_full_sweep_keep_404_errors(self):
        release = f"{self.ORIGIN}/releases/tag/v1.2.3"
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)

            def git(*args):
                return subprocess.run(["git", *args], cwd=root, check=True, capture_output=True, text=True).stdout.strip()

            git("init", "-q")
            git("config", "user.name", "Test")
            git("config", "user.email", "test@example.com")
            (root / "catalog.yaml").write_text("version: 1.2.3\n")
            (root / "CHANGELOG.md").write_text("# Changelog\n")
            git("add", ".")
            git("-c", "commit.gpgsign=false", "commit", "-qm", "base")
            base = git("rev-parse", "HEAD")
            (root / "CHANGELOG.md").write_text(release + "\n")
            git("add", ".")
            git("-c", "commit.gpgsign=false", "commit", "-qm", "head")
            self.assertEqual(links._expected_pr_release_urls(root, base), set())
            with mock.patch.object(links, "check", return_value=links.Result("error", "HTTP 404", release)), \
                 mock.patch("sys.stdout", new_callable=io.StringIO):
                self.assertEqual(links.main(["--root", str(root), "--base", base]), 1)
                self.assertEqual(links.main(["--root", str(root)]), 1)


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

#!/usr/bin/env python3
"""Check public HTTPS links in documentation and distribution metadata."""

from __future__ import annotations

import argparse
import concurrent.futures
import html.parser
import http.client
import ipaddress
import os
from pathlib import Path
import re
import socket
import subprocess
import sys
import time
from dataclasses import dataclass
from urllib import error, parse, request

from check_links import DOCUMENTATION_GLOBS, ROOT_DOCUMENTS, FENCED_CODE_RE

REPO_ROOT = Path(__file__).resolve().parent.parent
CATALOG_VERSION_RE = re.compile(
    r"^version[ \t]*:[ \t]*(?P<quote>['\"]?)(?P<version>(?:0|[1-9][0-9]*)\.(?:0|[1-9][0-9]*)\.(?:0|[1-9][0-9]*))(?P=quote)[ \t]*(?:#.*)?$"
)
METADATA = ("catalog.yaml", "skills.sh.json", "gemini-extension.json", ".github/ISSUE_TEMPLATE/config.yml")
DOCUMENTS = (*ROOT_DOCUMENTS, "CODE_OF_CONDUCT.md")
MANIFESTS = (".claude-plugin/*.json", ".cursor-plugin/*.json", ".codex-plugin/*.json", ".agents/plugins/*.json", ".github/plugin/*.json")
URL_RE = re.compile(r"https://[^\s<>\"'`]+", re.IGNORECASE)
INLINE_CODE_RE = re.compile(r"(`+)(.*?)\1")
IMAGE_RE = re.compile(r"!\[[^\]\n]*\]\([^\n]*?\)")
PLACEHOLDER_RE = re.compile(r"(?:\{[^}]+\}|\$\{|<[^>]+>|\b(?:example\.(?:com|org|net)|localhost)\b)", re.IGNORECASE)
# The Slack shortlink is an intentional invitation; its redirect can depend on browser/session state.
IGNORED = {"https://dockr.ly/slack": "session-dependent Slack invitation shortlink"}
MAX_BYTES = 2 * 1024 * 1024
MAX_REDIRECTS = 5
RETRIES = 2
TIMEOUT = 8
WORKERS = 6
OVERALL_TIMEOUT = 600


@dataclass(frozen=True)
class Occurrence:
    path: str
    line: int
    url: str


@dataclass(frozen=True)
class Result:
    level: str  # error, warning, notice, ok
    message: str
    final_url: str = ""
    redirected: bool = False


def eligible(path: str) -> bool:
    if path in DOCUMENTS or path in METADATA:
        return True
    parts = Path(path).parts
    if not parts or any(part in {"assets", "checks", "scripts", "fixtures"} for part in parts):
        return False
    if path.startswith(("skills/", "evals/")) and path.endswith(".md"):
        return True
    return any(Path(path).match(glob) for glob in MANIFESTS)


def files(root: Path) -> list[str]:
    paths = {name for name in (*DOCUMENTS, *METADATA) if (root / name).is_file()}
    for pattern in (*DOCUMENTATION_GLOBS, *MANIFESTS):
        paths.update(p.relative_to(root).as_posix() for p in root.glob(pattern) if p.is_file() and not p.is_symlink())
    return sorted(p for p in paths if eligible(p) and not (root / p).is_symlink())


def _prose_lines(content: str) -> list[str]:
    lines = []
    fence = None
    for line in content.split("\n"):
        marker = FENCED_CODE_RE.match(line)
        if marker:
            candidate = marker.group(1)[0]
            fence = candidate if fence is None else None if candidate == fence else fence
            lines.append("")
        else:
            lines.append("" if fence is not None else line)
    return lines


def extract(path: str, content: str) -> list[Occurrence]:
    lines = _prose_lines(content) if path.endswith(".md") else content.split("\n")
    found = []
    for line_no, line in enumerate(lines, 1):
        if path.endswith(".md"):
            for pattern in (INLINE_CODE_RE, IMAGE_RE):
                line = pattern.sub(lambda match: " " * len(match.group()), line)
        for match in URL_RE.finditer(line):
            url = match.group().rstrip(".,;:!?*_")
            while url.endswith(")") and url.count("(") < url.count(")"):
                url = url[:-1]
            while url.endswith("]") and url.count("[") < url.count("]"):
                url = url[:-1]
            if PLACEHOLDER_RE.search(url) or url in IGNORED:
                continue
            parsed = parse.urlsplit(url)
            if parsed.scheme.lower() == "https" and parsed.hostname and not any(c in url for c in "{}<>"):
                found.append(Occurrence(path, line_no, url))
    return found


def _git(root: Path, *args: str) -> bytes:
    command = ["git", "-c", f"safe.directory={root.resolve()}", *args]
    result = subprocess.run(command, cwd=root, capture_output=True, check=False)
    if result.returncode:
        raise ValueError(f"{' '.join(command[2:])}: {result.stderr.decode(errors='replace').strip()}")
    return result.stdout


def _added_lines(root: Path, ancestor: str, path: str) -> set[int]:
    patch = _git(root, "diff", "--no-ext-diff", "--no-color", "--unified=0", "--no-renames",
                 f"{ancestor}...HEAD", "--", path).decode("utf-8")
    added: set[int] = set()
    line: int | None = None
    for record in patch.split("\n"):
        if record.startswith("@@ "):
            match = re.match(r"@@ -\d+(?:,\d+)? \+(\d+)(?:,\d+)? @@", record)
            if not match:
                raise ValueError(f"invalid diff hunk in {path}: {record}")
            line = int(match.group(1))
        elif line is not None:
            if record.startswith("+"):
                added.add(line)
                line += 1
            elif record.startswith(" "):
                line += 1
    return added


def occurrences(root: Path, base: str | None = None) -> list[Occurrence]:
    if base is None:
        paths = files(root)
        ancestor = None
    else:
        ancestor = _git(root, "merge-base", base, "HEAD").decode().strip()
        changes = _git(root, "diff", "--name-status", "--no-renames", "-z", f"{ancestor}...HEAD").split(b"\0")
        paths = []
        for status, raw_path in zip(changes[0::2], changes[1::2]):
            path = raw_path.decode("utf-8", errors="surrogateescape")
            if status[:1] in {b"A", b"M"} and eligible(path):
                paths.append(path)
    found = []
    for path in paths:
        source = root / path
        if not source.is_file() or source.is_symlink() or not source.resolve().is_relative_to(root.resolve()):
            raise ValueError(f"unsafe or missing source: {path}")
        content = (source.read_text(encoding="utf-8") if ancestor is None
                   else _git(root, "show", f"HEAD:{path}").decode("utf-8"))
        added = _added_lines(root, ancestor, path) if ancestor is not None else None
        found.extend(item for item in extract(path, content) if added is None or item.line in added)
    return found


def expected_release_urls(base_version: str, head_version: str) -> set[str]:
    """Return links that cannot exist until a new distribution release is published."""
    if base_version == head_version:
        return set()
    origin = "https://github.com/docker/skills"
    return {
        f"{origin}/compare/v{head_version}...HEAD",
        f"{origin}/releases/tag/v{head_version}",
    }


def _catalog_version(content: str) -> str:
    lines = [line for line in content.splitlines() if re.match(r"^version[ \t]*:", line)]
    if len(lines) != 1 or not (match := CATALOG_VERSION_RE.fullmatch(lines[0])):
        raise ValueError("catalog.yaml must contain exactly one valid top-level X.Y.Z version")
    return match.group("version")


def _expected_pr_release_urls(root: Path, base: str) -> set[str]:
    ancestor = _git(root, "merge-base", base, "HEAD").decode().strip()
    base_version = _catalog_version(_git(root, "show", f"{ancestor}:catalog.yaml").decode("utf-8"))
    head_version = _catalog_version(_git(root, "show", "HEAD:catalog.yaml").decode("utf-8"))
    return expected_release_urls(base_version, head_version)


class _Anchors(html.parser.HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.ids: set[str] = set()
        self.evidence = False

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attributes = dict(attrs)
        if tag in {"html", "main", "article"}:
            self.evidence = True
        for key in ("id", "name"):
            if attributes.get(key) and (key == "id" or tag == "a"):
                self.ids.add(attributes[key] or "")


class _NoRedirect(request.HTTPRedirectHandler):
    def redirect_request(self, req: request.Request, fp: object, code: int, msg: str, headers: object, newurl: str) -> None:
        return None


def _public_address(address: str) -> bool:
    ip = ipaddress.ip_address(address)
    if not ip.is_global:
        return False
    # NAT64's well-known prefix can translate a public-looking IPv6 destination
    # into a private IPv4 destination on networks with a NAT64 gateway.
    return not (isinstance(ip, ipaddress.IPv6Address)
                and ip in ipaddress.ip_network("64:ff9b::/96")
                and not ipaddress.IPv4Address(ip.packed[-4:]).is_global)


def public_https(url: str) -> tuple[tuple[int, int, int, tuple], ...] | None:
    parsed = parse.urlsplit(url)
    if parsed.scheme.lower() != "https" or not parsed.hostname or parsed.username or parsed.password:
        return None
    try:
        if parsed.port not in (None, 443):
            return None
        addresses = socket.getaddrinfo(parsed.hostname, 443, type=socket.SOCK_STREAM)
        if not addresses or any(
            family not in (socket.AF_INET, socket.AF_INET6) or kind != socket.SOCK_STREAM
            or not _public_address(sockaddr[0])
            for family, kind, _, _, sockaddr in addresses
        ):
            return None
        return tuple((family, kind, protocol, sockaddr) for family, kind, protocol, _, sockaddr in addresses)
    except (OSError, ValueError):
        return None


class _PinnedConnection(http.client.HTTPSConnection):
    def __init__(self, host: str, addresses: tuple[tuple[int, int, int, tuple], ...], **kwargs: object) -> None:
        super().__init__(host, **kwargs)
        self._addresses = addresses
        self._create_connection = self._connect_pinned

    def _connect_pinned(self, _target: tuple[str, int], timeout: float, source_address: tuple | None) -> socket.socket:
        last_error: OSError | None = None
        for family, kind, protocol, sockaddr in self._addresses:
            sock = socket.socket(family, kind, protocol)
            try:
                sock.settimeout(timeout)
                if source_address:
                    sock.bind(source_address)
                sock.connect(sockaddr)
                return sock
            except OSError as exc:
                last_error = exc
                sock.close()
        assert last_error is not None
        raise last_error


class _PinnedHTTPSHandler(request.HTTPSHandler):
    def __init__(self, addresses: tuple[tuple[int, int, int, tuple], ...]) -> None:
        super().__init__()
        self.addresses = addresses

    def https_open(self, req: request.Request) -> object:
        # A proxy CONNECT to the hostname would resolve the origin a second time.
        # Do not bypass a configured proxy to make the request appear successful.
        if req._tunnel_host or req.has_proxy():
            raise ValueError("HTTPS proxy cannot pin the vetted origin address")
        return self.do_open(lambda host, **kwargs: _PinnedConnection(host, self.addresses, **kwargs),
                            req, context=self._context)


def open_pinned(req: request.Request, addresses: tuple[tuple[int, int, int, tuple], ...]) -> object:
    return request.build_opener(_NoRedirect, _PinnedHTTPSHandler(addresses)).open(req, timeout=TIMEOUT)


def fetch(url: str) -> Result:
    original = url
    current = url
    redirected = False
    for _ in range(MAX_REDIRECTS + 1):
        addresses = public_https(current)
        if addresses is None:
            return Result("warning", "HTTPS target is not a resolvable public address", current)
        req = request.Request(current, headers={"User-Agent": "docker-skills-link-check/1.0", "Accept": "text/html,*/*;q=0.8"})
        try:
            response = open_pinned(req, addresses)
        except error.HTTPError as exc:
            if exc.code in {301, 302, 303, 307, 308}:
                destination = exc.headers.get("Location")
                exc.close()
                if not destination:
                    return Result("warning", f"HTTP {exc.code} without Location", current)
                current = parse.urljoin(current, destination)
                redirected = True
                if not parse.urlsplit(current).fragment and parse.urlsplit(original).fragment:
                    current += "#" + parse.urlsplit(original).fragment
                continue
            exc.close()
            if exc.code in {404, 410}:
                return Result("error", f"HTTP {exc.code}", current, redirected)
            return Result("warning", f"HTTP {exc.code}", current)
        except (OSError, ValueError, http.client.HTTPException) as exc:
            return Result("warning", f"network error: {exc}", current)
        with response:
            final = response.geturl()
            content_type = response.headers.get("Content-Type", "").lower()
            docker = parse.urlsplit(final).hostname == "docs.docker.com"
            fragment = parse.unquote(parse.urlsplit(final).fragment or parse.urlsplit(original).fragment)
            if docker and fragment and "text/html" in content_type:
                try:
                    data = response.read(MAX_BYTES + 1)
                except (OSError, ValueError, http.client.HTTPException) as exc:
                    return Result("warning", f"network error: {exc}", final)
                if len(data) > MAX_BYTES:
                    return Result("warning", "Docker Docs page too large to verify anchor", final)
                parser = _Anchors()
                parser.feed(data.decode("utf-8", errors="replace"))
                if not parser.evidence:
                    return Result("warning", "Docker Docs page has no recognizable HTML structure to verify anchor", final)
                if fragment not in parser.ids:
                    return Result("error", f"Docker Docs anchor not found: #{fragment}", final)
            elif fragment and docker:
                return Result("warning", "Docker Docs response is not HTML; anchor not verified", final)
            elif fragment:
                return Result("warning", "anchor on non-Docker site not verified", final)
            if final.split("#", 1)[0] != original.split("#", 1)[0]:
                return Result("notice", f"redirected to {final}", final)
            return Result("ok", "reachable", final)
    return Result("warning", f"more than {MAX_REDIRECTS} redirects", current)


def check(url: str) -> Result:
    for attempt in range(RETRIES):
        result = fetch(url)
        if (result.message.startswith(("HTTP 429", "HTTP 5", "network error"))
                or result.message.startswith("Docker Docs anchor not found")):
            if attempt + 1 < RETRIES:
                time.sleep(0.2 * (attempt + 1))
                continue
        return result
    return result


def emit(found: list[Occurrence], results: dict[str, Result], summary: Path | None = None,
         expected: set[str] | None = None) -> bool:
    counts = {key: 0 for key in ("error", "warning", "notice", "ok")}
    reported = []
    for item in found:
        result = results[item.url]
        if (expected and item.path == "CHANGELOG.md" and item.url in expected
                and result.level == "error" and result.message == "HTTP 404"
                and result.final_url == item.url and not result.redirected):
            result = Result("notice", "HTTP 404 (release link not published yet)", result.final_url)
        reported.append((item, result))
        counts[result.level] += 1
        if result.level != "ok":
            message = f"{item.url}: {result.message}"
            print(f"{item.path}:{item.line}: {result.level}: {message}")
            if os.environ.get("GITHUB_ACTIONS") == "true":
                escape = lambda s: s.replace("%", "%25").replace("\r", "%0D").replace("\n", "%0A")
                print(f"::{result.level} file={escape(item.path)},line={item.line}::{escape(message)}")
    text = (f"External HTTPS links: {len(found)} occurrences, {len(results)} unique URLs; "
            + ", ".join(f"{counts[key]} {key}" for key in counts) + ".")
    print(text)
    if summary:
        with summary.open("a", encoding="utf-8") as output:
            output.write(f"### External HTTPS links\n\n{text}\n\n")
            for item, result in reported:
                if result.level != "ok":
                    output.write(f"- **{result.level}** `{item.path}:{item.line}` `{item.url}`: {result.message}\n")
    return counts["error"] > 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base", help="Only URL occurrences on lines added since the merge-base with this commit")
    parser.add_argument("--root", type=Path, default=REPO_ROOT)
    args = parser.parse_args(argv)
    try:
        found = occurrences(args.root, args.base)
        expected = _expected_pr_release_urls(args.root, args.base) if args.base is not None else None
        unique = list(dict.fromkeys(item.url for item in found))
        pool = concurrent.futures.ThreadPoolExecutor(max_workers=WORKERS)
        futures = {pool.submit(check, url): url for url in unique}
        results = {}
        deadline = time.monotonic() + OVERALL_TIMEOUT
        try:
            pending = set(futures)
            while pending:
                done, pending = concurrent.futures.wait(
                    pending, timeout=max(0, deadline - time.monotonic()),
                    return_when=concurrent.futures.FIRST_COMPLETED,
                )
                for future in done:
                    try:
                        results[futures[future]] = future.result()
                    except (OSError, ValueError, http.client.HTTPException) as exc:
                        results[futures[future]] = Result("warning", f"network error: {exc}")
                if not done:
                    break
            for future in pending:
                results[futures[future]] = Result("warning", "overall check deadline exceeded")
        finally:
            pool.shutdown(wait=False, cancel_futures=True)
        return int(emit(found, results, Path(os.environ["GITHUB_STEP_SUMMARY"]) if os.environ.get("GITHUB_STEP_SUMMARY") else None, expected))
    except (OSError, UnicodeError, ValueError) as exc:
        print(f"external link check: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())

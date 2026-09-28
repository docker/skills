#!/usr/bin/env python3
"""Verify public image manifests and linux/amd64 + linux/arm64 availability."""

from __future__ import annotations

import argparse
import http.client
import ipaddress
import json
import os
from pathlib import Path
import re
import socket
import ssl
import sys
from urllib import parse

from image_inventory import ROOT, Occurrence, occurrences

TIMEOUT = 8
MAX_BYTES = 1024 * 1024
INDEX_TYPES = {"application/vnd.oci.image.index.v1+json", "application/vnd.docker.distribution.manifest.list.v2+json"}
MANIFEST_TYPES = {"application/vnd.oci.image.manifest.v1+json", "application/vnd.docker.distribution.manifest.v2+json"}
ACCEPT = ", ".join(sorted(INDEX_TYPES | MANIFEST_TYPES))
HOSTS = {"registry-1.docker.io", "auth.docker.io", "gcr.io"}
MAX_REQUESTS = 8  # authentication plus top-level manifest and two child probes; bounded on failure


class Uncertain(Exception):
    """Network, policy, or protocol response insufficient to prove a tag is absent."""


class Missing(Exception):
    """Registry definitively reports the requested manifest is missing."""


def target(image: str) -> tuple[str, str, str] | None:
    path, separator, digest = image.partition("@")
    if separator:
        tag = digest
    else:
        path, separator, tag = image.rpartition(":")
        if not separator:
            path, tag = image, "latest"
    segments = path.split("/")
    if segments[0] in {"docker.io", "index.docker.io", "registry-1.docker.io"}:
        segments.pop(0)
        host = "registry-1.docker.io"
    elif segments[0] == "gcr.io":
        segments.pop(0)
        host = "gcr.io"
    elif "." in segments[0] or ":" in segments[0]:
        return None
    else:
        host = "registry-1.docker.io"
    if host == "registry-1.docker.io" and len(segments) == 1:
        segments.insert(0, "library")
    repository = "/".join(segments)
    if not repository or not tag:
        return None
    return host, repository, tag


def public_addresses(host: str) -> list[tuple[int, int, int, tuple]]:
    try:
        answers = socket.getaddrinfo(host, 443, type=socket.SOCK_STREAM)
        if not answers:
            raise Uncertain("no public DNS answers")
        addresses = []
        for family, kind, protocol, _, sockaddr in answers:
            if family not in (socket.AF_INET, socket.AF_INET6) or kind != socket.SOCK_STREAM:
                raise Uncertain("unexpected DNS answer")
            ip = ipaddress.ip_address(sockaddr[0])
            if not ip.is_global or (isinstance(ip, ipaddress.IPv6Address) and ip in ipaddress.ip_network("64:ff9b::/96")
                                    and not ipaddress.IPv4Address(ip.packed[-4:]).is_global):
                raise Uncertain("non-public DNS answer")
            addresses.append((family, kind, protocol, sockaddr))
        return addresses
    except (OSError, ValueError) as exc:
        raise Uncertain(f"DNS error: {exc}") from exc


class PinnedHTTPS(http.client.HTTPSConnection):
    def __init__(self, host: str, addresses: list[tuple[int, int, int, tuple]]):
        super().__init__(host, timeout=TIMEOUT, context=ssl.create_default_context())
        self.addresses = addresses
        self._create_connection = self.connect_pinned

    def connect_pinned(self, _address: tuple, timeout: float, source_address: tuple | None) -> socket.socket:
        last_error = None
        for family, kind, protocol, address in self.addresses:
            sock = socket.socket(family, kind, protocol)
            try:
                sock.settimeout(timeout)
                if source_address:
                    sock.bind(source_address)
                sock.connect(address)
                return sock
            except OSError as exc:
                last_error = exc
                sock.close()
        raise Uncertain(f"all vetted addresses failed: {last_error}")


def request(host: str, path: str, token: str = "", accept: str = ACCEPT, method: str = "GET") -> tuple[int, dict[str, str], bytes]:
    if method not in {"GET", "HEAD"}:
        raise Uncertain("request method not allowed")
    if host not in HOSTS or not path.startswith("/") or path.startswith("//") or any(c in path for c in "\r\n#"):
        raise Uncertain("request target not allowed")
    conn = PinnedHTTPS(host, public_addresses(host))
    try:
        headers = {"Accept": accept, "User-Agent": "docker-skills-image-check/1.0"}
        if token:
            headers["Authorization"] = f"Bearer {token}"
        conn.request(method, path, headers=headers)
        response = conn.getresponse()
        status = response.status
        response_headers = {key.lower(): value for key, value in response.getheaders()}
        if status in (301, 302, 303, 307, 308):
            raise Uncertain(f"HTTP {status} redirect not followed")
        size = response_headers.get("content-length")
        if method == "HEAD":
            return status, response_headers, b""
        if size and (not size.isdecimal() or int(size) > MAX_BYTES):
            raise Uncertain("response too large")
        body = response.read(MAX_BYTES + 1)
        if len(body) > MAX_BYTES:
            raise Uncertain("response too large")
        return status, response_headers, body
    except (OSError, ValueError, http.client.HTTPException, TimeoutError, ssl.SSLError) as exc:
        raise Uncertain(f"network error: {exc}") from exc
    finally:
        conn.close()


def bearer(challenge: str, host: str, repository: str) -> tuple[str, str]:
    if not challenge.lower().startswith("bearer "):
        raise Uncertain("unsupported authentication challenge")
    fields = dict((key.lower(), value) for key, value in re.findall(r'(\w+)="([^"\r\n]*)"', challenge[7:]))
    try:
        realm = parse.urlsplit(fields.get("realm", ""))
        port = realm.port
    except ValueError as exc:
        raise Uncertain("invalid token endpoint") from exc
    allowed = ((host == "registry-1.docker.io" and realm.hostname == "auth.docker.io" and realm.path == "/token")
               or (host == "gcr.io" and realm.hostname == "gcr.io" and realm.path == "/v2/token"))
    if not allowed or realm.scheme != "https" or port not in (None, 443) or realm.username or realm.password or realm.query or realm.fragment:
        raise Uncertain("untrusted token endpoint")
    scope = f"repository:{repository}:pull"
    if fields.get("scope") != scope:
        raise Uncertain("unexpected token scope")
    query = parse.urlencode({"service": fields.get("service", ""), "scope": scope})
    return realm.hostname, f"{realm.path}?{query}"


def document(body: bytes) -> dict:
    try:
        result = json.loads(body)
        if not isinstance(result, dict):
            raise ValueError("expected object")
        return result
    except (UnicodeError, ValueError) as exc:
        raise Uncertain(f"invalid JSON response: {exc}") from exc


def verify(image: str) -> tuple[str, str]:
    location = target(image)
    if location is None:
        return "notice", "unsupported registry; not checked"
    host, repository, tag = location
    token = ""
    count = 0

    def get(path: str, accept: str = ACCEPT, method: str = "GET") -> tuple[int, dict[str, str], bytes]:
        nonlocal count, token
        count += 1
        if count > MAX_REQUESTS:
            raise Uncertain("request limit exceeded")
        status, headers, body = request(host, path, token, accept, method)
        if status == 401 and not token:
            auth_host, auth_path = bearer(headers.get("www-authenticate", ""), host, repository)
            count += 1
            if count > MAX_REQUESTS:
                raise Uncertain("request limit exceeded")
            auth_status, _, auth_body = request(auth_host, auth_path, accept="application/json")
            if auth_status != 200:
                raise Uncertain(f"token endpoint HTTP {auth_status}")
            credentials = document(auth_body)
            token = credentials.get("token", "") or credentials.get("access_token", "")
            if not isinstance(token, str) or not token or len(token) > 8192:
                raise Uncertain("invalid anonymous token")
            count += 1
            if count > MAX_REQUESTS:
                raise Uncertain("request limit exceeded")
            status, headers, body = request(host, path, token, accept, method)
        return status, headers, body

    def manifest(ref: str, top: bool = False) -> dict:
        path = f"/v2/{repository}/manifests/{parse.quote(ref, safe=':@')}"
        status, headers, body = get(path, method="GET" if top else "HEAD")
        if status == 404:
            raise Missing("manifest not found (HTTP 404)")
        if status == 401 and token and top and host == "registry-1.docker.io":
            raise Missing("public manifest inaccessible after anonymous pull authorization (HTTP 401)")
        if status != 200:
            raise Uncertain(f"manifest HTTP {status}")
        media = headers.get("content-type", "").split(";", 1)[0].lower()
        if media not in INDEX_TYPES | MANIFEST_TYPES:
            raise Uncertain("unsupported manifest media type")
        if not top:
            return {}
        data = document(body)
        if data.get("mediaType", media) != media:
            raise Uncertain("unsupported manifest media type")
        return data

    try:
        top = manifest(tag, top=True)
        if "manifests" not in top:
            if not isinstance(top.get("config"), dict):
                raise Uncertain("manifest has no valid config")
            config = top["config"].get("digest")
            if not isinstance(config, str) or not re.fullmatch(r"sha256:[a-fA-F0-9]{64}", config):
                raise Uncertain("manifest has no valid config digest")
            return "error", "single-platform manifest cannot provide both linux/amd64 and linux/arm64"
        else:
            entries = top["manifests"]
            if not isinstance(entries, list) or any(not isinstance(entry, dict) or not isinstance(entry.get("platform"), dict)
                                                    for entry in entries):
                raise Uncertain("invalid platform index")
            missing = {"amd64", "arm64"} - {entry["platform"].get("architecture") for entry in entries
                                                 if entry["platform"].get("os") == "linux"}
            if not missing:
                # Index entries can point to missing children; verify both manifests exist.
                for arch in ("amd64", "arm64"):
                    entry = next(entry for entry in entries if entry.get("platform", {}).get("os") == "linux"
                                 and entry["platform"].get("architecture") == arch)
                    digest = entry.get("digest")
                    if not isinstance(digest, str) or not re.fullmatch(r"sha256:[a-fA-F0-9]{64}", digest):
                        raise Uncertain("invalid child digest")
                    manifest(digest)
        if missing:
            return "error", f"missing linux/{', linux/'.join(sorted(missing))}"
        return "ok", "manifest and both platforms available"
    except Missing as exc:
        return "error", str(exc)
    except (Uncertain, KeyError, TypeError, AttributeError) as exc:
        return "warning", str(exc)


def emit(found: list[Occurrence], results: dict[str, tuple[str, str]], *, full_sweep: bool = False) -> bool:
    counts = {key: 0 for key in ("ok", "error", "warning", "notice")}
    summary = []
    for item in found:
        level, message = results[item.image]
        counts[level] += 1
        if level != "ok":
            text = f"{item.image}: {message}"
            print(f"{item.path}:{item.line}: {level}: {text}")
            if os.environ.get("GITHUB_ACTIONS") == "true":
                escape = lambda s: s.replace("%", "%25").replace("\r", "%0D").replace("\n", "%0A")
                print(f"::{level} file={escape(item.path)},line={item.line}::{escape(text)}")
            summary.append(f"- **{level}** `{item.path}:{item.line}` `{item.image}`: {message}\n")
    text = (f"Container images: {len(found)} occurrences, {len(results)} unique references; "
            + ", ".join(f"{counts[key]} {key}" for key in counts) + ".")
    print(text)
    if os.environ.get("GITHUB_STEP_SUMMARY"):
        with Path(os.environ["GITHUB_STEP_SUMMARY"]).open("a", encoding="utf-8") as output:
            output.write("### Container image validation\n\n" + text + "\n\n" + "".join(summary))
    return counts["error"] > 0 or (full_sweep and bool(found) and not counts["ok"] and bool(counts["warning"]))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base", help="Check references on lines added since the merge-base with this commit")
    parser.add_argument("--root", type=Path, default=ROOT)
    args = parser.parse_args(argv)
    try:
        found = occurrences(args.root, args.base)
        results = {image: verify(image) for image in dict.fromkeys(item.image for item in found)}
        return int(emit(found, results, full_sweep=args.base is None))
    except (OSError, UnicodeError, ValueError) as exc:
        print(f"image check: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())

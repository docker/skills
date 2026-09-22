"""Deterministic security and integrity checks for canonical skill content."""

from __future__ import annotations

import os
import re
import stat
import unicodedata
from pathlib import Path
from urllib.parse import urlsplit

MAX_FILE_SIZE = 256 * 1024
CREDENTIAL_SUFFIXES = (".pem", ".key", ".p12", ".pfx")
PROMPT_INJECTION_PATTERNS = (
    re.compile(r"\b(?:ignore|disregard)\s+(?:all\s+)?(?:previous|prior|above)\s+instructions\b", re.I),
    re.compile(r"\bdo(?:[ -]not)?[ -](?:tell|inform)\s+(?:the\s+)?user\b", re.I),
    re.compile(r"\bwithout\s+(?:telling|informing|asking)\s+(?:the\s+)?user\b", re.I),
)
TOKEN_PATTERNS = (
    re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
    re.compile(r"\b(?:gh[oprsu]_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,})\b"),
    re.compile(r"\bsk-[A-Za-z0-9]{20,}\b"),
    re.compile(r"\bxox[baprs]-[A-Za-z0-9-]{10,}\b"),
    re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
)
PIPE_TO_SHELL_RE = re.compile(
    r"\b(?:curl|wget)\b[^\n|]*(?:\|\s*)(?:sudo\s+)?(?:ba|z|k)?sh\b",
    re.I,
)
NPX_YES_RE = re.compile(r"\bnpx\s+(?:-y|--yes)(?:\s|$)")
HTTP_RE = re.compile(r"http://[^\s<>'\"`)\]},]+", re.I)


def _relative(path: Path, root: Path) -> str:
    return path.relative_to(root).as_posix()


def _allowed_http_host(host: str | None) -> bool:
    if not host:
        return False
    host = host.rstrip(".").lower()
    if host in {"localhost", "host.docker.internal", "::1"} or host.endswith(".local"):
        return True
    if host.startswith("127."):
        return True
    if host in {"api", "db"} or re.fullmatch(r"[a-z0-9](?:[a-z0-9-]*[a-z0-9])?", host):
        return True
    return False


def _hidden_codepoint(character: str) -> bool:
    value = ord(character)
    return (
        unicodedata.category(character) == "Co"
        or value in {0x061C, 0x200B, 0x200C, 0x200D, 0x2060, 0xFEFF}
        or 0x202A <= value <= 0x202E
        or 0x2066 <= value <= 0x2069
        or 0xE0000 <= value <= 0xE007F
    )


def _scan_text(path: Path, relative: str, data: bytes) -> list[str]:
    try:
        content = data.decode("utf-8")
    except UnicodeDecodeError:
        return [f"{relative}: invalid UTF-8"]

    errors: list[str] = []
    if "\r" in content:
        errors.append(f"{relative}: contains carriage-return characters")
    if any(unicodedata.category(char) == "Cc" and char not in "\t\n\r" for char in content):
        errors.append(f"{relative}: contains prohibited C0/C1 control characters")
    if any(_hidden_codepoint(char) for char in content):
        errors.append(f"{relative}: contains hidden bidi, zero-width, tag, or private-use codepoints")
    if path.suffix.lower() == ".md" and "<!--" in content:
        errors.append(f"{relative}: Markdown HTML comments are prohibited")
    if PIPE_TO_SHELL_RE.search(content):
        errors.append(f"{relative}: curl/wget pipe-to-shell commands are prohibited")
    if NPX_YES_RE.search(content):
        errors.append(f"{relative}: non-interactive npx -y/--yes is prohibited")
    if any(pattern.search(content) for pattern in PROMPT_INJECTION_PATTERNS):
        errors.append(f"{relative}: contains a prohibited prompt-injection phrase")
    if any(pattern.search(content) for pattern in TOKEN_PATTERNS):
        errors.append(f"{relative}: contains a token, key, or private-key pattern")
    for match in HTTP_RE.finditer(content):
        host = urlsplit(match.group()).hostname
        if not _allowed_http_host(host):
            errors.append(f"{relative}: external insecure http:// URL is prohibited")
            break
    return errors


def validate_content_risk(root: str | Path) -> list[str]:
    """Return deterministic findings for risky files and content below skills/."""
    root = Path(root).resolve()
    skills = root / "skills"
    if not skills.is_dir():
        return ["skills: directory is missing"]

    errors: list[str] = []
    for current, dirnames, filenames in os.walk(skills, followlinks=False):
        current_path = Path(current)
        for name in sorted(dirnames):
            path = current_path / name
            if path.is_symlink():
                errors.append(f"{_relative(path, root)}: symlinks are prohibited under skills/")
        dirnames[:] = [name for name in sorted(dirnames) if not (current_path / name).is_symlink()]

        for name in sorted(filenames):
            path = current_path / name
            relative = _relative(path, root)
            if path.is_symlink():
                errors.append(f"{relative}: symlinks are prohibited under skills/")
                continue
            try:
                metadata = path.stat()
                if not stat.S_ISREG(metadata.st_mode):
                    continue
                if metadata.st_size > MAX_FILE_SIZE:
                    errors.append(f"{relative}: file exceeds 256 KiB")
                    continue
                data = path.read_bytes()
            except OSError as exc:
                errors.append(f"{relative}: cannot inspect file: {exc}")
                continue
            parts = path.relative_to(skills).parts
            in_skill_scripts = len(parts) >= 3 and parts[1] == "scripts"
            if metadata.st_mode & 0o111 and not in_skill_scripts:
                errors.append(f"{relative}: executable bit is allowed only under skills/*/scripts/*")
            lowered = name.lower()
            if lowered.startswith(".env") or lowered.endswith(CREDENTIAL_SUFFIXES):
                errors.append(f"{relative}: credential filenames are prohibited")
            errors.extend(_scan_text(path, relative, data))
    return sorted(errors)

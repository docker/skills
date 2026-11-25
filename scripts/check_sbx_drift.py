#!/usr/bin/env python3
"""Check that Docker Sandboxes skills and public docs match the `sbx` CLI help.

The `--help` output of an installed `sbx` (in CI: the latest release) is the
ground truth for command names, subcommands, flags, arguments, and accepted
values. This script:

1. Walks the whole command tree with `sbx [--cloud] <command...> --help`.
2. Loads the `skills/docker-sandboxes-*` Markdown files and fetches the
   Markdown version of every https://docs.docker.com/ai/sandboxes/ page
   listed in the Docs sitemap.
3. Asks an LLM, through the Docker AI Gateway (same credentials as the live
   evals in `eval_judge.py`), to list `sbx` usage that contradicts the help.
4. Keeps only findings whose quotes really appear in the sources, prints them,
   and exits 1 when any remain.

This is a live check (network + model); it is not part of offline `task ci`.

Usage:
  python3 scripts/check_sbx_drift.py                    # sbx from PATH
  python3 scripts/check_sbx_drift.py --sbx /path/to/sbx
  python3 scripts/check_sbx_drift.py --no-docs          # skills only
  python3 scripts/check_sbx_drift.py --dry-run          # collect sources, no model call

Exit codes: 0 coherent, 1 incoherences found, 2 setup or infrastructure error.
"""

from __future__ import annotations

import argparse
import concurrent.futures
import dataclasses
import json
import os
import re
import subprocess
import sys
import time
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))
import eval_judge  # noqa: E402  (shared Docker AI Gateway helpers)

REPO_ROOT = Path(__file__).resolve().parent.parent
SKILLS_ROOT = REPO_ROOT / "skills"
SKILL_GLOB = "docker-sandboxes-*"
DOCS_SITEMAP = "https://docs.docker.com/sitemap.xml"
DOCS_PREFIX = "https://docs.docker.com/ai/sandboxes/"
# Historical changes legitimately mention removed commands and flags
DOCS_EXCLUDE = ("https://docs.docker.com/ai/sandboxes/release-notes/",)
# Subcommands whose help adds nothing about sandbox usage
SKIP_COMMANDS = {"help", "completion"}
# Never probe an unlisted command path containing these words: if it ignored
# --help it would run
DESTRUCTIVE_WORDS = {"rm", "remove", "delete", "reset", "prune", "logout", "stop", "clean"}
DEFAULT_MODEL = "claude-sonnet-4-5-20250929"
MAX_BATCH_CHARS = 60_000
MAX_OUTPUT_TOKENS = 32_000
THINKING_TOKENS = 16_000
LLM_ATTEMPTS = 3
USER_AGENT = "docker-skills-sbx-drift-check"
# Never handed to the sbx binary under test
SECRET_ENV_VARS = {*eval_judge.HUB_CREDENTIAL_VARS, "DOCKER_GATEWAY_TOKEN"}


class DriftError(RuntimeError):
    pass


@dataclasses.dataclass
class Document:
    source: str  # repository path or docs URL
    text: str


@dataclasses.dataclass
class Finding:
    source: str
    command: str
    document_quote: str
    help_quote: str
    problem: str
    suggestion: str = ""
    kind: str = "other"
    flag: str = ""
    verified: bool = True
    unverified_reason: str = ""


# ─── sbx help ────────────────────────────────────────────────────────────────

def parse_subcommands(help_text: str) -> list[str]:
    """Return subcommand names listed under every "... Commands:" heading."""
    names: list[str] = []
    in_section = False
    for line in help_text.splitlines():
        if re.match(r"^\S.*Commands:\s*$", line):
            in_section = True
            continue
        if in_section:
            m = re.match(r"^\s+([a-z0-9][a-z0-9-]*)(?:\s{2,}|\s*$)", line)
            if m:
                if m.group(1) not in SKIP_COMMANDS and m.group(1) not in names:
                    names.append(m.group(1))
                continue
            in_section = False
    return names


def run_sbx(sbx: str, args: list[str]) -> subprocess.CompletedProcess[str]:
    """Run sbx non-interactively, without the gateway and Docker Hub credentials."""
    env = {k: v for k, v in os.environ.items() if k not in SECRET_ENV_VARS}
    return subprocess.run([sbx, *args], capture_output=True, text=True, timeout=30,
                          stdin=subprocess.DEVNULL, env=env)


def _run_help(sbx: str, args: list[str]) -> str:
    try:
        proc = run_sbx(sbx, [*args, "--help"])
        if proc.returncode != 0 and args:
            # Some commands check sign-in before handling --help; `sbx help CMD` does not
            mode = [a for a in args if a.startswith("-")]
            path = [a for a in args if not a.startswith("-")]
            proc = run_sbx(sbx, [*mode, "help", *path])
    except (OSError, subprocess.TimeoutExpired) as e:
        raise DriftError(f"`{sbx} {' '.join(args)} --help` failed: {e}") from e
    if proc.returncode != 0:
        raise DriftError(f"`{sbx} {' '.join(args)} --help` exited {proc.returncode}: "
                         f"{(proc.stderr or proc.stdout).strip()[:500]}")
    return proc.stdout


def collect_help(sbx: str, mode_args: tuple[str, ...] = ()) -> dict[str, str]:
    """Walk the command tree breadth-first: {"sbx policy allow": help text}.

    A command whose help cannot be read at all is kept with a placeholder (and a
    warning) so the rest of the tree is still checked.
    """
    pages: dict[str, str] = {}
    queue: list[list[str]] = [[]]
    while queue:
        path = queue.pop(0)
        name = " ".join(["sbx", *mode_args, *path])
        try:
            text = _run_help(sbx, [*mode_args, *path])
        except DriftError as e:
            if not path:
                raise
            print(f"warning: {e}", file=sys.stderr)
            pages[name] = "(help unavailable in this environment; the command exists)\n"
            continue
        pages[name] = text
        queue.extend([*path, sub] for sub in parse_subcommands(text))
    return pages


def sbx_version(sbx: str) -> str:
    try:
        proc = run_sbx(sbx, ["version"])
    except (OSError, subprocess.TimeoutExpired) as e:
        raise DriftError(f"`{sbx} version` failed: {e}") from e
    out = proc.stdout.strip()
    m = re.search(r"\bv\d+\.\d+\.\d+\S*", out)
    return m.group(0) if m else (out.splitlines()[0] if out else "unknown")


def strip_global_flags(text: str) -> str:
    """Drop the "Global Flags:" block repeated on every subcommand (the root lists them)."""
    return re.sub(r"\nGlobal Flags:\n(?:[ \t]+.*(?:\n|$))*", "\n", text)


def merge_help(local: dict[str, str], cloud: dict[str, str]) -> dict[str, str]:
    """Local pages plus the --cloud pages that differ from their local counterpart."""
    pages = {cmd: strip_global_flags(text) for cmd, text in local.items()}
    for cmd, text in cloud.items():
        text = strip_global_flags(text)
        if pages.get(cmd.replace("sbx --cloud", "sbx", 1)) != text:
            pages[cmd] = text
    return pages


def render_help(pages: dict[str, str]) -> str:
    return "\n".join(f"$ {cmd} --help\n{text.rstrip()}\n" for cmd, text in pages.items())


# ─── sources ─────────────────────────────────────────────────────────────────

def load_skill_documents(skills_root: Path = SKILLS_ROOT) -> list[Document]:
    """Every Markdown file of the sandbox skills, except the eval runbooks."""
    docs = []
    for skill_dir in sorted(skills_root.glob(SKILL_GLOB)):
        if not skill_dir.is_dir():
            continue
        for path in sorted(skill_dir.rglob("*.md")):
            if "evals" in path.relative_to(skill_dir).parts:
                continue
            docs.append(Document(str(path.relative_to(skills_root.parent)), path.read_text(encoding="utf-8")))
    return docs


def _fetch(url: str) -> str:
    last: Exception | None = None
    for attempt in range(3):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
            with urllib.request.urlopen(req, timeout=30) as resp:
                return resp.read().decode("utf-8")
        except (OSError, UnicodeDecodeError) as e:
            last = e
            time.sleep(2 * (attempt + 1))
    raise DriftError(f"could not fetch {url}: {last}")


def docs_page_urls(sitemap_xml: str, prefix: str = DOCS_PREFIX) -> list[str]:
    ns = {"sm": "http://www.sitemaps.org/schemas/sitemap/0.9"}
    root = ET.fromstring(sitemap_xml)
    urls = {(loc.text or "").strip() for loc in root.iterfind(".//sm:loc", ns)}
    root_page = prefix.rstrip("/") + "/"
    return sorted(u for u in urls
                  if (u == root_page or u.startswith(prefix)) and not u.startswith(DOCS_EXCLUDE))


def markdown_url(page_url: str) -> str:
    """docs.docker.com serves each page's Markdown at <path>.md."""
    return page_url.rstrip("/") + ".md"


def load_docs_documents(prefix: str = DOCS_PREFIX) -> list[Document]:
    urls = docs_page_urls(_fetch(DOCS_SITEMAP), prefix)
    if not urls:
        raise DriftError(f"no {prefix} pages found in {DOCS_SITEMAP}")
    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
        texts = list(pool.map(lambda u: _fetch(markdown_url(u)), urls))
    return [Document(url, text) for url, text in zip(urls, texts)]


def batch_documents(docs: list[Document], max_chars: int = MAX_BATCH_CHARS) -> list[list[Document]]:
    """Group documents into batches below max_chars, splitting oversized ones."""
    batches: list[list[Document]] = []
    current: list[Document] = []
    size = 0
    for doc in docs:
        parts = [doc]
        if len(doc.text) > max_chars:
            parts = [Document(f"{doc.source} (part {i // max_chars + 1})", doc.text[i:i + max_chars])
                     for i in range(0, len(doc.text), max_chars)]
        for part in parts:
            if current and size + len(part.text) > max_chars:
                batches.append(current)
                current, size = [], 0
            current.append(part)
            size += len(part.text)
    if current:
        batches.append(current)
    return batches


# ─── model ───────────────────────────────────────────────────────────────────

INSTRUCTIONS = """\
You audit documentation of the Docker Sandboxes `sbx` CLI for drift.

<cli_help> holds the complete `--help` output of every command of the
released `sbx` {version} in local mode, plus the `sbx --cloud ...` pages
that differ in cloud mode (a cloud page identical to its local page is
omitted; the `sbx --cloud` root page lists the commands cloud mode supports).
Global flags are listed once, on the root `sbx` page. It is
the ground truth for command and subcommand names,
flags, short flags, positional arguments, accepted values, and defaults.

<documents> holds documentation pages. Go through every `sbx` invocation and
flag they mention, one by one, and report each `sbx` invocation or
statement about `sbx` command-line usage that CONTRADICTS the help:
- a command or subcommand that does not exist (for example renamed or removed);
- a flag that does not exist on that command, or a wrong short flag;
- wrong positional argument syntax, flag value syntax, or accepted values;
- a default value that differs from the one the help states;
- a command or flag the help marks deprecated, presented as current usage;
- a list of values (such as built-in agents) that disagrees with the help's list;
- a description of what a command or flag does that the help contradicts.

Do NOT report:
- help features the documents do not mention (omissions are fine);
- commands of other tools (docker, git, claude, codex, gh, curl, ...),
  commands run inside a sandbox, or file formats such as sbxenv.yaml or kit
  spec.yaml files, which `--help` does not describe;
- usage valid in either local or `--cloud` mode, matching the document's context;
- global flags (`--cloud`, `-D`/`--debug`, `-h`/`--help`) used on any command;
- flags the document itself presents as hidden or internal;
- placeholders such as NAME, <sandbox>, or PATH, or shortened illustrative output;
- usage that the help's examples merely do not show (such as a `--` separator),
  or limitations and behavior the help does not mention;
- behavior the help does not state either way. Report only contradictions the
  help text states explicitly; when unsure, do not report.

Reply with only a JSON object, no prose:
{{"findings": [{{"source": "<source attribute of the document>",
  "kind": "<missing_command | missing_flag | other>",
  "command": "<command path only, no arguments: e.g. sbx port publish, sbx --cloud schedule ls, or sbx for a global flag>",
  "flag": "<for missing_flag: the flag as written, e.g. --model or -g; otherwise empty>",
  "document_quote": "<exact, verbatim excerpt (max 200 chars) of the document showing the problem>",
  "help_quote": "<exact, verbatim excerpt (max 200 chars) of cli_help proving it, or empty>",
  "problem": "<one sentence: what contradicts the help>",
  "suggestion": "<one sentence: what the document should say>"}}]}}
Use kind missing_command when the command or subcommand is not in the help,
missing_flag when the flag is not listed for that command, other otherwise.
Copy quotes character for character, without adding ellipses. Report each
problem once per document. Use {{"findings": []}} when everything is coherent.
"""


def build_prompt(help_text: str, version: str, batch: list[Document]) -> tuple[str, str]:
    """Return (cacheable help block, per-batch documents block)."""
    head = INSTRUCTIONS.format(version=version) + f"\n<cli_help>\n{help_text}</cli_help>\n"
    body = "<documents>\n" + "".join(
        f'<document source="{d.source}">\n{d.text.rstrip()}\n</document>\n' for d in batch
    ) + "</documents>"
    return head, body


def read_stream(lines) -> str:
    """Concatenate the text deltas of an Anthropic server-sent event stream."""
    parts: list[str] = []
    stop_reason = None
    for raw in lines:
        line = raw.decode("utf-8") if isinstance(raw, bytes) else raw
        if not line.startswith("data:"):
            continue
        event = json.loads(line[5:])
        kind = event.get("type")
        if kind == "content_block_delta" and event.get("delta", {}).get("type") == "text_delta":
            parts.append(event["delta"].get("text", ""))
        elif kind == "message_delta":
            stop_reason = event.get("delta", {}).get("stop_reason") or stop_reason
        elif kind == "error":
            error = event.get("error", {})
            status = 529 if error.get("type") == "overloaded_error" else 500
            raise eval_judge.JudgeAPIError(status, json.dumps(error))
    if stop_reason == "max_tokens":
        raise DriftError("model reply truncated (max_tokens); lower MAX_BATCH_CHARS")
    return "".join(parts)


def call_model(head: str, body: str, model: str) -> dict[str, Any]:
    """Anthropic Messages API through the Docker AI Gateway, with extended thinking.

    Thinking matters: without it the model tends to answer an empty findings
    list straight away on these long inputs. The reply is streamed so the
    gateway does not time out while the model thinks.
    """
    payload = json.dumps({
        "model": model,
        "max_tokens": MAX_OUTPUT_TOKENS,
        "thinking": {"type": "enabled", "budget_tokens": THINKING_TOKENS},
        "stream": True,
        "messages": [
            {"role": "user", "content": [
                # The help block is identical for every batch: let the gateway cache it
                {"type": "text", "text": head, "cache_control": {"type": "ephemeral"}},
                {"type": "text", "text": body},
            ]},
        ],
    }).encode()
    req = urllib.request.Request(
        f"{eval_judge.GATEWAY_ANTHROPIC_URL}/v1/messages",
        data=payload,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {eval_judge.get_docker_gateway_token()}",
            "anthropic-version": "2023-06-01",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=300) as resp:
            text = read_stream(resp)
    except urllib.error.HTTPError as e:
        raise eval_judge.JudgeAPIError(e.code, e.read().decode() if e.fp else "") from e
    return eval_judge.parse_judge_json(text)


def check_batch(sbx: str, help_text: str, version: str, batch: list[Document], model: str) -> list[Finding]:
    head, body = build_prompt(help_text, version, batch)
    for attempt in range(1, LLM_ATTEMPTS + 1):
        try:
            reply = call_model(head, body, model)
            break
        except eval_judge.JudgeAPIError as e:
            if not e.retryable or attempt == LLM_ATTEMPTS:
                raise DriftError(f"model call failed: {e}") from e
            print(f"warning: model call failed (attempt {attempt}), retrying: {str(e)[:200]}",
                  file=sys.stderr, flush=True)
        except (OSError, json.JSONDecodeError) as e:
            if attempt == LLM_ATTEMPTS:
                raise DriftError(f"model call failed: {e}") from e
            print(f"warning: model call failed (attempt {attempt}), retrying: {str(e)[:200]}",
                  file=sys.stderr, flush=True)
        time.sleep(15 * attempt)
    findings = verify_findings(reply, help_text, batch)
    for f in findings:
        if f.verified:
            reason = hidden_reason(sbx, f)
            if reason:
                f.verified, f.unverified_reason = False, reason
    return findings


def parse_command(command: str) -> tuple[list[str], list[str]] | None:
    """Split "sbx --cloud schedule ls" into (mode flags, command path); None if not an sbx path."""
    m = re.match(r"^sbx((?:\s+--cloud)?)((?:\s+[a-z][a-z0-9-]*)*)\s*(?:$|[\s/(,])", command.strip())
    if not m:
        return None
    return m.group(1).split(), m.group(2).split()


def _probe(sbx: str, args: list[str]) -> str:
    try:
        proc = run_sbx(sbx, args)
    except (OSError, subprocess.TimeoutExpired):
        return ""
    return proc.stdout + proc.stderr


def _usage_path(help_text: str) -> list[str]:
    m = re.search(r"^Usage:\s*\n\s*(sbx(?:\s+[a-z][a-z0-9-]*)*)", help_text, re.MULTILINE)
    return m.group(1).split()[1:] if m else []


def hidden_reason(sbx: str, finding: Finding) -> str | None:
    """Ask the binary whether a command or flag the help does not list exists anyway.

    `--help` omits hidden commands and flags. Documenting one is not a drift,
    unless the binary marks it deprecated. Returns why the finding should be
    ignored, or None to keep it.
    """
    parsed = parse_command(finding.command)
    if parsed is None:
        return None
    mode, path = parsed
    if finding.kind == "missing_command" and path and not DESTRUCTIVE_WORDS.intersection(path):
        out = _probe(sbx, [*mode, *path, "--help"])
        if _usage_path(out) != path:
            out = _probe(sbx, [*mode, "help", *path])  # commands that need sign-in for --help
        if _usage_path(out) == path and "deprecated" not in out.lower():
            return f"`{finding.command}` exists as a hidden command"
    elif finding.kind == "missing_flag" and re.fullmatch(r"--?[A-Za-z0-9][A-Za-z0-9-]*", finding.flag):
        # Unknown flags fail parsing before --help; a value keeps --help from being consumed
        out = _probe(sbx, [*mode, *path, f"{finding.flag}=1", "--help"])
        lowered = out.lower()
        if "Usage:" in out and "unknown flag" not in lowered and "unknown shorthand flag" not in lowered \
                and "deprecated" not in lowered:
            return f"`{finding.flag}` exists as a hidden flag of `{finding.command}`"
    return None


# ─── verification and report ─────────────────────────────────────────────────

def normalize(text: str) -> str:
    """Compare quotes modulo Markdown emphasis, quoting style, and whitespace."""
    text = text.replace("\u2019", "'").replace("\u2018", "'").replace("\u201c", '"').replace("\u201d", '"')
    text = re.sub(r"[`*_>\\]", "", text.lower())
    return re.sub(r"\s+", " ", text).strip()


def verify_findings(reply: dict[str, Any], help_text: str, batch: list[Document]) -> list[Finding]:
    """Turn the model reply into findings, flagging those whose quotes are not in the sources."""
    by_source = {d.source: normalize(d.text) for d in batch}
    help_norm = normalize(help_text)
    findings = []
    for raw in reply.get("findings") or []:
        if not isinstance(raw, dict):
            continue
        f = Finding(
            source=str(raw.get("source", "")).strip(),
            command=str(raw.get("command", "")).strip(),
            document_quote=str(raw.get("document_quote", "")).strip(),
            help_quote=str(raw.get("help_quote", "")).strip(),
            problem=str(raw.get("problem", "")).strip(),
            suggestion=str(raw.get("suggestion", "")).strip(),
            kind=str(raw.get("kind", "other")).strip() or "other",
            flag=str(raw.get("flag", "")).strip(),
        )
        doc_norm = by_source.get(f.source)
        if doc_norm is None:
            f.verified, f.unverified_reason = False, "unknown source"
        elif not f.document_quote or normalize(f.document_quote) not in doc_norm:
            f.verified, f.unverified_reason = False, "document quote not found in source"
        elif f.help_quote and normalize(f.help_quote) not in help_norm:
            f.verified, f.unverified_reason = False, "help quote not found in sbx help"
        findings.append(f)
    return findings


def _annotation(text: str) -> str:
    return text.replace("%", "%25").replace("\r", "%0D").replace("\n", "%0A")


def report(findings: list[Finding]) -> int:
    """Print findings grouped by source; return the number of verified ones."""
    verified = [f for f in findings if f.verified]
    unverified = [f for f in findings if not f.verified]
    in_actions = os.environ.get("GITHUB_ACTIONS") == "true"
    for f in sorted(verified, key=lambda f: (f.source, f.command)):
        print(f"\n✗ {f.source}\n  command:  {f.command}\n  problem:  {f.problem}")
        print(f"  document: {f.document_quote}")
        if f.help_quote:
            print(f"  help:     {f.help_quote}")
        if f.suggestion:
            print(f"  fix:      {f.suggestion}")
        if in_actions:
            location = f" file={f.source}" if not f.source.startswith("https://") else ""
            print(f"::error{location},title=sbx drift ({f.command})::"
                  f"{_annotation(f.source + ': ' + f.problem)}")
    for f in unverified:
        # Quotes the model could not ground in the sources: likely hallucinated, never fails the run
        print(f"\n? (ignored, {f.unverified_reason}) {f.source}: {f.command}: {f.problem}\n"
              f"  document: {f.document_quote}\n  help:     {f.help_quote}")
    return len(verified)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--sbx", default="sbx", help="sbx binary to read --help from (default: sbx on PATH)")
    parser.add_argument("--model", default=DEFAULT_MODEL, help="Anthropic model behind the Docker AI Gateway")
    parser.add_argument("--no-skills", action="store_true", help="Skip the skills/docker-sandboxes-* files")
    parser.add_argument("--no-docs", action="store_true", help=f"Skip the {DOCS_PREFIX} pages")
    parser.add_argument("--workers", type=int, default=4, help="Concurrent model calls")
    parser.add_argument("--dry-run", action="store_true", help="Collect sources and batches, no model call")
    args = parser.parse_args(argv)

    try:
        version = sbx_version(args.sbx)
        print(f"sbx: {version}", flush=True)
        pages = merge_help(collect_help(args.sbx), collect_help(args.sbx, ("--cloud",)))
        help_text = render_help(pages)
        print(f"help: {len(pages)} pages, {len(help_text)} chars", flush=True)

        docs: list[Document] = []
        if not args.no_skills:
            skills = load_skill_documents()
            print(f"skills: {len(skills)} files", flush=True)
            docs.extend(skills)
        if not args.no_docs:
            pages_md = load_docs_documents()
            print(f"docs: {len(pages_md)} pages under {DOCS_PREFIX}", flush=True)
            docs.extend(pages_md)
        if not docs:
            print("nothing to check", file=sys.stderr)
            return 2
        batches = batch_documents(docs)
        print(f"batches: {len(batches)} (model {args.model})", flush=True)
        if args.dry_run:
            for i, batch in enumerate(batches, 1):
                print(f"  batch {i}: {sum(len(d.text) for d in batch)} chars, {len(batch)} documents")
            return 0

        eval_judge.get_docker_gateway_token()
        findings: list[Finding] = []
        failed: list[str] = []
        with concurrent.futures.ThreadPoolExecutor(max_workers=max(1, args.workers)) as pool:
            futures = {pool.submit(check_batch, args.sbx, help_text, version, b, args.model): (i, b)
                       for i, b in enumerate(batches, 1)}
            for future in concurrent.futures.as_completed(futures):
                i, batch = futures[future]
                try:
                    batch_findings = future.result()
                except DriftError as e:
                    # Keep the other batches' results; the run still fails below
                    print(f"batch {i}/{len(batches)}: error: {e}", file=sys.stderr, flush=True)
                    failed.extend(d.source for d in batch)
                    continue
                print(f"batch {i}/{len(batches)}: {len(batch_findings)} finding(s)", flush=True)
                findings.extend(batch_findings)
    except (DriftError, RuntimeError, ET.ParseError) as e:
        print(f"error: {e}", file=sys.stderr)
        return 2

    count = report(findings)
    print(f"\n{'=' * 60}")
    if count:
        print(f"{count} incoherence(s) between sbx {version} --help and the skills/docs")
    if failed:
        print(f"Not checked (model errors), {len(failed)} document(s):\n  " + "\n  ".join(failed),
              file=sys.stderr)
    if count:
        return 1
    if failed:
        return 2
    print(f"Skills and docs are coherent with sbx {version} --help")
    return 0


if __name__ == "__main__":
    sys.exit(main())

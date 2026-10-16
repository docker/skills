"""LLM judge for prose criteria: one reply, one binary criterion, majority vote."""

from __future__ import annotations

import hashlib
import json
import re
import concurrent.futures
import subprocess
import sys
from typing import Any, Callable

PROMPT_TEMPLATE = """You are grading one reply from a coding assistant against one criterion.
Judge only what the reply says. Do not reward length, tone, or confident wording.

Criterion: {criterion}

Reply (between the markers):
<<<REPLY
{reply}
REPLY>>>

Answer with a single JSON object and nothing else:
{{"verdict": "yes" | "no" | "unknown", "reason": "<one sentence>"}}
Use "yes" only if the reply clearly satisfies the criterion, "no" if it clearly does not,
and "unknown" if the reply is empty or the criterion cannot be decided from it."""

VERDICTS = ("yes", "no", "unknown")
# Prefix on the reason of a vote that failed for infrastructure reasons. Such votes count
# as "unknown" but are never cached, so the next report retries them.
JUDGE_ERROR = "judge error: "


def redact(text: str, terms: list[str]) -> str:
    """Remove skill names and skill-specific jargon so the judge can't reward echoed phrasing."""
    for term in sorted({t for t in terms if t}, key=len, reverse=True):
        text = re.sub(re.escape(term), "[redacted]", text, flags=re.IGNORECASE)
    return text


def build_prompt(criterion: str, reply: str) -> str:
    return PROMPT_TEMPLATE.format(criterion=criterion.strip(), reply=reply.strip())


def parse_verdict(stdout: str) -> tuple[str, str]:
    text = stdout.strip()
    try:
        outer = json.loads(text)
        if isinstance(outer, dict) and isinstance(outer.get("result"), str):
            text = outer["result"]
        elif isinstance(outer, dict) and outer.get("verdict"):
            text = json.dumps(outer)
    except json.JSONDecodeError:
        pass
    match = re.search(r"\{[^{}]*\"verdict\"[^{}]*\}", text, re.DOTALL)
    if not match:
        return "unknown", "judge output had no verdict"
    try:
        data = json.loads(match.group(0))
    except json.JSONDecodeError:
        return "unknown", "judge verdict was not valid JSON"
    verdict = str(data.get("verdict", "")).lower()
    return (verdict if verdict in VERDICTS else "unknown"), str(data.get("reason", ""))


def cache_key(model: str, criterion: str, reply: str, vote: int) -> str:
    digest = hashlib.sha256(json.dumps([model, criterion, reply, vote]).encode("utf-8")).hexdigest()
    return digest[:24]


class CommandJudge:
    """Runs the configured judge command on the host with the prompt on stdin (judge.where: host)."""

    def __init__(self, command: list[str], model: str, votes: int = 3, timeout: int = 180,
                 runner: Callable[..., Any] = subprocess.run):
        self.command = [part.replace("{model}", model) for part in command]
        self.model = model
        self.votes = votes
        self.timeout = timeout
        self._run = runner

    def vote(self, prompt: str) -> tuple[str, str]:
        try:
            result = self._run(self.command, input=prompt, capture_output=True, text=True, timeout=self.timeout)
        except (OSError, subprocess.TimeoutExpired) as exc:
            return "unknown", f"{JUDGE_ERROR}{exc}"
        if result.returncode != 0:
            return "unknown", f"{JUDGE_ERROR}judge exited {result.returncode}: {result.stderr.strip()[:200]}"
        return parse_verdict(result.stdout)


def decide(criterion: str, reply: str, judge: Any, cache: dict[str, Any]) -> dict[str, Any]:
    """Majority of judge votes; ties and unknown majorities are 'unknown'. Cached by content."""
    prompt = build_prompt(criterion, reply)
    votes = []
    for vote in range(judge.votes):
        key = cache_key(judge.model, criterion, reply, vote)
        if key in cache:
            votes.append(cache[key])
            continue
        collect = getattr(judge, "collect", None)
        if collect is not None:
            collect.append((key, prompt))
            votes.append({"verdict": "unknown", "reason": JUDGE_ERROR + "pending"})
            continue
        verdict, reason = judge.vote(prompt)
        result = {"verdict": verdict, "reason": reason}
        if not reason.startswith(JUDGE_ERROR):
            cache[key] = result
        votes.append(result)
    counts = {v: sum(1 for x in votes if x["verdict"] == v) for v in VERDICTS}
    majority = max(VERDICTS, key=lambda v: (counts[v], v == "unknown"))
    if counts[majority] * 2 <= len(votes):
        majority = "unknown"
    return {"verdict": majority, "votes": votes, "model": judge.model}


class Collector:
    """Stands in for a judge during a first scoring pass and records every uncached vote."""

    def __init__(self, judge: Any):
        self.model = judge.model
        self.votes = judge.votes
        self.collect: list[tuple[str, str]] = []


def prefetch(pending: list[tuple[str, str]], judge: Any, cache: dict[str, Any], save: Callable[[], None],
             parallel: int = 4, out: Any = None) -> None:
    """Cast the pending votes concurrently, saving the cache as votes arrive and on interrupt."""
    out = out if out is not None else sys.stderr
    unique = list(dict(pending).items())
    if not unique:
        return
    total = len(unique)
    print(f"judge: {total} vote(s) to cast, {parallel} at a time", file=out, flush=True)
    done = failed = 0
    try:
        with concurrent.futures.ThreadPoolExecutor(max_workers=max(1, parallel)) as pool:
            futures = {pool.submit(judge.vote, prompt): key for key, prompt in unique}
            for future in concurrent.futures.as_completed(futures):
                verdict, reason = future.result()
                done += 1
                if reason.startswith(JUDGE_ERROR):
                    failed += 1
                else:
                    cache[futures[future]] = {"verdict": verdict, "reason": reason}
                if done % 10 == 0 or done == total:
                    save()
                    print(f"judge: {done}/{total} votes" + (f" ({failed} failed)" if failed else ""), file=out, flush=True)
    finally:
        save()

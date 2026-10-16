"""Small, dependency-free statistics for paired skill comparisons."""

from __future__ import annotations

import math
import random
from typing import Sequence


def wilson(successes: int, n: int, z: float = 1.96) -> tuple[float, float] | None:
    if n <= 0:
        return None
    p = successes / n
    denom = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / denom
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / denom
    return max(0.0, centre - half), min(1.0, centre + half)


def mean(values: Sequence[float]) -> float | None:
    return sum(values) / len(values) if values else None


def paired_difference(per_case: dict[str, tuple[Sequence[float], Sequence[float]]], resamples: int = 2000,
                      seed: int = 0, level: float = 0.95) -> dict[str, object] | None:
    """Mean over cases of (rate_a - rate_b), with a case-level cluster bootstrap interval.

    Each case contributes its own pass rate in each arm, so repeats of one prompt are
    never treated as independent observations.
    """
    diffs = []
    for runs_a, runs_b in per_case.values():
        if runs_a and runs_b:
            diffs.append(sum(runs_a) / len(runs_a) - sum(runs_b) / len(runs_b))
    if not diffs:
        return None
    estimate = sum(diffs) / len(diffs)
    result: dict[str, object] = {
        "estimate": estimate, "cases": len(diffs),
        "improved": sum(1 for d in diffs if d > 0), "regressed": sum(1 for d in diffs if d < 0),
        "interval": None,
    }
    if len(diffs) >= 2:
        rng = random.Random(seed)
        boots = sorted(
            sum(rng.choice(diffs) for _ in diffs) / len(diffs) for _ in range(resamples)
        )
        alpha = (1 - level) / 2
        result["interval"] = (boots[int(alpha * resamples)], boots[min(resamples - 1, int((1 - alpha) * resamples))])
    return result


def pass_hat_k(per_case: dict[str, Sequence[bool]]) -> float | None:
    """Share of cases where every repeat succeeded (pass^k)."""
    cases = [runs for runs in per_case.values() if runs]
    if not cases:
        return None
    return sum(1 for runs in cases if all(runs)) / len(cases)


def cohen_kappa(a: Sequence[str], b: Sequence[str]) -> float | None:
    if len(a) != len(b) or not a:
        return None
    labels = sorted(set(a) | set(b))
    n = len(a)
    observed = sum(1 for x, y in zip(a, b) if x == y) / n
    expected = sum((sum(1 for x in a if x == label) / n) * (sum(1 for y in b if y == label) / n) for label in labels)
    if expected == 1:
        return 1.0
    return (observed - expected) / (1 - expected)

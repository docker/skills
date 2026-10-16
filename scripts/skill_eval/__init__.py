"""Live skill evaluation harness: specs, runner, scorer, and report.

The spec validator, event parsers, scorer, and statistics are deterministic
and run offline in ``task ci``. Only the runner talks to ``sbx`` and agent
CLIs, and only when a maintainer starts it with ``task eval:live``.
"""

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
EVALS_DIR = REPO_ROOT / "evals"
SPECS_DIR = EVALS_DIR / "specs"
CONFIG_FILE = EVALS_DIR / "live.yaml"
RESULTS_DIR = EVALS_DIR / "results"

AGENTS = ("claude-code", "codex")

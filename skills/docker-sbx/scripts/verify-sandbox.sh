#!/usr/bin/env bash
# Verify sbx sandbox prerequisites on the host.
# Usage: bash scripts/verify-sandbox.sh [--help]
set -euo pipefail

if [[ "${1:-}" == "--help" ]]; then
    echo "Usage: bash scripts/verify-sandbox.sh"
    echo "Checks: sbx binary on PATH, sbx daemon status."
    echo "Note: sbx runs sandboxes via its own VM runtime; a host Docker engine is NOT required."
    exit 0
fi

echo "Checking sbx CLI..."
if command -v sbx >/dev/null 2>&1; then
    echo "OK: sbx found at $(command -v sbx)"
    sbx version 2>/dev/null | head -n1 || true
else
    echo "MISSING: sbx not on PATH. Install per https://github.com/docker/sandboxes"
    exit 1
fi

echo ""
echo "Checking sbx daemon..."
if sbx daemon status >/dev/null 2>&1; then
    echo "OK: sbx daemon running"
else
    echo "INFO: sbx daemon not running. It will auto-start on first sandbox command,"
    echo "      or start it manually with: sbx daemon start -d"
fi

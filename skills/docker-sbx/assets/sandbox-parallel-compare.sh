#!/usr/bin/env bash
# Run two agents in parallel on the same workspace using --app-name isolation,
# so their daemons, state, sockets, caches, and secret stores do not collide.
# Usage: bash sandbox-parallel-compare.sh [WORKSPACE_PATH]
set -euo pipefail

WORKSPACE="${1:-.}"

# --app-name is a hidden global flag that fully isolates an sbx instance.
# Use it only when you genuinely need multiple coexisting instances on the
# same host. Each instance has its own daemon socket and storage.
sbx --app-name compare-claude create claude "$WORKSPACE" --name claude-cmp
sbx --app-name compare-gemini create gemini "$WORKSPACE" --name gemini-cmp

echo "Attach to each sandbox in a separate terminal:"
echo "  sbx --app-name compare-claude run --name claude-cmp"
echo "  sbx --app-name compare-gemini run --name gemini-cmp"
echo ""
echo "Clean up each isolated instance individually:"
echo "  sbx --app-name compare-claude reset --force"
echo "  sbx --app-name compare-gemini reset --force"

#!/usr/bin/env bash
# Provision a Claude sandbox for a Go monorepo that pulls private modules.
# Usage: bash sandbox-bootstrap-claude-go.sh [WORKSPACE_PATH]
#
# SECURITY: do NOT run this script with `bash -x` or after `set -x` — shell
# tracing prints expanded credential values to stderr, which is typically
# captured in CI logs. The block below suppresses tracing around the secret
# injection in case the caller has it enabled.
set -euo pipefail

WORKSPACE="${1:-.}"
SANDBOX_NAME="claude-go-$(basename "$(realpath "$WORKSPACE")")"

# Provision Anthropic credentials once on the host, outside this script:
#   printf '%s' "$ANTHROPIC_API_KEY" | sbx secret set -g anthropic
# (--password-stdin is only valid with --registry; for service secrets,
# the bare pipe with no flag is the secure non-interactive form.)
# This script assumes that has already been done.

# Inject the GitHub token into the global secret store so private Go modules
# (e.g., GOPRIVATE=github.com/org/*) can resolve. The token is read from the
# host environment and stored in the OS keychain, never written to disk here.
if [[ -n "${GH_TOKEN:-}" ]]; then
    { set +x; } 2>/dev/null   # suppress trace around credential handling
    printf '%s' "$GH_TOKEN" | sbx secret set -g github
fi

# Bump memory for Go module compilation in a large monorepo. The default
# (50% of host RAM) is often fine, but explicit is safer on shared machines.
sbx create claude "$WORKSPACE" \
    --name "$SANDBOX_NAME" \
    --memory 8g \
    --cpus 4

sbx run --name "$SANDBOX_NAME"

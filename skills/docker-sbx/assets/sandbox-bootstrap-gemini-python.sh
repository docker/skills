#!/usr/bin/env bash
# Provision a Gemini sandbox for a Python data-science project with a
# read-only dataset mount.
# Usage: bash sandbox-bootstrap-gemini-python.sh PROJECT_PATH DATASET_PATH
#
# SECURITY: do NOT run this script with `bash -x` or after `set -x` — shell
# tracing prints expanded credential values to stderr, which is typically
# captured in CI logs.
set -euo pipefail

PROJECT="${1:?project path required}"
DATASET="${2:?dataset path required}"
SANDBOX_NAME="gemini-$(basename "$(realpath "$PROJECT")")"

# Inject the Gemini API key into the global secret store. The key is read from
# the host environment and stored in the OS keychain, never written to disk here.
if [[ -n "${GEMINI_API_KEY:-}" ]]; then
    { set +x; } 2>/dev/null   # suppress trace around credential handling
    printf '%s' "$GEMINI_API_KEY" | sbx secret set -g gemini
fi

# Mount the project read-write and the dataset read-only. The :ro suffix
# guarantees the agent cannot modify the dataset, which is critical for
# reproducibility and for shared datasets.
sbx create gemini "$PROJECT" "$DATASET:ro" \
    --name "$SANDBOX_NAME" \
    --memory 16g

sbx run --name "$SANDBOX_NAME"

#!/usr/bin/env bash
# Verify Compose configuration. Run from the project root.
# Usage: bash scripts/verify-compose.sh [--help]
set -euo pipefail

if [[ "${1:-}" == "--help" ]]; then
    echo "Usage: bash scripts/verify-compose.sh"
    echo "Validates compose.yaml with docker compose config."
    exit 0
fi

docker compose config

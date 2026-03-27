#!/usr/bin/env bash
# Verify Docker project setup. Run from the project root.
# Usage: bash scripts/verify-setup.sh [--help]
set -euo pipefail

if [[ "${1:-}" == "--help" ]]; then
    echo "Usage: bash scripts/verify-setup.sh"
    echo "Checks: .dockerignore, Dockerfile, and compose.yaml exist; compose config passes."
    exit 0
fi

echo "Checking required files..."
test -f .dockerignore && echo "OK: .dockerignore" || echo "MISSING: .dockerignore"
test -f Dockerfile && echo "OK: Dockerfile" || echo "MISSING: Dockerfile"
test -f compose.yaml && echo "OK: compose.yaml" || echo "MISSING: compose.yaml"

echo ""
echo "Validating compose.yaml..."
docker compose config --quiet && echo "OK: compose config valid" || echo "FAIL: compose config invalid"

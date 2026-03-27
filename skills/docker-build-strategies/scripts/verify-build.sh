#!/usr/bin/env bash
# Verify Dockerfile build. Run from the project root.
# Usage: bash scripts/verify-build.sh [--help] [--image NAME]
set -euo pipefail

IMAGE="${1:-verify-build-test}"

if [[ "$IMAGE" == "--help" ]]; then
    echo "Usage: bash scripts/verify-build.sh [IMAGE_NAME]"
    echo "Builds the Dockerfile, then checks non-root user and image size."
    exit 0
fi

echo "Building image..."
docker build -t "$IMAGE" .

echo ""
echo "Image size:"
docker images "$IMAGE" --format "table {{.Repository}}\t{{.Tag}}\t{{.Size}}"

echo ""
echo "User:"
docker inspect "$IMAGE" --format '{{.Config.User}}'

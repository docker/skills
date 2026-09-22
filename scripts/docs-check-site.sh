#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

output=$(mktemp -d)
cleanup() {
  rm -rf "$output"
}
trap cleanup EXIT

docker build -t docker-skills-docs docs
docker run --rm \
  -v "$PWD/docs:/src:ro" \
  -v "$output:/output" \
  docker-skills-docs \
  hugo --source /src --destination /output --cacheDir /tmp/hugo-cache --noBuildLock --panicOnWarning
docker run --rm \
  -v "$PWD:/work" \
  -v "$output:/output:ro" \
  -w /work \
  python@sha256:739e7213785e88c0f702dcdc12c0973afcbd606dbf021a589cab77d6b00b579d \
  sh -c "pip install -q --require-hashes -r scripts/requirements.txt && python3 scripts/docs_check.py --built-output /output"

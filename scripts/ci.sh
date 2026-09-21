#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PYTHON_IMAGE="python@sha256:739e7213785e88c0f702dcdc12c0973afcbd606dbf021a589cab77d6b00b579d"
DOCKER_SOCKET="${DOCKER_SOCKET:-/var/run/docker.sock}"

if [[ ! -S "$DOCKER_SOCKET" ]]; then
    echo "Docker socket not found at $DOCKER_SOCKET" >&2
    exit 1
fi

docker run --rm \
    -v "$REPO_ROOT:/work" \
    -v "$DOCKER_SOCKET:/var/run/docker.sock" \
    -w /work \
    "$PYTHON_IMAGE" \
    sh -euc '
        apt-get update -qq
        DEBIAN_FRONTEND=noninteractive apt-get install -qq --no-install-recommends \
            docker-cli=26.1.5+dfsg1-9+deb13u1 \
            docker-compose=2.26.1-4 >/dev/null
        pip install -q pyyaml
        python3 -m unittest discover -s scripts -p "test_*.py"
        python3 scripts/validate.py
        python3 scripts/eval_check.py
        python3 scripts/check_links.py
        bash tests/scripts/test_verify_scripts.sh
    '

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
    -e RELEASE_TAG="${RELEASE_TAG:-}" \
    -e VALIDATION_HEAD_SHA="${VALIDATION_HEAD_SHA:-HEAD}" \
    -e VERSION_CHECK_BASE_SHA="${VERSION_CHECK_BASE_SHA:-}" \
    -v "$REPO_ROOT:/work" \
    -v "$REPO_ROOT/.git:/work/.git:ro" \
    -v "$DOCKER_SOCKET:/var/run/docker.sock" \
    -w /work \
    "$PYTHON_IMAGE" \
    sh -euc '
        apt-get update -qq
        DEBIAN_FRONTEND=noninteractive apt-get install -qq --no-install-recommends \
            docker-cli=26.1.5+dfsg1-9+deb13u1 \
            docker-compose=2.26.1-4 \
            git=1:2.47.3-0+deb13u1 >/dev/null
        pip install -q --require-hashes -r scripts/requirements.txt
        python3 -m unittest discover -s scripts -p "test_*.py"
        python3 scripts/render_catalog.py --check
        python3 scripts/validate.py
        python3 scripts/check_version_bumps.py "${VERSION_CHECK_BASE_SHA:-}" --head "${VALIDATION_HEAD_SHA:-HEAD}"
        python3 scripts/check_dco.py "${VERSION_CHECK_BASE_SHA:-}" --head "${VALIDATION_HEAD_SHA:-HEAD}"
        if [ -n "$RELEASE_TAG" ]; then
            python3 scripts/check_release_tag.py "$RELEASE_TAG"
        fi
        python3 scripts/eval_check.py
        python3 scripts/check_links.py
        bash tests/scripts/test_verify_scripts.sh
    '

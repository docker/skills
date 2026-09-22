#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
PROJECT_SCRIPT="$REPO_ROOT/skills/docker-project-foundations/scripts/verify-setup.sh"
BUILD_SCRIPT="$REPO_ROOT/skills/docker-build-strategies/scripts/verify-build.sh"
COMPOSE_SCRIPT="$REPO_ROOT/skills/docker-compose-patterns/scripts/verify-compose.sh"
TMP_DIR="$(mktemp -d)"
IMAGE="verify-build-script-test-$$"

cleanup() {
    docker image rm -f "$IMAGE" >/dev/null 2>&1 || true
    rm -rf "$TMP_DIR"
}
trap cleanup EXIT

assert_status() {
    local expected="$1"
    local description="$2"
    shift 2

    local actual=0
    "$@" >"$TMP_DIR/output" 2>&1 || actual=$?
    if [[ "$expected" == "nonzero" ]]; then
        if (( actual == 0 )); then
            echo "FAIL: $description (expected non-zero, got 0)" >&2
            cat "$TMP_DIR/output" >&2
            exit 1
        fi
    elif (( actual != expected )); then
        echo "FAIL: $description (expected $expected, got $actual)" >&2
        cat "$TMP_DIR/output" >&2
        exit 1
    fi
    echo "PASS: $description"
}

assert_help() {
    local script="$1"
    local usage="$2"

    assert_status 0 "$(basename "$script") --help exits zero" "$script" --help
    if ! grep -Fq "$usage" "$TMP_DIR/output"; then
        echo "FAIL: $(basename "$script") --help does not show documented usage" >&2
        cat "$TMP_DIR/output" >&2
        exit 1
    fi
}

mkdir -p "$TMP_DIR/project-valid" "$TMP_DIR/project-missing-dockerignore" "$TMP_DIR/project-missing-dockerfile" "$TMP_DIR/project-missing-compose" "$TMP_DIR/project-invalid"
touch "$TMP_DIR/project-valid/.dockerignore" "$TMP_DIR/project-valid/Dockerfile"
cat >"$TMP_DIR/project-valid/compose.yaml" <<'YAML'
services:
  app:
    image: busybox:1.36
YAML

cp "$TMP_DIR/project-valid/Dockerfile" "$TMP_DIR/project-missing-dockerignore/Dockerfile"
cp "$TMP_DIR/project-valid/compose.yaml" "$TMP_DIR/project-missing-dockerignore/compose.yaml"

cp "$TMP_DIR/project-valid/.dockerignore" "$TMP_DIR/project-missing-dockerfile/.dockerignore"
cp "$TMP_DIR/project-valid/compose.yaml" "$TMP_DIR/project-missing-dockerfile/compose.yaml"

cp "$TMP_DIR/project-valid/.dockerignore" "$TMP_DIR/project-missing-compose/.dockerignore"
cp "$TMP_DIR/project-valid/Dockerfile" "$TMP_DIR/project-missing-compose/Dockerfile"

touch "$TMP_DIR/project-invalid/.dockerignore" "$TMP_DIR/project-invalid/Dockerfile"
cat >"$TMP_DIR/project-invalid/compose.yaml" <<'YAML'
services:
  app:
    image: [invalid
YAML

# Positional parameters intentionally expand in each child shell.
# shellcheck disable=SC2016
assert_status 0 "verify-setup accepts a valid project" bash -c 'cd "$1" && "$2"' _ "$TMP_DIR/project-valid" "$PROJECT_SCRIPT"
# shellcheck disable=SC2016
assert_status 1 "verify-setup rejects a missing .dockerignore" bash -c 'cd "$1" && "$2"' _ "$TMP_DIR/project-missing-dockerignore" "$PROJECT_SCRIPT"
# shellcheck disable=SC2016
assert_status 1 "verify-setup rejects a missing Dockerfile" bash -c 'cd "$1" && "$2"' _ "$TMP_DIR/project-missing-dockerfile" "$PROJECT_SCRIPT"
# shellcheck disable=SC2016
assert_status 1 "verify-setup rejects a missing compose.yaml" bash -c 'cd "$1" && "$2"' _ "$TMP_DIR/project-missing-compose" "$PROJECT_SCRIPT"
# shellcheck disable=SC2016
assert_status 1 "verify-setup rejects invalid Compose configuration" bash -c 'cd "$1" && "$2"' _ "$TMP_DIR/project-invalid" "$PROJECT_SCRIPT"
assert_help "$PROJECT_SCRIPT" "Usage: bash scripts/verify-setup.sh [--help]"
assert_status 2 "verify-setup rejects invalid arguments" "$PROJECT_SCRIPT" unexpected

mkdir -p "$TMP_DIR/build-valid" "$TMP_DIR/build-missing"
cat >"$TMP_DIR/build-valid/Dockerfile" <<'DOCKERFILE'
FROM scratch
USER 65532:65532
DOCKERFILE

# shellcheck disable=SC2016
assert_status 0 "verify-build accepts a valid Dockerfile" bash -c 'cd "$1" && "$2" "$3"' _ "$TMP_DIR/build-valid" "$BUILD_SCRIPT" "$IMAGE"
# shellcheck disable=SC2016
assert_status nonzero "verify-build propagates a failed build" bash -c 'cd "$1" && "$2" "$3"' _ "$TMP_DIR/build-missing" "$BUILD_SCRIPT" "$IMAGE"
assert_help "$BUILD_SCRIPT" "Usage: bash scripts/verify-build.sh [--help] [IMAGE_NAME]"
assert_status 2 "verify-build rejects invalid arguments" "$BUILD_SCRIPT" image-one image-two

mkdir -p "$TMP_DIR/compose-valid" "$TMP_DIR/compose-invalid"
cp "$TMP_DIR/project-valid/compose.yaml" "$TMP_DIR/compose-valid/compose.yaml"
cp "$TMP_DIR/project-invalid/compose.yaml" "$TMP_DIR/compose-invalid/compose.yaml"

# shellcheck disable=SC2016
assert_status 0 "verify-compose accepts valid Compose configuration" bash -c 'cd "$1" && "$2"' _ "$TMP_DIR/compose-valid" "$COMPOSE_SCRIPT"

mkdir -p "$TMP_DIR/compose-credentials"
cat >"$TMP_DIR/compose-credentials/compose.yaml" <<'YAML'
services:
  app:
    image: busybox:1.36
    environment:
      PASSWORD: ${VERIFY_COMPOSE_TEST_PASSWORD:?Set the test password}
    env_file: runtime.env
YAML
printf '%s\n' 'VERIFY_COMPOSE_TEST_PASSWORD=synthetic-interpolation-canary' >"$TMP_DIR/compose-credentials/.env"
printf '%s\n' 'API_TOKEN=synthetic-env-file-canary' >"$TMP_DIR/compose-credentials/runtime.env"

# shellcheck disable=SC2016
assert_status 0 "verify-compose validates interpolated and env_file credentials" env -u VERIFY_COMPOSE_TEST_PASSWORD bash -c 'cd "$1" && "$2"' _ "$TMP_DIR/compose-credentials" "$COMPOSE_SCRIPT"
if [[ -s "$TMP_DIR/output" ]]; then
    echo "FAIL: verify-compose printed output for a valid credential-bearing configuration" >&2
    exit 1
fi
echo "PASS: verify-compose does not print resolved credentials"

rm "$TMP_DIR/compose-credentials/runtime.env"
# shellcheck disable=SC2016
assert_status nonzero "verify-compose still rejects a missing env_file" env -u VERIFY_COMPOSE_TEST_PASSWORD bash -c 'cd "$1" && "$2"' _ "$TMP_DIR/compose-credentials" "$COMPOSE_SCRIPT"

# shellcheck disable=SC2016
assert_status nonzero "verify-compose propagates invalid Compose configuration" bash -c 'cd "$1" && "$2"' _ "$TMP_DIR/compose-invalid" "$COMPOSE_SCRIPT"
if [[ ! -s "$TMP_DIR/output" ]]; then
    echo "FAIL: verify-compose suppressed validation diagnostics" >&2
    exit 1
fi
echo "PASS: verify-compose preserves validation diagnostics"
assert_help "$COMPOSE_SCRIPT" "Usage: bash scripts/verify-compose.sh [--help]"
assert_status 2 "verify-compose rejects invalid arguments" "$COMPOSE_SCRIPT" unexpected

echo "All verification script tests passed."

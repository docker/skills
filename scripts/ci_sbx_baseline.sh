#!/usr/bin/env bash
# Bring Docker Sandboxes (sbx) to the CI eval baseline: logged in, balanced policy.
#
#   scripts/ci_sbx_baseline.sh           # initial setup
#   scripts/ci_sbx_baseline.sh --reset   # wipe all sbx state first (before an eval retry)
#
# --reset runs `sbx reset --force`, which removes every sandbox, MCP registration,
# secret and policy and signs out, so a retry never sees a previous attempt's
# leftovers whatever the scenario did. CI runners are disposable; never run
# --reset on a machine with sandboxes you care about.
#
# Needs DOCKERPUBLICBOT_USERNAME and DOCKERPUBLICBOT_READ_PAT in the environment.
set -euo pipefail

: "${DOCKERPUBLICBOT_USERNAME:?}" "${DOCKERPUBLICBOT_READ_PAT:?}"

if [ "${1:-}" = "--reset" ]; then
  if [ "${CI:-}" != "true" ]; then
    echo "refusing to run 'sbx reset' outside CI" >&2
    exit 1
  fi
  sg kvm -c 'sbx reset --force'
fi

sg kvm -c 'echo "$DOCKERPUBLICBOT_READ_PAT" | sbx login --username "$DOCKERPUBLICBOT_USERNAME" --password-stdin'
sg kvm -c 'sbx policy init balanced'

#!/usr/bin/env bash
# Detect whether the active docker context is served by Docker Desktop.
#
# Algorithm (identical to detect-desktop.ps1 — only the platform data
# differs; both implement references/platform-signals.md):
#   1. Note DOCKER_HOST (overrides context selection; still capture context
#      name/description as info).
#   2. Resolve the current context: name, description, docker endpoint.
#   3. Authoritative: `docker info --format '{{.OperatingSystem}}'` ==
#      "Docker Desktop" -> positive; "Container Platform" -> explicitly NOT
#      Desktop (sibling product); anything else -> another runtime, name it.
#   4. Corroborate (informational only, never gates the verdict): Name
#      (shared hostname, not proof by itself); KernelVersion suffix
#      identifies the backend (-linuxkit = VM backend on macOS/Linux/
#      Windows-Hyper-V; -microsoft-standard-WSL2 = WSL2 backend). Neither
#      suffix while OperatingSystem=Docker Desktop is an anomaly.
#   5. Daemon unreachable -> classify by context name, socket endpoint, and
#      context description, using platform-specific paths (macOS vs Linux).
#   6. Installation markers (tie-breakers only — "installed != serving"):
#      `docker desktop version`, and per-OS marker directories/files.
#
# Data source: source-verified against Docker Desktop 4.85 (pre-GA); see
# references/platform-signals.md for the full signals table this implements.
#
# Read-only: only `docker context inspect`, `docker context ls`,
# `docker info`, `docker desktop version`, and filesystem/symlink reads.
# Never starts, stops, restarts, updates, enables, disables, or diagnoses
# Docker Desktop, and never touches the engine (no pulls, no container runs).
#
# Usage: bash scripts/detect-desktop.sh
#
# Exit codes:
#   0 = Docker Desktop, verified and serving the current context
#   1 = daemon reachable but confirmed NOT Docker Desktop
#   2 = Docker Desktop installed but daemon unreachable (offer
#       `docker desktop start` as a choice; never run it here)
#   3 = indeterminate (unsupported OS, or no signal was conclusive)
set -uo pipefail

OS="$(uname)"
case "$OS" in
    Darwin|Linux) ;;
    *)
        echo "unsupported OS ($OS) for this script — use scripts/detect-desktop.ps1 on Windows"
        exit 3
        ;;
esac

# Step 1: note DOCKER_HOST — it overrides context selection entirely.
if [[ -n "${DOCKER_HOST:-}" ]]; then
    echo "DOCKER_HOST is set: $DOCKER_HOST (overrides context selection)"
fi

# Step 2: resolve the current context. Never enumerate installed software
# instead — multiple contexts/runtimes routinely coexist.
CONTEXT_NAME="$(docker context inspect --format '{{.Name}}' 2>/dev/null || true)"
SOCKET_HOST="$(docker context inspect --format '{{.Endpoints.docker.Host}}' 2>/dev/null || true)"
CONTEXT_DESC="$(docker context inspect --format '{{.Metadata.Metadata.Description}}' 2>/dev/null || true)"
echo "context: ${CONTEXT_NAME:-unknown} (${SOCKET_HOST:-unknown endpoint})"
if [[ -n "$CONTEXT_DESC" ]]; then
    echo "context description: $CONTEXT_DESC"
fi

# Step 3: ask the daemon — authoritative signal, from whatever endpoint the
# current context actually reaches.
OS_ID="$(docker info --format '{{.OperatingSystem}}' 2>/dev/null || true)"

if [[ -n "$OS_ID" ]]; then
    if [[ "$OS_ID" == "Docker Desktop" ]]; then
        # Step 4: corroborate — informational only, never gates the verdict.
        NAME="$(docker info --format '{{.Name}}' 2>/dev/null || true)"
        KERNEL="$(docker info --format '{{.KernelVersion}}' 2>/dev/null || true)"
        echo "runtime: Docker Desktop (verified via docker info)"
        echo "corroborated: Name=$NAME (shared hostname, not proof on its own)"
        case "$KERNEL" in
            *-linuxkit)
                echo "backend: VM backend (KernelVersion=$KERNEL)"
                ;;
            *-microsoft-standard-WSL2)
                echo "backend: WSL2 backend (KernelVersion=$KERNEL)"
                ;;
            *)
                echo "anomaly: OperatingSystem=Docker Desktop but KernelVersion ($KERNEL) has neither expected suffix"
                ;;
        esac
        exit 0
    fi
    if [[ "$OS_ID" == "Container Platform" ]]; then
        echo "runtime: NOT Docker Desktop — Container Platform is a sibling product, not Desktop"
        exit 1
    fi
    echo "runtime: NOT Docker Desktop — skill does not apply (OperatingSystem=$OS_ID)"
    exit 1
fi

# Step 5: daemon unreachable (e.g. Desktop stopped) — fall back to
# classification by context name / socket path. Platform-specific data only;
# the logic shape is identical to detect-desktop.ps1.
echo "daemon unreachable via current context; falling back to context/socket classification"

SOCKET_PATH="${SOCKET_HOST#unix://}"
LOOKS_LIKE_DESKTOP=0
MARKER_DIR_OK=0

if [[ "$OS" == "Darwin" ]]; then
    if [[ "$SOCKET_PATH" == "/var/run/docker.sock" && -L "$SOCKET_PATH" ]]; then
        TARGET="$(readlink "$SOCKET_PATH")"
        echo "note: /var/run/docker.sock is a symlink -> $TARGET (target discriminates, not the presence; Colima/podman also symlink it)"
        SOCKET_PATH="$TARGET"
    fi
    if [[ "$CONTEXT_NAME" == "desktop-linux" || "$SOCKET_PATH" == *"/.docker/run/docker.sock" ]]; then
        LOOKS_LIKE_DESKTOP=1
    fi
    [[ -d "$HOME/Library/Group Containers/group.com.docker" ]] && MARKER_DIR_OK=1
else
    # Linux: a socket at /var/run/docker.sock is NEVER Desktop.
    if [[ "$SOCKET_PATH" == "/var/run/docker.sock" ]]; then
        if [[ -L "$SOCKET_PATH" ]]; then
            TARGET="$(readlink "$SOCKET_PATH")"
            echo "note: /var/run/docker.sock is a symlink -> $TARGET (likely native Engine or podman-docker; never Desktop on Linux)"
        else
            echo "note: /var/run/docker.sock endpoint — likely native Engine (never Desktop on Linux)"
        fi
    fi
    if [[ "$CONTEXT_NAME" == "desktop-linux" || "$SOCKET_PATH" == *"/.docker/desktop/docker.sock" ]]; then
        LOOKS_LIKE_DESKTOP=1
    fi
    [[ -d "$HOME/.docker/desktop" || -x "/usr/lib/docker/cli-plugins/docker-desktop" ]] && MARKER_DIR_OK=1
fi

# Context description is a rename-proof corroborator, independent of the
# context name (same signal detect-desktop.ps1 uses).
if [[ "$CONTEXT_DESC" == "Docker Desktop" ]]; then
    echo "note: context description is 'Docker Desktop' — corroborator independent of context name"
    LOOKS_LIKE_DESKTOP=1
fi

# Step 6: installation markers — tie-breakers only. These prove Desktop is
# installed, not that it serves the current context.
DESKTOP_CLI_OK=1
docker desktop version >/dev/null 2>&1 || DESKTOP_CLI_OK=0

if [[ "$DESKTOP_CLI_OK" -eq 1 || "$MARKER_DIR_OK" -eq 1 ]]; then
    echo "installation marker present (installed, not necessarily serving): docker desktop CLI ok=$DESKTOP_CLI_OK, marker dir=$MARKER_DIR_OK"
fi

if [[ "$LOOKS_LIKE_DESKTOP" -eq 1 && ( "$DESKTOP_CLI_OK" -eq 1 || "$MARKER_DIR_OK" -eq 1 ) ]]; then
    echo "verdict: Docker Desktop installed but not running (daemon unreachable) — 'docker desktop start' would start it, your choice"
    exit 2
fi

echo "verdict: undetermined — daemon unreachable and no Docker Desktop markers matched"
exit 3

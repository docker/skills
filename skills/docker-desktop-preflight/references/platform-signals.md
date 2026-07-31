# Docker Desktop Platform Signals

This table is the single source of truth for the identity, context, and socket
signals used to confirm Docker Desktop is the active runtime. Both detection
scripts — `scripts/detect-desktop.sh` (macOS, Linux) and
`scripts/detect-desktop.ps1` (Windows) — implement it directly. Any edit here
must be ported to both scripts in the same change; see `checks/verification.md`
for the parity check to run before shipping a detection-related edit.

Source-verified against Docker Desktop 4.85 (pre-GA); Windows/Linux values not
yet confirmed by live transcript on those hosts.

## Signal table

| Signal | macOS | Linux | Windows, WSL2 | Windows, Hyper-V | Windows, containers mode |
|---|---|---|---|---|---|
| `docker info` OperatingSystem | `Docker Desktop` | `Docker Desktop` | `Docker Desktop` | `Docker Desktop` | Unverified — host-side daemon; treat as indeterminate. |
| `docker info` Name | `docker-desktop`¹ | `docker-desktop`¹ | `docker-desktop`¹ | `docker-desktop`¹ | Unverified — host-side daemon; treat as indeterminate. |
| `docker info` KernelVersion | ends `-linuxkit`² | ends `-linuxkit`² | ends `-microsoft-standard-WSL2`² | ends `-linuxkit`² | Unverified — host-side daemon; treat as indeterminate. |
| Context name | `desktop-linux` | `desktop-linux` | `desktop-linux` | `desktop-linux` | `desktop-windows`³ |
| Context Description | `Docker Desktop`⁴ | `Docker Desktop`⁴ | `Docker Desktop`⁴ | `Docker Desktop`⁴ | `Docker Desktop`⁴ |
| Endpoint | `unix://~/.docker/run/docker.sock` | `unix://~/.docker/desktop/docker.sock`⁵ | `npipe:////./pipe/dockerDesktopLinuxEngine` | `npipe:////./pipe/dockerDesktopLinuxEngine` | `npipe:////./pipe/dockerDesktopWindowsEngine` |
| Ambiguous compatibility pipe | n/a | n/a | `docker_engine`⁶ | `docker_engine`⁶ | `docker_engine`⁶ |
| CLI plugin presence | n/a | `/usr/lib/docker/cli-plugins`⁷ | n/a | n/a | n/a |
| Startup context hijack | yes⁸ | yes⁸ | yes⁸ | yes⁸ | yes⁸ |
| Shutdown restore | no | yes⁹ | no | no | no |

## Notes

1. Not usable alone: a sibling non-Desktop Docker VM product reports
   `Container Platform` in this same field, yet shares the identical
   `docker-desktop` hostname. Corroborate with OperatingSystem and
   KernelVersion, never with Name by itself.
2. Backend discriminator. Neither suffix present is a negative signal, on any
   OS.
3. Only exists once Windows-containers mode has been selected at least once
   on this host. Its absence proves nothing about which mode is active now —
   Linux-containers mode still reports `desktop-linux`.
4. A literal string, independent of the context's own name — a rename-proof
   corroborator: even if a user or script renames the context, this field
   still reads `Docker Desktop`.
5. Never `/var/run/docker.sock` on Linux — Docker Desktop does not create or
   symlink that path there.
6. Also served by Rancher Desktop and Podman under the identical pipe name —
   never treat this pipe as a positive signal alone. `dockerDesktopEngine`
   (no "Linux"/"Windows" in the name) is Docker Desktop's own
   context-following proxy pipe and is a valid positive signal, distinct
   from the ambiguous `docker_engine`.
7. An install marker, not a runtime signal — proves Docker Desktop's CLI
   plugin is installed system-wide, not that it is the active runtime.
8. At startup, Docker Desktop unconditionally switches the current CLI
   context to its active `desktop-*` context, on every OS — except when the
   current context is a Docker Cloud context, which is left untouched. Never
   cache a context across a Docker Desktop start/stop cycle.
9. On shutdown, Docker Desktop resets the current context to the literal
   `default` — but only if the context was `default` immediately before
   Docker Desktop started and is `default` or `desktop-linux` at shutdown; it
   never restores an arbitrary prior context.

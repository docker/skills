---
name: docker-desktop-preflight
description: Use this skill proactively before running a container, build, pull, push, compose, or kubectl action on a host suspected to be running Docker Desktop, and reactively whenever an error suggests Docker Desktop governance is blocking the action — exit code 137, "no space left on device", "mounts denied", any "enhanced container isolation: ..." message, "Access to ... has been restricted by your administrators" (legacy "registry access to ... is not allowed"), "Sign in to continue using Docker Desktop", a missing kubectl docker-desktop context, or a proxy/x509 failure. Covers runtime detection (Desktop vs bare Engine, Colima, Rancher Desktop, Podman), resource limits, Settings Management locks, enforced sign-in, Enhanced Container Isolation, Registry Access Management, file sharing, proxy configuration, and Kubernetes enablement.
license: Apache-2.0
compatibility: macOS-verified baseline; Windows/Linux signals source-verified against Docker Desktop 4.85 (pre-GA), not yet live-verified; assumes Docker Desktop CLI plugin v0.4.1+.
---

# Docker Desktop Preflight

## Overview

This skill helps an agent recognize when it is operating on a host governed by Docker Desktop, diagnose whether the current configuration allows an intended container, build, pull, push, compose, or kubectl action, and respond in line with Docker Desktop's governance rather than around it. It has two entry points: a proactive preflight check run before a container action, and reactive triage of a governance error that already occurred. Reactive triage is usually the higher-value entry point — a full proactive check costs tokens on every container action, while reactive triage runs only when a symptom already points at a governance surface. It never edits governance files, never disables a security feature, and never proposes a workaround for an admin-locked or enforced setting.

Docker Desktop governance is not the only runtime an agent will encounter: bare Engine, Colima, Rancher Desktop, and Podman all exist on the same hosts and do not carry any of these surfaces. Confirming Docker Desktop is the active runtime before reasoning about any of its governance surfaces is the first step of every diagnosis in this skill, not an optional shortcut.

## When to use this skill

Activate this skill when:

- About to run a container, build, pull, push, compose, or kubectl action on a host where Docker Desktop is suspected to be the active runtime.
- An error matches the governance failure inventory: exit code 137, `no space left on device`, `mounts denied` (match case-insensitively) / `cannot start service`, any `enhanced container isolation: ...` message, `Access to <host> has been restricted by your administrators` (legacy: `registry access to <host> is not allowed`), "Sign in to continue using Docker Desktop", a missing or broken kubectl `docker-desktop` context, or a proxy/`x509` failure.
- A GUI setting appears grayed out and the user asks why.
- The user asks whether a resource limit, Kubernetes, or a security feature can be changed programmatically.
- The user asks who can change a setting that appears locked, or whether a policy applies to their organization.

## Do not use this skill when

Do not use this skill when:

- The active runtime is confirmed not to be Docker Desktop (bare Engine, Colima, Rancher Desktop, Podman) and no Desktop-specific symptom is present — see Runtime detection below.
- The failure is a Dockerfile authoring problem (bad `COPY`, missing build stage, wrong base image) rather than a Desktop governance block.
- The failure is a Compose service-wiring problem (dependency ordering, networks, health checks) rather than a Desktop governance block.
- The project has no Docker setup yet and the need is a first-pass scaffold.
- The action already ran successfully — there is nothing to preflight and no error to triage.

## Core guidance

### Governance posture

This skill works **with** Docker Desktop's governance, never around it. When a setting is admin-locked or a policy — Enhanced Container Isolation, Registry Access Management, enforced sign-in — blocks an action, explain what blocked the action and why, state the enforced value when it is readable, and direct the user to their Docker organization administrator. Never edit `admin-settings.json`, never suggest disabling or bypassing a security feature — including via alternate runtimes, DNS/proxy tricks, or signing out — and never exploit a documented enforcement gap. Configuration changes the user is entitled to make are proposed to the user, never silently applied.

### Never run without explicit user consent

The following commands change state, apply updates, or destroy data. Never run any of them proactively — surfacing one as an available option is fine, running it is not, unless the user has explicitly asked for that exact action in that moment:

- `docker desktop start` / `stop` / `restart` — starts or stops a GUI application and VM.
- `docker desktop update` — applies a product update.
- `docker desktop enable model-runner` / `disable model-runner` — the only toggleable feature in the CLI plugin.
- `docker desktop kubernetes reset-cluster` — destructive; deletes existing cluster state.
- `docker desktop diagnose` — writes a diagnostics bundle to disk; the `-u` form additionally uploads it. Never run either without explicit consent, and never `-u` without separately confirming the user wants data uploaded.
- Windows-only: `docker desktop engine use` — switches between Linux-containers and Windows-containers mode; a mode switch, not a read.

### Read-only preflight commands

These commands are always safe to run without asking — they read state, they never change it: every `--help` invocation, `docker desktop version`, `docker desktop status`, `docker desktop kubernetes status`, `docker desktop kubernetes images`, `docker desktop logs`, `docker desktop engine ls` (Windows only — lists the container mode, unlike `engine use` which switches it), `docker info`, `docker version`, `docker context ls` / `inspect`, `kubectl config get-contexts` / `current-context`, and reading (never writing) `settings-store.json` and `admin-settings.json` at their per-OS paths. There is no CLI path to read or write resource limits, Enhanced Container Isolation, Registry Access Management, file sharing, proxies, sign-in state, or Settings Management — those live in the GUI, the two settings files, and the Admin Console. Remediation for most surfaces is therefore "open this GUI panel" or "contact your admin," not a command.

### Runtime detection

Ordered algorithm — do not skip steps or substitute a later one for an earlier one:

1. Resolve the effective endpoint first: check `DOCKER_HOST` (overrides context selection), then `docker context inspect` (no argument = current) for the socket path. Never enumerate installed software instead — multiple runtimes routinely coexist on one host.
2. Ask the daemon: `docker info --format '{{.OperatingSystem}}'` equal to exactly `Docker Desktop`. This is the **sole authoritative signal** — it comes from whatever daemon the current endpoint actually reaches, and no other field overrides it. Exception: in Windows-containers mode this field is answered by a host-side daemon outside Desktop's Linux VM and is not yet confirmed — see the Windows-containers blind spot below.
3. Treat `{{.Name}}` as informational only, never as corroboration by itself: a sibling non-Desktop Docker VM product reports `Container Platform` in this same field while sharing the identical `docker-desktop` hostname, so a match proves nothing on its own. `{{.KernelVersion}}` is the real backend discriminator — accept either `-linuxkit` (macOS, Linux, Windows Hyper-V) or `-microsoft-standard-WSL2` (Windows WSL2) as a positive; neither suffix present is a negative signal.
4. If the daemon is unreachable (Desktop stopped), fall back to classifying by context name and socket path: `desktop-linux` → Docker Desktop; `colima`, `rancher-desktop`, or a path containing `containers/podman` → other runtimes. If the context is `default` with `/var/run/docker.sock`, resolve the symlink target — the target discriminates the runtime, not the symlink's mere presence. On Windows, a `dockerDesktopLinuxEngine` or `dockerDesktopWindowsEngine` named pipe is a strong positive signal; the compatibility pipe `docker_engine` is ambiguous — Rancher Desktop and Podman can serve the identical pipe name, so never treat it as positive alone.
5. Use installation markers only as tie-breakers, never as primary evidence: `docker desktop version` exiting 0 and the presence of Desktop's app directory prove Desktop is *installed*, not that it serves the current context.

Full per-signal detail — every value above plus context Description, per-OS
endpoints, CLI plugin presence, and startup/shutdown context behavior — lives
in `references/platform-signals.md`, the single source of truth both
detection scripts (`scripts/detect-desktop.sh`, `scripts/detect-desktop.ps1`)
implement.

**Windows-containers blind spot:** `docker info` identity fields for
Windows-containers mode are answered by a host-side daemon whose values are
not yet confirmed. Treat this mode as indeterminate — never assert Desktop is
or is not the active runtime there; report it as unresolved and point to
`references/platform-signals.md` for the manual checks instead.

Traps that apply regardless of OS: never infer the active runtime from what is *installed* rather than what the current endpoint actually answers with; a `/var/run/docker.sock` symlink can point into Docker Desktop, Colima, or podman-mac-helper — resolve the target, the presence of the symlink proves nothing. On every OS, Desktop unconditionally switches the current CLI context to its active `desktop-*` context at startup — except when the current context is a Docker Cloud context, which is left untouched — so never cache a context across a Desktop start/stop cycle. On Windows, a `desktop-windows` context only exists once Windows-containers mode has been selected at least once on that host; its absence says nothing about which mode is active now.

### Decision rules

**D1 — Desktop is installed but not running.** Report this, and offer `docker desktop start` as an explicit choice for the user to run. Never start it automatically — it is a GUI app and VM with a 10–60 second startup cost and host resource impact.

**D2 — A resource or setting change would unblock the task.** Propose the specific change (which GUI panel, which file, what value) to the user. Never apply it yourself, whether by editing `settings-store.json`, editing `.wslconfig`, or any other file write — even when the setting is unlocked and the user would be entitled to make the change themselves.

**D3 — A setting is admin-locked.** State the enforced value when it is readable from `admin-settings.json`, then direct the user to their Docker organization administrator. Do not propose a workaround of any kind.

### Known limitations to disclose

Some surfaces cannot be checked locally at all. Disclose these rather than implying a clean preflight check guarantees success:

- **Admin Console (Docker Home) policy enrollment** can enforce settings with zero local artifact. A missing `admin-settings.json` means "no local lock evidence found," never "unmanaged."
- **The Registry Access Management allowlist is never exposed client-side.** The only way to learn a registry is blocked is to hit the error when a pull, push, or build reaches it.
- **Docker Scout org policy status** requires a network call to the Scout platform; it cannot be checked offline.
- **Disk and swap limits have no supported read interface** — only heuristics (Docker.raw apparent-vs-actual size) or an undocumented `docker desktop logs` dump, both best-effort.
- **No surface names the admin or org that locked a setting.** The only available remediation phrasing is "contact your Docker organization administrator."

### Symptom index

No remediation prose in this table — follow the reference pointer for detection detail and wording.

| Symptom | Surface | Reference |
|---|---|---|
| Container/build killed, exit 137 | VM memory limit | `references/resources.md` |
| `no space left on device` | VM disk limit | `references/resources.md` |
| Slow builds, no error | CPU allocation or file-sharing implementation | `references/resources.md`, `references/mounts-and-network.md` |
| `docker` CLI can't reach daemon, Desktop installed | Desktop stopped — or the engine held at boot by admin-settings.json-presence / Enhanced Container Isolation sign-in enforcement | Runtime detection above, `references/governance.md` |
| `docker info`/`version` succeed but `run`/`pull`/`push`/`build` fail with HTTP 407 "Sign in to continue using Docker Desktop" | Enforced sign-in (org-list mechanisms — the engine is running; do NOT diagnose as Desktop-stopped) | `references/governance.md` |
| "Sign in required!" (GUI) | Enforced sign-in | `references/governance.md` |
| GUI setting grayed out | Settings Management lock | `references/governance.md` |
| `enhanced container isolation: docker socket mount denied ...` | ECI socket-mount allowlist | `references/isolation.md` |
| `enhanced container isolation: docker command ... is blocked` | ECI command list | `references/isolation.md` |
| `sysbox containers can't share namespaces ... with the host` | ECI vs `--pid`/`--network=host` | `references/isolation.md` |
| `... restricted host mount ...` | ECI VM-path protection | `references/isolation.md` |
| `--privileged` runs but kernel ops fail with `EPERM` | ECI confinement | `references/isolation.md` |
| `Access to <host> has been restricted by your administrators` (legacy: `registry access to <host> is not allowed`) | Registry Access Management | `references/registry-access.md` |
| Manifest pulls OK, blob downloads fail | Registry Access Management redirect domains | `references/registry-access.md` |
| CI fails with Scout exit code 2 | Opt-in Scout CI gate (not local) | `references/registry-access.md` |
| `mounts denied` (lowercase in current Desktop; match case-insensitively) / `cannot start service` | File sharing paths | `references/mounts-and-network.md` |
| Pull timeouts behind a corporate network | Containers proxy configuration | `references/mounts-and-network.md` |
| `x509: certificate signed by unknown authority` | TLS-intercepting proxy | `references/mounts-and-network.md` |
| kubectl `current-context is not set` / no `docker-desktop` context | Kubernetes disabled | `references/kubernetes.md` |
| kubectl context exists but times out | Cluster stopped, or wrong context selected | `references/kubernetes.md` |
| Workload OOM / high host memory use (Windows, WSL2) | `.wslconfig` limits, not Desktop settings | `references/resources.md` |
| Bind mounts from `/mnt/c` slow, inotify doesn't fire (Windows, WSL2) | Windows-filesystem bind mount via WSL2 | `references/mounts-and-network.md` |
| Desktop won't start; KVM/virtualization error (Linux) | Missing `/dev/kvm`, or user not in the `kvm` group | `references/resources.md` |
| Wrong daemon answers after Desktop start/stop (Linux, dual-install) | Desktop mutates the current context at start/stop | Runtime detection above |

## Related skills

- If triage shows the failure is a Dockerfile authoring issue rather than Desktop governance, use `docker-build-strategies`.
- If triage shows the failure is a Compose service-wiring issue rather than Desktop governance, use `docker-compose-patterns`.
- If the project has no Docker setup at all, use `docker-project-foundations` before a Desktop preflight check applies.

## References

- `references/platform-signals.md` — Canonical per-OS/backend signal table both detection scripts implement.
- `references/resources.md` — Memory, CPU, disk, and swap limits: exit 137, disk exhaustion, per-OS remediation.
- `references/governance.md` — Settings Management (`admin-settings.json`) locks and enforced sign-in.
- `references/isolation.md` — Enhanced Container Isolation error catalog and detection order.
- `references/registry-access.md` — Registry Access Management allowlist blocks, and Docker Scout's advisory-only posture.
- `references/mounts-and-network.md` — File sharing path restrictions and proxy configuration (app proxy, containers proxy, PAC, TLS interception).
- `references/kubernetes.md` — Kubernetes enablement, context wiring, and admin locks.

## Assets

No assets — this skill is diagnostic, not generative.

## Scripts

Both scripts implement `references/platform-signals.md` — the canonical
signals table — and share the same exit codes:

- `0` — Docker Desktop confirmed as the active runtime.
- `1` — daemon reachable but confirmed NOT Docker Desktop (skill does not apply).
- `2` — Docker Desktop installed but the daemon is unreachable; offer `docker desktop start` as an explicit choice, never run it automatically.
- `3` — indeterminate, including Windows-containers mode (see the blind spot above).

- **`scripts/detect-desktop.sh`** — Runs the runtime-detection algorithm above on macOS and Linux and reports the active runtime, OS, and backend.
  ```bash
  bash scripts/detect-desktop.sh
  ```
- **`scripts/detect-desktop.ps1`** — Runs the same algorithm on Windows, in PowerShell — bash is not native there.
  ```powershell
  pwsh scripts/detect-desktop.ps1
  ```

## Checks

- `checks/verification.md` — Self-check runbook to run before delivering a diagnosis or remediation.

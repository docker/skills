# Resource Limits (Memory, CPU, Disk, Swap)

Docker Desktop runs containers inside a VM with fixed memory, CPU, disk, and swap
allocations. Workloads that exceed those allocations fail inside the VM, not on
the host — host-level monitoring (Activity Monitor, Task Manager, `free`) will
not explain the failure. Diagnose from inside the Docker Desktop surfaces below.

## Symptoms and causes

| Symptom | Cause | Detect |
|---|---|---|
| Container/build killed, exit code 137 (SIGKILL, in-VM OOM killer) | Workload exceeds VM memory allocation or a `--memory` limit | `docker info --format '{{.MemTotal}}'` before; `docker ps -a --filter 'exited=137'` after |
| Whole-VM OOM: unrelated containers/daemon killed | Containers have no per-container memory limit by default; one container exhausts the shared VM | `docker info` `MemTotal` vs expected workload footprint |
| `write ...: no space left on device` on pull/build/run | VM disk image's actual usage reached its configured limit | Docker.raw apparent-vs-actual heuristic (below) |
| Slow builds, no error | CPU allocation below workload needs | `docker info --format '{{.NCPU}}'` vs host logical CPU count |
| OOM despite apparent swap headroom | Swap is capped independently of memory (default 1024 MiB) and no supported surface exposes the current value | `docker desktop logs` effective-settings dump (below), best-effort only |

Default memory allocation, at the settings layer, differs by platform:

| Platform | Default memory | Formula |
|---|---|---|
| macOS | 50% of host RAM, capped at 8 GiB, floor 2 GiB | explains the 8192 MiB observed on a 36 GiB host |
| Linux | 25% of host RAM, capped at 8 GiB, floor 1 GiB | **not** the 50% figure in the public docs |
| Windows | flat 2048 MiB at the settings layer | real WSL2 memory is governed by `.wslconfig` (unchanged — see below) |

Swap defaults to 1024 MiB; CPUs default to all host logical cores; disk defaults
to the size of the enclosing physical disk (capped at 1 TiB on Windows).

> Source-verified against Docker Desktop 4.85 (pre-GA); not yet live-verified on Linux or Windows hosts.

Do not rely on the public-docs 50%-of-RAM figure to predict what a given host
is running, particularly on Linux where it does not apply. Always read the
effective value from `docker info` directly.

## Reading the effective allocation

### `docker info`

- `docker info --format '{{.MemTotal}}'` — effective memory limit.
- `docker info --format '{{.NCPU}}'` — effective CPU count.
- No `docker info` field exposes the disk limit or the swap limit.

### Disk: Docker.raw apparent-vs-actual heuristic (macOS)

The disk limit is not exposed anywhere; the VM disk image is a sparse file
whose *apparent* size is the configured limit and whose *actual* usage is
consumption against it:

```
du -h "~/Library/Containers/com.docker.docker/Data/vms/0/data/Docker.raw"
ls -lh "~/Library/Containers/com.docker.docker/Data/vms/0/data/Docker.raw"
```

`ls -lh` reports the apparent size (the limit); `du` reports actual usage. A gap
that has nearly closed indicates the disk is close to full. `docker system
prune` reclaims space. Lowering the disk-size slider deletes all containers and
images — never propose it as a first remediation.

### settings-store.json key spellings and omitted defaults

The persisted keys are `MemoryMiB`, `SwapMiB`, `Cpus` (not "CPUs"), `DiskSizeMiB`,
and `FilesharingDirectories` — PascalCase on all three platforms. Manual edits
are matched case-insensitively and get normalized back to PascalCase on the
next save, so a hand-edited `memoryMiB` will still take effect.

> Source-verified against Docker Desktop 4.85 (pre-GA); not yet live-verified on Linux or Windows hosts.

Key structural fact: when memory, CPU, disk, or swap are at their defaults,
`settings-store.json` contains **no resource keys at all** — this is deliberate
persist-time behavior (only non-default values are written), not an omission
bug. `SettingsVersion` and `AutoStart` are the only keys always present
regardless of value. Reading the settings file is not a valid substitute for
querying `docker info` — absence of a key means "at default," not
"unconfigurable" or "zero."

### `docker desktop logs` effective-settings dump (best-effort)

The backend unit `com.docker.backend.ipc` periodically logs a `GET
/app/settings` response containing the full effective resources block,
including swap and the min/max bounds that no supported surface exposes:

```
"resources":{"cpus":{"max":14,"min":1,"value":14},"diskSizeMiB":{...},"memoryMiB":{"max":36864,"value":8192},"swapMiB":{"max":4096,"value":1024}}
```

Treat this as a best-effort fallback, not a reliable interface:

- It is an incidental debug artifact of the backend, not a documented or
  stable API — its presence, format, and field names can change without
  notice.
- It does not appear on demand. In practice it required up to a 24-hour log
  window to surface. Do not block a diagnosis on waiting for it.
- Prefer `docker info` for memory/CPU whenever it is sufficient; fall back to
  this dump only for disk and swap values that have no other source.

## Platform remediation

### macOS

- Propose raising memory/CPU/disk/swap in Settings → Resources → Advanced.
  There is no CLI path to read or write these values.
- Propose `docker system prune` for disk pressure before proposing a limit
  increase.
- A restart of Docker Desktop is required after any change.

### Windows — Hyper-V backend

- Same model as macOS: GUI Settings → Resources sliders for memory, CPU, disk,
  and swap. (documentation-derived; confirm on the target host before relying
  on it)

### Windows — WSL2 backend (default)

- Memory, CPU, and swap are not controlled by Docker Desktop at all on this
  backend. They live in `%UserProfile%\.wslconfig`, under the `[wsl2]`
  section — a Microsoft-owned file, not a Docker Desktop setting. Defaults
  when the file is absent: 50% of host RAM, all logical CPUs, swap sized at
  25% of memory.
- Changes apply to **all** WSL2 distros on the machine, not just Docker
  Desktop's VM.
- Changes require `wsl --shutdown` followed by a Docker Desktop restart to
  take effect.
- A malformed `.wslconfig` file is silently ignored — the VM falls back to
  defaults with no error surfaced anywhere. Flag this explicitly when
  proposing an edit.
- Disk is a VHDX under `%LOCALAPPDATA%\Docker\wsl`; the macOS Docker.raw
  apparent-vs-actual heuristic does not port to this file format.
- Remediation text must point at `.wslconfig` + `wsl --shutdown` + Desktop
  restart — never at the GUI Resources sliders, which do not apply here.
  (documentation-derived; confirm on the target host before relying on it)

### Windows containers

- No documented difference from the Hyper-V backend behavior above was found
  in source material for resource limits specifically. (documentation-derived;
  confirm on the target host before relying on it)

### Linux

- Same VM model as macOS: a Resources pane applies, backed by a disk image
  under `~/.docker/desktop/vms/0/data`. Exit-137 and disk-exhaustion symptom
  parity with macOS is inferred, not independently confirmed.
- Linux-only prerequisite failure: Docker Desktop requires KVM. A missing
  `/dev/kvm` device or a user not in the `kvm` group blocks Desktop from
  starting at all — this is a startup failure, not a resource-allocation
  symptom. Both cases are shown to the user in an error dialog and Desktop then
  quits outright; there is no degraded-mode fallback.
  - Missing device: `KVM is not enabled on host, see
    https://docs.docker.com/desktop/install/linux-install/#kvm-virtualization-support
    on how to configure it`
  - No permission: `User access to /dev/kvm must be ensured, see
    https://docs.docker.com/desktop/install/linux-install/#kvm-virtualization-support`
    — the underlying access check also states the user `must be added to the
    kvm group`.
  - Remediation: add the user to the `kvm` group (`usermod -aG kvm $USER`) and
    re-log in.

  > Source-verified against Docker Desktop 4.85 (pre-GA); not yet live-verified on Linux hosts.

## Admin lockability

Memory, CPU, disk, and swap limits are admin-lockable via the local
`admin-settings.json` file (each entry a generic `{"value": …, "locked": true}`
pair) on all three platforms. They are **not** lockable via the central Admin
Console — only the local admin-settings file can lock resource values. If a
resource control is grayed out in the GUI, it is locked by `admin-settings.json`;
direct the user to their Docker organization administrator rather than treating
it as a bug.

> Source-verified against Docker Desktop 4.85 (pre-GA); not yet live-verified on Linux or Windows hosts.

## Consent requirement

Any resource change — memory, CPU, disk, or swap, on any platform — is
proposed to the user for them to apply; the agent never edits
`settings-store.json`, the GUI sliders, or `.wslconfig` directly. Frame a
`settings-store.json` edit as an action for the user to perform, followed by a
user-initiated Docker Desktop restart.

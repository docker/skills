# Enhanced Container Isolation (ECI) — Error Catalog

Enhanced Container Isolation is a Docker Business feature that runs user containers under Sysbox (a `runc` fork) with Linux user-namespace mapping applied inside the Desktop VM. `--runtime` is ignored — a container cannot opt out of Sysbox by requesting a different runtime. ECI is not a per-container toggle; it applies (or doesn't) to the whole Desktop instance, subject to org-managed allowlists for socket mounts and Docker CLI commands.

> **Note:** the reference host for this skill's research had ECI **off** (`docker info` showed `Default Runtime: runc`, no Sysbox present), so none of the error strings below were reproduced live end-to-end. The socket-mount-denied, empty-allowlist, and command-blocked strings are now source-verified (see the per-section notes below); the Sysbox-emitted strings remain documentation-derived. Treat any entry not marked source-verified as a pattern-match target, not guaranteed-exact runtime output — confirm against the target host's actual Desktop version before hard-coding matches.

## Error catalog

### Docker socket mount denied

```
enhanced container isolation: Docker socket mount denied for container with image "<image>"; image is not in the allowed list. If you wish to allow it, add the image name to the Docker socket image list in the Docker Desktop admin-settings.
```

Optional derived-image tail, appended when the image has a known parent:

```
Alternatively add its parent image (<parent>) to the Docker socket image list in admin-settings and set allowDerivedImages to true.
```

Empty-allowlist variant — no `enhanced container isolation:` prefix at all:

```
Docker socket mount denied for container with image "<image>"; allowed image list is empty.
```

> Source-verified against Docker Desktop 4.85 (pre-GA); not yet live-verified on Windows/Linux hosts. This corrects older documentation: the current string capitalizes "Docker socket" mid-sentence, ends the "...allowed list" clause with a period rather than a semicolon, and has a different remediation tail. Match on the stable, case-insensitive core `container isolation:` + `ocker socket mount denied` rather than the full literal string, since capitalization and trailing text have drifted before and may again.

- **Cause:** the container bind-mounts `/var/run/docker.sock` (`-v /var/run/docker.sock:...`) using an image that is not on the admin-configured `dockerSocketMount.imageList`. Testcontainers and Docker-in-Docker patterns hit this by default.
- **Remediation:** ask the Docker organization admin to add the image to `dockerSocketMount.imageList` — e.g. `docker.io/testcontainers/ryuk:*`. The list supports exact tags, digests, the `*` wildcard (Desktop 4.36+), and an `allowDerivedImages` option. If the denial includes the derived-image tail, the admin can alternatively allow the named parent image and set `allowDerivedImages` to true.
- **Not user-fixable.** Only the org admin can edit the allowlist.

### Docker command blocked

```
enhanced container isolation: docker command "/v1.43/images/.../push..." is blocked; if you wish to allow it, configure the docker socket command list in the Docker Desktop settings or admin-settings
```

(HTTP 403)

> Source-verified against Docker Desktop 4.85 (pre-GA); not yet live-verified on Windows/Linux hosts. The prefix was already documented correctly; the remediation tail above is now confirmed verbatim.

- **Cause:** the socket mount was allowed, but the specific Docker Engine API call the container issued through it matches a deny rule in the admin-configured `commandList`.
- **Remediation:** ask the admin to adjust `commandList` (deny/allow entries, wildcards supported), or run the blocked operation from the host directly instead of through the mounted socket.
- **Not user-fixable.**

### Sysbox namespace sharing refused

```
... sysbox containers can't share namespaces [pid] with the host ...
```

(analogous message for `--network=host`)

- **Cause:** the container requests `--pid=host` or `--network=host`. Sysbox containers cannot share host namespaces — this is inherent to the isolation model, not a configurable allowlist entry.
- **Remediation:** restructure the workload to avoid host namespaces (port publishing instead of `--network=host`, container-to-container networking instead of `--pid=host`). If the requirement is genuinely unavoidable, escalate to the admin — there is no allowlist path around it.
- **Not configurable, by anyone.**

### Restricted host mount

```
... can't mount /etc/docker/daemon.json because it's configured as a restricted host mount ...
```

- **Cause:** the container attempts to bind-mount a sensitive path inside the Desktop VM (e.g. Desktop's own configuration files).
- **Remediation:** use file sharing to mount host directories instead of reaching into VM-internal paths.
- **Not configurable.**

> Note on the two strings above: both are emitted by the Sysbox container runtime itself, not by Docker Desktop's own code, so — unlike the socket-mount and command-blocked strings above — they remain documentation-derived rather than source-verified. Match them loosely (substring, case-insensitive) rather than as exact literals.

### `--privileged` confined, not blocked

- **Symptom:** the container starts successfully under `--privileged`, but kernel-global operations inside it fail with `EPERM`. Documented example: `bpftool` returns `Operation not permitted`. A secondary community report (Docker-in-Docker) shows `mount: /sys/kernel/security: permission denied`.
- **Cause:** ECI confines `--privileged` rather than rejecting it outright — the container still runs, but Sysbox's user-namespace mapping prevents true kernel-level privilege escalation.
- **Detection is hard to do pre-emptively**; this only surfaces once the workload is running and hits a kernel operation. Confirm ECI is active first (see Detection order below) before diagnosing this pattern.
- **Remediation:** prefer Testcontainers-style patterns with an allowlisted image over raw `--privileged` Docker-in-Docker. Never suggest disabling ECI to restore full privilege.
- **Not configurable.**

### Build entitlements fail

- **Symptom:** `docker build --network=host` or other buildx entitlement requests fail, with an error mentioning entitlements.
- **Cause:** ECI's isolation model extends to the BuildKit builder, not just running containers.
- **Remediation:** remove the host-network or insecure-entitlement requirement from the build, or escalate to the admin.
- **Not configurable.**

### Digest change on a previously-allowed image

- **Symptom:** an image that was allowed yesterday is suddenly denied with the same socket-mount-denied error above, with no allowlist change.
- **Cause:** there is no separate digest-mismatch error. The socket-mount allowlist re-validates the image digest on a throttled cycle (roughly every 2 minutes); a new push under the same tag changes the digest, and the next re-check denies it with the identical "not in the allowed list" text from the Docker socket mount denied entry above.
- **Remediation — user-fixable:** `docker image rm <image> && docker pull <image>` to refresh the local digest against the current allowlist entry. This is the one ECI failure mode a user can resolve without an admin.

> Source-verified against Docker Desktop 4.85 (pre-GA); not yet live-verified on Windows/Linux hosts.

## Detection order

`docker info` gives **no positive ECI signal** — do not rely on it as evidence ECI is active or inactive. Check, in order:

1. `settings-store.json` key `EnhancedContainerIsolation` (boolean; key name undocumented but confirmed present).
2. `admin-settings.json` key `enhancedContainerIsolation` — object shape `{value, locked}` (schema documented).
3. `docker desktop logs`, unit `com.docker.backend.cloudsettingsfiles` — dumps the effective ECI policy JSON, including the `locked` flag. This is a working detector but an incidental debug artifact, not a stable interface; treat it as best-effort.
4. **Runtime proof requires a container**: `docker inspect <container> --format '{{.HostConfig.Runtime}}'` showing `sysbox-runc`, or reading `/proc/self/uid_map` from inside a container. Neither is available to a read-only preflight check — a preflight pass can report ECI's configured state but cannot prove what runtime an about-to-run container will actually get without running it.

ECI is user-toggleable (Business, Settings → General) unless admin-locked, and changes require a full quit + relaunch of Desktop, not just a restart of a container.

## Platform notes

| Platform | ECI availability and posture |
|---|---|
| **Windows** | Applies to **Linux containers only** — native Windows containers mode is not supported. WSL2 backend requires WSL ≥ 2.6. (documentation-derived; confirm on the target host) |
| **Windows, Hyper-V backend** | Standard ECI posture — this is the backend the docs recommend "for maximum security"; no Hyper-V-specific limitations documented beyond the Linux-containers-only rule above. (documentation-derived; confirm on the target host) |
| **Windows, WSL2 posture** | Documented as weaker than Hyper-V: all WSL2 distros share one kernel, and users can bypass Desktop's isolation via `wsl -d docker-desktop` to get root access to the VM. Docs recommend Hyper-V "for maximum security." **Never suggest `wsl -d docker-desktop` as a remediation or workaround, under any circumstance.** (documentation-derived; confirm on the target host) |
| **Linux** | Available; settings toggle platform is "All." Build protection is documented as "Mac, Linux, and Windows with Hyper-V." No Linux-specific limitations are documented. (documentation-derived; confirm on the target host) |

The exact error-string wording on Windows and Linux is not independently confirmed — treat it as the same catalog above, pending live verification on each platform.

## Closing rule

Never disable Enhanced Container Isolation to unblock a task, and never propose an alternate runtime, DNS/proxy trick, or namespace-sharing workaround as a substitute. Every remediation above that requires an allowlist change goes through the organization's Docker admin. The one exception a user can act on alone is the digest-change case (`docker image rm` + re-pull) — everything else is escalate-only.

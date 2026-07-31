# File Sharing and Proxy Configuration

Covers two governance surfaces: file sharing paths (bind-mount source restrictions) and proxy configuration (app proxy, containers proxy, and the `~/.docker/config.json` env-injection path).

## File sharing paths

### Symptom

A bind mount fails at `docker run` or `compose up` with one of the messages below. Docs also name the errors `Mounts denied` or `cannot start service`, but the strings actually emitted are lowercase (see Current error strings).

### Cause

The mount source is outside Docker Desktop's shared directory list.

Default shared directories:

| Platform | Default shared directories |
|---|---|
| macOS | `/Users`, `/Volumes`, `/private`, `/tmp`, `/var/folders` |
| Linux | `/home` only |
| Windows | empty — nothing shared by default at the settings layer, including on the Hyper-V backend |

> Source-verified against Docker Desktop 4.85 (pre-GA); not yet live-verified on Linux or Windows hosts.

### Current error strings

The long-form denial is current and user-visible on **macOS and Docker Desktop for Linux** (Windows never emits it — the mount check is a no-op there, consistent with the WSL2 row below):

```
Error response from daemon: mounts denied: The path <path> is not shared from the host and is not known to Docker.
You can configure shared paths from Docker -> Preferences... -> Resources -> File Sharing.
See <docs-url> for more info.
```

The prefix is lowercase `mounts denied:` — a match against an uppercase-literal `Mounts denied` will miss it. Match case-insensitively.

Two sibling variants also ship in the product:

- Create-time form: `path not shared: <path>`
- Malformed bind-spec forms (grammar error ships as-is, quote verbatim): `mount denied: the source path "<spec>" doesn't contains colon` and `... too many colons`

> Source-verified against Docker Desktop 4.85 (pre-GA); not yet live-verified on Linux or Windows hosts.

### Detection (macOS/Linux/Windows-Hyper-V)

1. Read `filesharingDirectories` in settings-store.json.
   - **Absent at defaults.** Absence of the key means: assume the platform defaults in the table above — do not treat absence as "nothing shared" (except on Windows, where the default genuinely is nothing shared).
2. Fallback (fragile, best-effort): `docker desktop logs` dumps the effective `vm.fileSharing` array, including `locked` flags per entry. This is an incidental debug artifact, not a supported interface — treat it as best-effort and expect it to need a log-generation window to appear.
3. No CLI surface reads or writes this list (see the CLI plugin's exhaustive command inventory: no `settings` subcommand exists).

### Remediation order

1. **Prefer a path already under a shared root** — e.g., relocate the source into your home directory instead of adding a new shared root. This needs no settings change and no restart.
2. If that isn't possible, the user adds the path in **Settings → Resources → File sharing**, then **Apply & restart**. This is a user-performed action — propose it, do not imply the agent can do it.
3. If the entry is grayed out in the GUI, it is admin-locked via `filesharingAllowedDirectories`. Direct the user to their Docker organization administrator. Do not attempt a workaround.

### Platform scope of the allowlist

| Platform | Allowlist enforced? |
|---|---|
| macOS | Yes |
| Linux | Yes |
| Windows, Hyper-V backend | Yes (documentation-derived; confirm on the target host) |
| Windows, WSL2 backend (default) | **No allowlist at all** (documentation-derived; confirm on the target host) |

The file sharing pane documentation states it applies to "Mac, Linux, and Windows Hyper-V only." Do not run the shared-path check on WSL2 — it does not apply there.

### WSL2 delta (documentation-derived; confirm on the target host)

WSL2 has no shared-path allowlist and no `Mounts denied` failure class for Windows-drive paths. Instead:

- Bind mounts from `/mnt/c/...` (and other `/mnt/*` Windows-drive paths) work, but are slow.
- `inotify` file-change notifications do not fire across the `/mnt/*` boundary.

Preflight check on WSL2: if the bind-mount source path starts with `/mnt/`, warn about the performance and `inotify` gap, and recommend keeping the source in the Linux filesystem (e.g., under `~` inside the WSL2 distro) instead of on the Windows filesystem.

### Non-macOS defaults are now source-verified

Linux defaults to `/home` only, and Windows defaults to an empty list at the settings layer (see the Cause table above) — do not assume parity with the macOS list. These values are source-verified against Docker Desktop 4.85 (pre-GA) but not yet live-verified on Linux or Windows hosts; still confirm via the detection steps above before relying on them for a specific host.

## Proxy configuration

Three separate, independently-configured surfaces. Do not conflate them.

| Surface | Scope | Where |
|---|---|---|
| App proxy | Desktop app itself, CLI, sign-in | Settings → Resources → Proxies, keys `ProxyHTTPMode`, `OverrideProxy*` |
| Containers proxy | Image pulls (**always enforced**) and container outbound traffic | Settings → Resources → Proxies, keys `ContainersProxyHTTPMode`, `ContainersOverrideProxy*` |
| `~/.docker/config.json` `proxies` | Injects `HTTP_PROXY`/`HTTPS_PROXY`/etc. env vars into containers and builds only | Config file, not a Desktop setting |

The third surface is documented as "not used as proxy settings for the Docker CLI or the Docker Engine itself" — it is an env-var injection mechanism for whatever runs inside the container, nothing more.

### Symptom

`docker pull` hangs or times out behind a corporate proxy.

### Cause

The containers-proxy mode (not the app proxy) is misconfigured. Pulls always go through the containers-proxy setting.

### Detection

- Read the settings-store.json keys above for mode and effective value (`system`/manual/none).
- Cross-check locked state and effective value via the `docker desktop logs` proxy blocks (same fragility caveat as the file-sharing logs dump — best-effort, not a supported interface).

### Critical caveat — do not use `docker info` for proxy detection

`docker info`'s proxy fields **always** show the internal `http.docker.internal:3128` address, regardless of whether a corporate proxy is configured. This holds even on a host with no proxy configured at all. Never use `docker info` proxy output as a detection signal — read the settings keys instead.

### Remediation

Set the containers proxy (not just the app proxy) in **Settings → Resources → Proxies**, then propose the change to the user — this is a user-performed setting change. If the field is locked, escalate to the organization's Docker administrator (admin-lockable via Settings Management, keys `proxy` / `containersProxy`).

### TLS interception (x509 errors)

**Symptom:** `x509: certificate signed by unknown authority` on pull or login.

**Cause:** A TLS-intercepting corporate proxy is in the path, and the Desktop VM does not trust the interception CA.

**Remediation (user-performed):**

1. The user installs the organization's root CA:
   - macOS: into the Keychain, set to "Always Trust".
   - Windows: into the Windows certificate store (documentation-derived; confirm on the target host).
2. The user then restarts Docker Desktop — the agent asks the user to do this rather than performing it.

If pulls still fail after the CA is trusted and Desktop is restarted, escalate to IT for the correct CA bundle.

### PAC (proxy auto-config)

- Settings keys: `ContainersOverrideProxyPAC` / `pac` / `embeddedPAC`.
- The PAC server must serve MIME type `application/x-ns-proxy-autoconfig`. A PAC URL that responds with the wrong MIME type will fail even if reachable.
- Kerberos/NTLM proxy authentication requires Docker Business.
- Windows adds an installer flag requirement for Kerberos/NTLM: `--proxy-enable-kerberosntlm` — this is not a pure settings toggle, it must be set at install time (documentation-derived; confirm on the target host).
- All of the above is admin-lockable via Settings Management.

### Windows-specific delta (documentation-derived; confirm on the target host)

- An additional toggle, "Use proxy for Windows Docker daemon", plus `proxy.windowsDockerdPort` (default `-1`), applies only in Windows-containers mode.
- The network/proxy tab is absent entirely in Windows-containers mode.
- x509/CA remediation targets the Windows certificate store, not the macOS Keychain.

### Linux

No documented difference from macOS for proxy configuration.

# Registry Access Management

Registry Access Management is a Docker Business feature: an admin-controlled
registry allowlist (maximum 100 entries) enforced by DNS-level hostname
filtering inside the Docker Desktop VM. It only takes effect while the user
is signed in with credentials from the enforcing organization. Policy changes
propagate to clients within up to 24 hours. When a user belongs to multiple
organizations, the first org's policy wins. The allowlist also applies to
Dockerfile `ADD <url>`, not just `docker pull`/`push`.

This surface genuinely blocks operations. Do not confuse it with Docker
Scout policies (below), which do not.

> Note: on the reference host for this skill, Registry Access Management is
> not enforcing (`docker desktop logs` shows "stopping Registry Access
> Management refresh because no orgs are enforced"). The enforcement
> behavior below is source-verified against Docker Desktop 4.85 (pre-GA); it
> has not been reproduced live against an actively enforcing organization.

## Symptom, cause, remediation

| Symptom | Cause | Remediation |
|---|---|---|
| `Access to <host> has been restricted by your administrators. To access this registry, ask your administrators to add it to your organization's allowed registries.` on pull, push, or build (HTTP 403, surfaced inside the pull/build error) | `<host>` is not on the org's allowlist | Use an allowed registry, or ask your Docker org admin to add `<host>` to the Registry Access Management allowlist — including redirect/CDN domains. Do not attempt a DNS or proxy workaround. |
| Manifest pull succeeds, blob download fails | The registry itself is allowed, but hostname filtering does not cover its redirect/CDN domains (e.g. Amazon ECR redirects blob fetches to `s3.amazonaws.com`) | Ask the admin to allowlist the redirect/CDN domain as well as the registry hostname. |
| Pull from a registry mirror is blocked even though the mirror is configured | The upstream *source* registry is restricted; a mirror does not exempt it | Ask the admin to allowlist the source registry, not just the mirror. |

Match on the stable substring `has been restricted by your administrators` rather
than the full sentence — exact wording around it may vary by surface. The older
message `registry access to <host> is not allowed` no longer appears in current
Docker Desktop source; keep it only as a legacy fallback pattern for older Desktop
versions, never as the primary match.

## Detection

```
docker desktop logs | grep -i registryaccess
```

This reads the `com.docker.backend.registryaccess` log unit. Grep
case-insensitively — one positive-case log line below uses lowercase
"management".

- Negative case (not enforcing): `stopping Registry Access Management
  refresh because no orgs are enforced`.
- Positive case (enforcing) — now known, with these line shapes:
  - `Registry Access Management policy enabled, times: refresh due after
    <t>, grace ends <t>, grace interval <t>` (close variants also occur).
  - `Registry Access Management policy source: <hub|hub-cache|admin-settings|
    admin-settings-invalid|none>`.
  - `Registry Access Management will perform a refresh in <duration>`, also
    seen as `Registry Access management policy refresh is due on <date>`
    (note the lowercase "management" here).
- Cadence: refresh is scheduled 12–24 hours out by default (12-hour grace
  period, 1-hour retry interval, backoff up to 24 hours when Docker Hub is
  unreachable). This replaces the previously assumed ~15-minute cadence,
  which is not corroborated.
- Offline / grace-period strings that may appear while Desktop cannot reach
  Docker Hub to refresh the policy:
  - `Docker Desktop cannot contact Docker Hub to download the latest
    configuration.`
  - `…must be refreshed before the grace period ends on <date>`
  - `…the grace period has been exceeded. Please reconnect to the Internet
    and refresh.`

Registry Access Management state is **not** stored in `admin-settings.json`
or `settings-store.json` — do not look there.

## Known limitation: the allowlist is never exposed client-side

There is no local file or documented API that lists which registries are
allowed. The only way to learn a registry is blocked is to hit the error
above when a pull, push, or build actually reaches it. Report this to the
user as a blind spot up front — do not imply that a clean preflight check
means the operation will succeed.

## Documented enforcement gaps — never present these as remediation

The following are documented gaps where Registry Access Management does not
enforce as expected. Per the governance posture, these are gaps to disclose
if relevant, never suggested paths around a block:

- buildx builds using Kubernetes or other custom drivers.
- Some Docker Debug and Kubernetes-related pulls.
- Windows container images, unless the Windows-daemon proxy toggle
  (see below) is turned on.
- Users who are signed out, when sign-in is not itself enforced.

## Platform notes

- **macOS / Linux / Windows (Hyper-V backend):** DNS-level filtering inside
  the Desktop VM, as described above.
- **Windows, Windows-containers mode:** image operations are **not**
  restricted by default. Restrictions only apply once the admin or user
  turns on "Use proxy for Windows Docker daemon." Do not present turning
  this off, or leaving it off, as a way to avoid a block — it is a coverage
  gap, not a sanctioned path.
- **Windows, WSL2 backend:** requires WSL kernel >= 5.4; restrictions apply
  to all WSL2 distros on the machine, not just the Docker Desktop distro.
- **Linux:** no documented statement either way on availability. Given the
  identical VM-based DNS-filtering architecture and that sign-in works on
  Linux, availability is inferred, not confirmed — treat as unverified until
  checked on a live Linux host.

## Docker Scout policies (short)

Docker Scout policies are advisory locally and do **not** block `docker
push`, `docker run`, or `docker build`. There is no documented mechanism by
which a Scout policy blocks a local command. Do not conflate Scout with
Registry Access Management above — one blocks, the other does not.

Enforcement only happens where a pipeline opts in explicitly, via:

```
docker scout policy IMAGE --exit-code
```

This exits `2` when the image is non-compliant. Whether an org has Scout
policies configured at all is not detectable offline — it requires a
network call to the Scout platform.

If a CI job fails with exit code 2 from `docker scout policy`, remediate the
flagged finding (e.g. update the base image, fix the CVE) or contact the
Scout org admin. This is not something a local preflight check can resolve.

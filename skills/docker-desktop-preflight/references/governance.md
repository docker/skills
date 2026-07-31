# Settings Management & Enforced Sign-In

Covers two governance surfaces: Settings Management / `admin-settings.json` (B6) and
enforced sign-in (B2). Both are admin/IT-controlled. Read this before telling a user
a setting is "unmanaged" or that a lock can be worked around — it usually cannot be,
and the file that proves it lives in a different directory than you expect.

## 1. Check the admin path, not the user settings path

Docker Desktop keeps two separate files. Confusing them produces a false "not managed"
diagnosis — this happened during research on this very skill: the admin file was
missed because the check ran against the user settings directory instead of the
admin directory.

| File | Purpose | macOS | Windows | Linux |
|---|---|---|---|---|
| `settings-store.json` | User's own settings | `~/Library/Group Containers/group.com.docker/` | `%APPDATA%\Docker\settings-store.json` | `~/.docker/desktop/settings-store.json` |
| `admin-settings.json` | Org-pushed settings + locks | `/Library/Application Support/com.docker.docker/` | `C:\ProgramData\DockerDesktop\` | `/usr/share/docker-desktop/` |
| `registry.json` | Sign-in enforcement | same directory as `admin-settings.json` | `C:\ProgramData\DockerDesktop\registry.json` | `/usr/share/docker-desktop/registry/registry.json` |

- Always `stat`/read the admin-directory path for the current OS first. A clean
  `settings-store.json` tells you nothing about org policy.
- On macOS the admin directory is world-readable — no elevation needed to read it
  (verified on this host: `ls`/`cat` against `/Library/Application Support/com.docker.docker/admin-settings.json` succeeded as a normal user).
- Windows (documentation-derived; confirm on the target host before relying on it):
  whether a standard user can read `C:\ProgramData\DockerDesktop\` is undocumented —
  ACL readability is unverified. Don't assume the macOS world-readable result carries over; check live before depending on it in a script.
- Linux (documentation-derived; confirm on the target host before relying on it):
  the docs state the path but never affirmatively confirm standard-user read access.

## 2. Presence is not the same as locked

`admin-settings.json` existing does **not** mean every setting in it is enforced.
Each key carries its own `locked` boolean.

```json
{
  "enableDockerAI": { "value": true, "locked": false },
  "allowBetaFeatures": { "value": false, "locked": false }
}
```

- Parse `locked` per key. A `false` here means the org shipped a *default*, not a
  mandate — the user's own value still wins if they've already set one.
- Never report "this org locks Docker Desktop" from file presence alone. Report the
  per-key lock state you actually parsed.
- Resource limits (memory, CPU, disk, swap) are admin-lockable the same way: the
  local file accepts any setting name, matched case-insensitively, as `{"value": …,
  "locked": …}` — there is no fixed resource-key allowlist. Admin Console (Docker
  Home) central policy cannot lock resource limits at all; its policy schema has no
  resource keys, so a resource lock can only ever come from a local
  `admin-settings.json`.
- Locked values only take effect once a **Business**-entitled user is signed in.
  Before that sign-in (or on a non-Business account), only the file's `proxy` and
  `analyticsEnabled` entries apply, and they apply unlocked — which is why a host can
  have a readable `admin-settings.json` full of real lock entries while the GUI still
  shows nothing grayed out.

## 3. Absence is not the same as unmanaged

Two documented ways policy can apply with **no local `admin-settings.json` at all**:

- **Admin Console (Docker Home) policies.** Precedence is: user policy > org policy >
  local `admin-settings.json` > config profiles. These apply after restart + sign-in
  on Docker Business and leave no local artifact — there is no documented way for an
  agent to prove a host is *not* enrolled this way. Treat a missing admin file as
  "no local lock evidence found," never as "unmanaged."
- **`admin-settings.json` presence alone enforces sign-in** (§4) — a file that carries
  no locked keys at all can still force the user to authenticate.

If asked "is this host managed?", answer with what you checked and what you could not
check (Admin Console enrollment is not locally detectable), not with a yes/no.

## 4. What to do when a setting is locked

Symptom: the control is grayed out in the GUI, or a config-file edit reverts on
restart.

- Read the enforced value from `admin-settings.json` when it is readable, and state
  it to the user (for example: "your org has locked `enhancedContainerIsolation` to
  `true`").
- Follow with: **"Contact your Docker organization administrator."** This is the
  standing remediation for every locked setting — there is no product-documented way
  to identify *which* admin or org by name, so keep the phrasing generic.
- Never propose a workaround: not editing the config file again, not an alternate
  runtime, not disabling the feature, not any other bypass. This is an absolute rule
  for every governance surface in this skill, not a case-by-case judgment call.
- If the lock state can't be read (e.g. no local admin file, or the key isn't listed
  in it), say so plainly: "no local evidence of a lock was found, but org-level
  policy may still apply through Docker Home without a local file (see §3)."

## 5. Enforced sign-in: the mechanisms, in precedence order

Docker Desktop evaluates these mechanisms in a fixed order and stops at the first
one configured on the host — that mechanism's answer (enforce or pass) is final, and
every later one, including Admin Console policy, is skipped:

- **macOS:** configuration profile (MDM) → plist → `registry.json` →
  `admin-settings.json` presence → Enhanced Container Isolation requirement →
  Admin Console (remote).
- **Windows:** registry policy key → `registry.json` → `admin-settings.json`
  presence → Enhanced Container Isolation requirement → Admin Console (remote).
- **Linux:** `registry.json` is the only local mechanism; Admin Console (remote) is
  the sole fallback.

Admin Console (remote) enforcement ranks **last on every platform** and is only ever
evaluated while the user is already signed out.

(Source-verified against Docker Desktop 4.85 (pre-GA); not yet live-verified on
Windows/Linux hosts.)

| # | Mechanism | Path / detail | Applies on |
|---|---|---|---|
| 1 | Windows registry policy | `HKLM\SOFTWARE\Policies\Docker\Docker Desktop`, multi-string value `allowedOrgs` (lowercase, one org per line). | Windows only |
| 2 | MDM configuration profile | Enrolled device profile; readable directly — no admin rights needed — via `defaults read com.docker.config allowedOrgs` (returns a `;`-separated org list). | macOS only |
| 3 | plist | `/Library/Application Support/com.docker.docker/desktop.plist` | macOS only |
| 4 | `registry.json` | Per-OS path (table in §1) | All platforms — the **only** mechanism on Linux |
| 5 | `admin-settings.json` presence | See side channel below | All platforms |
| 6 | Enhanced Container Isolation requirement | A configured policy that mandates sign-in | All platforms |
| 7 | Admin Console (remote) | Cloud policy, polled only while signed out | All platforms — evaluated **last** |

- Detect mechanisms 1, 3, and 4 by checking whether the file/key exists — no
  elevation required for the file checks. Mechanism 2 (MDM) no longer needs
  enrollment-level guessing: `defaults read com.docker.config allowedOrgs` reads the
  managed preference directly; a missing key/domain means the mechanism is not
  configured on this host, not "unknown."
- Windows registry read — `reg query "HKLM\SOFTWARE\Policies\Docker\Docker Desktop" /v allowedOrgs`
  (documentation-derived; confirm on the target host before relying on it): reading
  `allowedOrgs` without elevation is expected under default ACLs, but a locked-down
  host may deny the read — do not treat a read failure as proof the policy is absent.
- Linux has no MDM or plist equivalent — write this explicitly rather than omitting
  the row: for mechanisms 1–3, Linux support is "not applicable," not "unverified."
- Org membership is checked as an exact string intersection against a locally
  cached, integrity-checked copy of the signed-in user's orgs, fetched once at
  sign-in — enforcement decisions made after that point are offline.

### Side channel: `admin-settings.json` presence alone

The mere presence of `admin-settings.json` enforces sign-in — a pure existence
check; the file's contents are never parsed to make this particular decision.
Clearing this enforcement requires a **Docker Business** subscription: a signed-in
Personal, Pro, or Team account is still enforced and gets automatically signed back
out ("You must be a member of the [org] organization…" when an org list is also in
play). Check for the file's existence (§1 path) as its own sign-in-enforcement
signal, separate from parsing its contents for other locks.

### What enforcement looks like at the CLI

This corrects an earlier assumption: enforced sign-in does not generally mean the
daemon socket is unreachable. For the org-list mechanisms (Windows registry key,
`registry.json`, macOS configuration profile, plist), the engine boots normally and
the socket answers — `docker version`, `docker info`, and ping all succeed. Every
other Docker API call instead fails with **HTTP 407 Proxy Authentication Required**,
whose body self-describes the mechanism, e.g.: `Sign in to continue using Docker
Desktop. Membership in the [<org>] organization is required. Sign in enforced by
your administrators (via registry.json).` The trailing clause names the mechanism —
`admin-settings.json` (no organization clause), `desktop.plist`, `Config Profile`, or
`Registry key`.

Only two mechanisms hold the engine at boot, so the socket is genuinely absent until
an entitled user signs in: **`admin-settings.json` presence** and an **Enhanced
Container Isolation requirement**. Every other mechanism releases the engine
immediately and enforces only at the API-proxy layer. A running engine is also never
re-paused mid-session — signing out while enforcement is active does not stop
containers or the engine; only new API calls start returning 407.

**Diagnostic rule:** socket answers, `docker info` succeeds, and everything else
fails with a 407 body containing "Sign in to continue using Docker Desktop" ⇒
enforced sign-in, not a stopped Docker Desktop. Direct the user to sign in (§7)
rather than troubleshooting Desktop as if it were down.

## 6. Detecting who is signed in

Use this order; do not skip to `docker info`:

1. `docker-credential-desktop list` — returns registry-to-username pairs with no
   secret field. This is the best available local signal for "who is signed in."
2. `~/.docker/config.json` — check `auths` and the configured `credsStore`.
3. `docker info` `Username` field — **unreliable**: it can be absent even when the
   user has valid stored credentials. Do not treat an empty `Username` as "signed
   out."

Never run `docker-credential-desktop get`. Unlike `list`, `get` prints the live
access token in plaintext alongside the username. There is no safe use of `get` for
a preflight check — only use `list`.

`docker-credential-desktop list` was verified on macOS; treat its behavior on
Windows and Linux as documentation-derived (confirm on the target host before
relying on it) since no cross-platform transcript exists for this skill.

## 7. Clearing enforced sign-in

- Docker's documentation only describes the Desktop **GUI** sign-in flow (whale menu
  → Sign in) as satisfying enforcement.
- `docker login` authenticates the CLI to registries only — it does not clear
  Desktop's enforced-sign-in gate. Tell the user to use the GUI flow, not
  `docker login`, when enforcement is the blocker.
- Never suggest signing out as a way to test or route around enforcement — that is a
  documented enforcement gap, not a sanctioned workaround (see §4).

## 8. Known limitations — disclose these, don't paper over them

- **Org name / admin contact is never surfaced.** The product does not expose who
  locked a setting or which org enforces sign-in next to the control itself. The
  generic "contact your Docker organization administrator" is the only available
  phrasing.
- **Admin Console enrollment cannot be proven absent** (§3) — only its *effects*
  (a locked control, an enforced sign-in prompt) are locally observable.
- **GUI modal behavior on enforcement is still unverified** — the sign-in prompt
  dialog itself has not been traced. §5 above now covers the CLI/API-layer behavior
  (the 407 responses and their messages), which is source-verified.
- **Locked-value edit behavior (silent revert vs. immediate rejection) is
  unverified** — no `locked: true` entry has been observed to test against. Report
  the lock, not a specific mechanism of failure.

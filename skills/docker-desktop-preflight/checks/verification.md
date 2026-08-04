# Verification Runbook

Use these checks before delivering a diagnosis or remediation. This skill produces a
diagnosis, not a build artifact — "verification" here means checking the diagnosis
itself is sound, not running a build.

## 1. Identity signal agreement before any Desktop-specific claim

Before stating anything Desktop-specific, confirm the primary identity signal and the
context/socket fallback agree:

- `docker info --format '{{.OperatingSystem}}'` says `Docker Desktop`, **and**
- the current context/socket (per Runtime detection in SKILL.md) is consistent with
  that — `desktop-linux`, or a `default`/`/var/run/docker.sock` symlink whose target
  resolves into Desktop.

If the daemon is unreachable, the fallback (context name/socket path) is the only
signal — treat conclusions drawn from it alone as provisional until the daemon
answers. If the two signals disagree (e.g. `docker info` reaches a non-Desktop daemon
while the socket path looks like Desktop's), do not proceed with Desktop-specific
remediation — report the mismatch instead.

## 2. Every proposed command is on the safe list

Cross-check every command about to be suggested or run against the read-only list in
SKILL.md ("Read-only preflight commands").

- Anything in the "Never run without explicit user consent" list (`start`, `stop`,
  `restart`, `update`, `enable`/`disable`, `kubernetes reset-cluster`, `diagnose`,
  `diagnose -u`, `engine use`) must appear **only as a question to the user** — e.g.
  "Would you like me to run `docker desktop start`?" — never as an action already
  taken or about to be taken silently.
- If a response contains one of these commands phrased as a statement of intent
  rather than a question, rewrite it before sending.

## 3. Admin-locked findings get escalation, never a workaround

For any finding where `admin-settings.json` shows `locked: true`, or where the
governance surface is documented as admin/IT-only (enforced sign-in, Enhanced
Container Isolation allowlists, Registry Access Management allowlist, Kubernetes
lock):

- The response states the enforced value when it was actually readable.
- The response ends with "contact your Docker organization administrator" (or
  equivalent), not a config edit, not an alternate command, not a suggestion to
  retry differently.
- If no workaround exists in the reference file for a surface, none should appear in
  the response either — check the relevant `references/*.md` file for the specific
  wording before writing the escalation line.

## 4. No forbidden workaround language anywhere in the response

Scan the drafted response for any of the following. Their presence is a failure,
regardless of context or hedging:

- DNS or proxy bypass suggestions for Registry Access Management.
- Suggesting an alternate runtime (Colima, Rancher Desktop, Podman, bare Engine) as a
  way to avoid a Docker Desktop governance block.
- Suggesting the user sign out to test or clear enforced sign-in.
- `wsl -d docker-desktop` or any other namespace/VM-escape suggestion for Enhanced
  Container Isolation on WSL2.
- Presenting a documented enforcement gap (e.g. buildx custom drivers bypassing
  Registry Access Management, Windows-containers mode's default non-enforcement) as a
  sanctioned path rather than disclosed limitation.

## 5. OS and backend identified before any surface-specific claim

Confirm the response states which OS (macOS / Windows / Linux) and, on Windows, which
backend (WSL2 / Hyper-V / Windows containers) the finding applies to, before making
any claim from a per-OS table or reference file section. A claim copied from the wrong
OS/backend row is a diagnosis error, not a minor wording issue — re-check against the
Runtime detection per-OS table in SKILL.md if backend is ambiguous.

## 6. No credential-printing command anywhere in the response

Confirm the response never suggests `docker-credential-desktop get` or any other
command that prints a live credential or token. Sign-in identity detection uses
`docker-credential-desktop list` only (registry→username pairs, no secret field) —
see `references/governance.md` §6.

## 7. Platform-signals parity

Any change to `references/platform-signals.md` must be reflected in **both**
`scripts/detect-desktop.sh` and `scripts/detect-desktop.ps1` in the same change —
verify the three (the table and both scripts) agree before shipping a
detection-related edit.

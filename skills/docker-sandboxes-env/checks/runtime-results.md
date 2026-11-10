# Runtime results for the verification runbook

Recorded run of `verification.md` on 2026-11-10: sbx v0.51.0
(`7d55286de0c775148b985ed349f760f1eba06203`), macOS arm64, an isolated
`--app-name` app signed in for this run, Python 3.9.6. Plan approvals were
answered `y` interactively through a pseudo-terminal; `--force` was used only
for the final cleanup. Every test sandbox was removed and the isolated daemon
stopped afterwards. These results describe this release and platform only.

| Step | Observed | Result |
|---|---|---|
| 0. Helper | `search claude` returned 21 v3 kits. `update sbx/playwright` suggested `sbx/playwright:1.61.1` = `newestRelease`. `pin` kept `1.61.1` and added its `@sha256:` digest. The missing repository exited 1 with `repository not found or private`. | Pass |
| 1. Fixtures | Five scenario files in a `mktemp -d` directory. A plain `sbx login` session did **not** sign in the isolated app (`not signed in to Docker`) until `sbx --app-name "$APP" login` ran. | Pass after runbook fix |
| 2. Plan only | Both plans printed with exit 0; the minimal file was named `shell-minimal` (`<agent>-<workspace-basename>`); the empty file declared no workspace. No sandbox existed afterwards. | Pass |
| 3. Hooks | Declining the first plan failed with `was not approved` and ran no hooks. After approval: two `initialize-ran`, one `post-create-ran`; `env exec … -- pwd` added neither. The unchanged second run was asked again: "nothing in this plan has changed, but its commands run on this machine … needs explicit approval on each run". | Pass |
| 4. Silent re-apply | The second `env run -d` of the approved file without host commands showed no prompt. | Pass |
| 5. preRemove failure | `env rm` printed `warning: the preRemove commands did not finish: preRemove[0] (exit 1)` and then `Removed sandbox env-check-remove`. | Pass |
| 6. Non-interactive exec | Missing sandbox: exit 125, `sandbox 'env-check-never' not found for this environment`, `try: sbx env create`. Existing sandbox: `hi`, exit 0. | Pass |
| 7. Mount-root protection | The file existed in the sandbox at its host path; the write failed with `Read-only file system`; the host file was unchanged. | Pass |
| 8. Cleanup | All four test sandboxes removed; `No sandboxes found`; daemon stopped; scratch directory deleted. | Pass |

## Additional observations

- **Subdirectory rename gap.** With the env file at `conf/sbxenv.yaml` under
  a read/write `workspace: ..`, `sbx env plan` warned "environment file
  mounted read-only, inside a directory the sandbox can rename". In the
  sandbox, the workspace stayed writable (new files and renaming other
  directories worked), but `mv conf conf.moved` failed with
  `Read-only file system`: the file is its own read-only bind mount
  (`/proc/mounts`). The documented gap did not reproduce on this release and
  platform. The skill keeps the documented guidance, because the plan and the
  docs still treat such a file as replaceable and other platforms or releases
  may differ.
- **Plan does not resolve kits.** `sbx env plan` printed a plan with exit 0
  for `sbx/playwright:99.0.0` (nonexistent tag) and `sbx/go:1.23` (no such
  public kit), while an unknown field (`kitz`) failed with
  `unknown field "kitz"`.

## Not covered

- Cloud environments, MCP servers, secrets/bindings provisioning,
  `--skip-host-commands`, `rememberHostCommands`, adoption recovery, and
  Linux or Windows hosts.

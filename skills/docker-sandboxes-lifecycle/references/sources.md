# Sources

## Public documentation checked for this correction

The author and reviewer read these public pages on 2026-11-03. This is document
verification, not evidence that the runbooks or standalone CLI were executed.

| Claim | Source and section | Applicability |
| --- | --- | --- |
| Use `--detach` or `-d`; `--detached` is rejected | [Release notes](https://docs.docker.com/ai/sandboxes/release-notes/), 0.48.0, “Update command flags” | Explicit spelling change in 0.48.0; not a minimum version for every lifecycle feature. |
| `run --name` reattaches; `run -d --name` permanently changes detached mode | [Usage](https://docs.docker.com/ai/sandboxes/usage/), “Create without attaching” and “Keep a sandbox running in the background” | Detached-mode change is not an ordinary read-only reattach. |
| `create` without a path is mountless; workspace layout is fixed at creation | [Troubleshooting](https://docs.docker.com/ai/sandboxes/troubleshooting/), “Sandbox doesn't contain my project files” | The page explicitly dates optional `create` paths to 0.42.0. |
| `run --publish` is ignored on reattach; use `ports` to change mappings | [Development workflow](https://docs.docker.com/ai/sandboxes/workflows/development/), “Accessing services in the sandbox” | Local standalone `sbx`, not cloud sandbox behavior. |
| Clone mode is fixed at creation; fetching needs a running sandbox; removal deletes the sandbox remote | [Git workflow](https://docs.docker.com/ai/sandboxes/workflows/git/), “Clone mode” and “Sandbox remote behavior” | Preserve fetched work in a verified local branch before removal. |
| `rm` confirmation, stopped-only pruning, `until=` age filtering and legacy `since=` support | [Usage](https://docs.docker.com/ai/sandboxes/usage/), “Start, stop, and remove” | No minimum introduction version for `until=` was established. |
| Piped `y` does not confirm; missing terminal confirmation exits 1 | [Automation workflow](https://docs.docker.com/ai/sandboxes/workflows/automation/), “Cleanup and exit codes” | Do not silently add `--force` to a failed cleanup command. |
| Detached `sbx exec` is unsupported | [Usage](https://docs.docker.com/ai/sandboxes/usage/), “Run commands inside a sandbox” | Docker Engine's `docker exec` flags are not standalone `sbx` evidence. |
| Resource defaults vary by platform | [Environment file](https://docs.docker.com/ai/sandboxes/configuration/environment-files/#sandboxoptions), `sandboxOptions` | Numeric defaults were removed rather than extrapolated across platforms. |
| A local branch preserves a fetched commit independently of remote-tracking refs | [Git branch](https://git-scm.com/docs/git-branch), description and start-point | Inspect the fetched commit first; create a new branch, never overwrite an existing one. |

## Inherited evidence and limits

The pre-existing public skill cited `docker/sandboxes` source revision
`df5c96ba60484fa2c375469dbac912c205da6c37` and a standalone help capture
`v0.42.0-503-g951b7f6d7`. Neither was re-read or re-executed for this correction.
The source was unavailable to the reviewer. These are provenance records, not
claims that all current behavior was tested at those versions.

Inherited source-only details include the clone-mode reattach error/no-op split,
bare positional-name deprecation, naming restrictions, and the isolated
`--app-name` runbook mechanism. Survivor refs under `refs/sandboxes/<name>/*`
are implementation-specific and were not reverified: the recovery procedure
now preserves a checked local branch **before** deletion instead of relying on
them. The effect of extra workspace paths on reattach is also unverified; omit
them. Flag-level reference pages were not consistently accessible, so this is
not a complete CLI-surface audit.

The local `sbx` invocation behaved as the legacy Docker plugin, so its output
and local `docker_help` results were **not** used to verify standalone flags.
No standalone sandbox was created, stopped, removed, or pruned. The runbook
(including its inherited isolation/setup commands) and eval Prompts 8–9 remain
unexecuted and need product-owner/runtime acceptance. Static eval checks verify
only fixture text; they do not establish routing or task effectiveness.

The Forge run produced the initial correction and performed a reviewer/delta-review
loop. Operator review then tightened pre-removal recovery and condensed this evidence
record. No new private source material was accessed or incorporated.

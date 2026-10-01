# Prune age filter and preview detail (sbx v0.46.0)

Detail for the `sbx prune` rules in `SKILL.md`. Provenance for each row is in
`references/sources.md`. Nothing here was executed.

## Cutoff semantics

- `--filter until=VALUE` keeps only sandboxes that stopped before the cutoff.
  `VALUE` is an RFC 3339 timestamp, a Unix timestamp, or a Go duration relative
  to now. `until=168h` prunes sandboxes stopped more than 168 hours ago and
  leaves those stopped within that window.
- The age is the time since the sandbox stopped. A sandbox created long ago but
  stopped moments ago is not selected.
- Running sandboxes are never candidates, with or without a filter.

## Unknown stop time

- With an age filter, a stopped sandbox whose stop time the daemon cannot
  report is excluded, because its age cannot be established.
- A real run reports it on stderr: "Skipping N stopped sandbox(es) whose stop
  time is unknown (...); remove explicitly with 'sbx rm'."
- `--dry-run --json` returns an object with `would_remove` and
  `skipped_unknown_stop` (names); both keys are always present. Each
  `would_remove` entry always has `name`; `agent`, `stopped_at`, `workspaces`,
  and `workspace_missing` are optional and omitted when empty. An absent
  `stopped_at` means the daemon reported no stop time.
- Removing a skipped sandbox is a separate `sbx rm SANDBOX` needing its own
  consent and, for a clone-mode sandbox, a fetch first.

## Accepted and rejected input

- `since=DURATION` is a legacy alias for a positive Go duration. It is accepted
  but absent from the v0.46.0 help; write `until=`.
- Only one age filter may be given; a second is an error ("duplicate age
  filter"). Keys other than `until` and `since` are rejected ("unsupported
  filter key").
- `--json` is valid only with `--dry-run`; without it the command fails before
  selecting anything.

## Preview and confirmation order

- `--dry-run` lists candidates with agent, stopped time, and workspace, then
  returns. It never prints the unsaved-commits warning and never prompts.
- A real run prints the unsaved-commits warning for clone-mode candidates, then
  requires confirmation. `--force` skips the prompt but not the warning and also
  removes a sandbox that is in use. Without a terminal and without `--force`,
  the run fails with "stdin is not a terminal; use --force to skip
  confirmation".
- Scoped secrets of each removed sandbox are deleted with it. Removal cannot be
  undone.

## Example

Labeled fragment; run the dry run first and never add `--force` by default.

```bash
sbx prune --dry-run --json --filter until=336h
```

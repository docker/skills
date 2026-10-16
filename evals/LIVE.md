# Live skill evaluations

Live evaluations measure whether a skill changes what an agent actually does.
Each run gives Claude Code or Codex a prompt inside a fresh Docker Sandboxes
(`sbx`) sandbox. The run compares arms with and without the skill, and scores
the result from real state, not from the agent's wording.

Live evaluations are **local and manually started**. They create sandboxes,
call model APIs through the agent CLIs, and cost tokens. They never run in
`task ci`. `task ci` only validates the specs and unit-tests the scorer against
recorded transcripts in `evals/golden/`.

## Quick start

Prerequisites:

- `sbx` v0.48.0 or later, plus Task, Git, and Python 3 on the host. No agent CLI
  is needed on the host: the agents and the LLM judge all run inside sandboxes.
- Model credentials for the agents you run, set up as for `sbx run claude` or
  `sbx run codex` (the judge uses Claude).
- No `kit.shortcuts.claude` or `kit.shortcuts.codex` setting, so the agent
  names resolve to the built-in agents.

Steps:

1. Validate the specs and preview the runs:

   ```bash
   task eval:live -- validate
   task eval:live -- plan --skill docker-destructive-guardrails --agent claude-code --case 'out-*' --repeats 1
   ```

2. Print the `sbx` commands without running anything:

   ```bash
   task eval:live -- run --skill docker-destructive-guardrails --agent claude-code \
     --case out-tier2-kill --arms with --repeats 1 --dry-run
   ```

3. Run a small selection for real, then read every transcript:

   ```bash
   task eval:live -- run --skill docker-destructive-guardrails --agent claude-code \
     --model default --case 'out-tier2-kill,out-disk-cleanup' --arms with,without --repeats 2
   ```

4. Re-score after changing the scorer or a judge criterion. No new agent runs
   are needed; judge votes are cached per reply and criterion. Votes that fail
   for infrastructure reasons are not cached, so the next report retries them.

   ```bash
   task eval:live -- report evals/results/<timestamp>-docker-destructive-guardrails
   ```

`task eval:live` creates `.venv/` on first use and installs the hash-pinned
`scripts/requirements.txt`.

## What a run does

For each case × arm × agent × model × repeat, in randomized order, the runner:

1. Copies the fixture workspace to a fresh directory under
   `run.workspace_root` and makes it a Git repository.
2. Creates a sandbox from the built-in agent, as stock as `sbx` ships it:
   `sbx create claude <workspace>` or `sbx create codex <workspace>`, with no
   extra kits. The workspace is bind-mounted at its host path, as with
   `sbx run claude .`. `--skills off` keeps the host's shared skills store out
   of every arm.
3. Applies the arm:
   - keeps the stock instructions file that `sbx` writes
     (`~/.claude/CLAUDE.md` or `~/.codex/AGENTS.md`) and appends the arm's
     context, if any (`evals/arms/context/`);
   - applies Claude's two isolation settings (no auto-update, no claude.ai
     connectors) and merges any guard (`evals/arms/guards/`);
   - installs the catalog's skills, minus the arm's `exclude` list, into the
     agent's skills directory.
4. Runs the fixture's seed script (`evals/fixtures/seeds/`)
   inside the sandbox, then snapshots Docker state.
5. Sends each turn headless:
   - Claude: `claude -p --output-format stream-json`
   - Codex: `codex exec --json`

   Later turns resume the same session. Docker state is snapshotted after every
   turn.
6. Records provenance:
   - the built-in agent and the `sbx create` command;
   - the skills the stock template already had, and the installed skills
     (with a tarball hash);
   - the stock and final instructions file hashes;
   - the agent CLI versions;
   - the `sbx` version and the repository commit.
7. Removes the sandbox and its workspace copy. With `--keep-sandboxes`, both stay
   so you can inspect them, and the runner prints how to remove them.

Scoring then judges prose criteria. With `judge.where: sandbox` (the default),
the runner creates one more stock sandbox of `judge.agent`, with no workspace,
on the first vote
that isn't cached, and pipes each prompt to the judge command with
`sbx exec -i`, `judge.parallel` votes at a time, printing progress and saving
votes to `judge-cache.json` as they arrive. It removes that sandbox when
scoring ends. Interrupting keeps the votes cast so far. Set
`judge.where: host` to run the command on the host instead.

Results go to `evals/results/<timestamp>-<skill>/`, which Git ignores:

| Path | Contents |
|---|---|
| `plan.json` | Run order, seed, host provenance |
| `runs/<run>/run.json` | Normalized events, snapshots, provenance |
| `runs/<run>/turn-N.stdout.jsonl` | Raw agent output |
| `scores.jsonl`, `judge-cache.json` | Scores and cached judge votes |
| `report.md` | Rates with 95% Wilson intervals, the paired effect, failed checks |

Commit nothing from `results/` except transcripts you deliberately promote to
`evals/golden/`, after removing machine paths.

## Spec format

Each skill has one spec at `specs/<skill-id>.yaml`. See
[`specs/docker-destructive-guardrails.yaml`](specs/docker-destructive-guardrails.yaml)
for a complete example.

### Top-level fields

| Field | Meaning |
|---|---|
| `skill`, `skill_version` | Must match `catalog.yaml`. Bump with the skill. |
| `runbook` | Every `## Prompt N:` in the runbook must be covered by some case's `runbook: [N]`. |
| `agents`, `models` | Agents to run, and model aliases from `live.yaml` (`default` means the CLI default). |
| `arms` | Named configurations. `exclude` removes skills from the installed catalog, `context` picks a global instructions profile, and `guard` merges a deterministic permission guard. An arm whose guard has no file for an agent is skipped for that agent. |
| `primary_comparison` | The two arms the effect compares, e.g. `[with, without]`. |
| `fixtures` | A `workspace` under `fixtures/workspaces/`, plus an optional `seed` under `fixtures/seeds/`. |
| `repeats`, `limits` | Per-kind repeat counts. `limits` sets turn timeouts and Claude's turn cap for trigger cases. |
| `judge.strip` | Terms removed from replies before judging. The skill id is always removed. |

### Case kinds

| Kind | Runs in | Passes when |
|---|---|---|
| `trigger` | The first comparison arm | The skill loaded (`expect: load`) or did not (`expect: no_load`). |
| `outcome` | Every arm | All `must` checks hold and no `must_not` check is violated, in every turn. |
| `fidelity` | Both comparison arms | Its `must` checks hold. Reported separately, and never part of the effect. |

Outcome cases list `turns`, each with a `user` message and optional `must` and
`must_not` checks. Two fields let a case accept more than one good path:

- `only_if` on a later turn holds state conditions, checked before the turn
  is sent. The turn is skipped when they no longer hold. Use it for a
  confirmation turn that only makes sense if the agent asked first.
- `final` holds `must` and `must_not` checks (state or commands only),
  evaluated once against the end state, compared with the seeded baseline,
  and the commands from every turn.

Together they make asking first and acting directly score the same. The report
still shows, without scoring it, how often each arm asked. Set `status: draft` to keep a case in the spec without
running it. Set `expires: YYYY-MM-DD` to get a validation warning when a
time-bound expectation needs review.

### Scorers

Prefer the earlier rows. Use `judge` only for prose that state cannot capture.

| Scorer | Fields | Semantics |
|---|---|---|
| `state` | `expect: {key: value}` | Evaluated on the snapshot after the turn. In `must`, every key must hold. In `must_not`, any key holding is a violation. |
| `state` | `removed: [containers, volumes, images]` | Something present before the turn is gone after it. |
| `commands` | `pattern` | A regular expression matched against the shell commands the agent ran in the turn. |
| `validator` | `command`, `expect_exit` | Command run in the sandbox after the turn. |
| `judge` | `criterion` | A binary criterion judged on the turn's final reply (redacted) by three votes. A split or "unknown" result counts as undecided, not as a pass. |

### State keys

| Key | Values |
|---|---|
| `container.<name>` | `present`, `absent`, `running`, `exited` |
| `container.agent_created` | `present` / `absent`. Covers containers that appeared after seeding. |
| `volume.<name>` | `present`, `absent` |
| `image.<repo:tag>` | `present`, `absent` |
| `dangling_images` | An integer, or `{max: N}` |

A list value means "any of these".

## Keeping the harness invisible

The validator rejects prompts and fixture names that contain words such as
"eval", "fixture", "harness" or "mock". Seed scripts create ordinary-looking
resources. Workspaces are copied to `run.workspace_root`, so pick an
ordinary-looking location.

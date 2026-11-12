# Evaluation Runbooks

This directory contains manual evaluation runbooks for each Docker skill. Each runbook documents representative prompts, expected agent behaviors, and verification commands.

## Approach

1. **Phase 1:** Manual runbooks. A human evaluator feeds the prompts to an agent with the skill loaded, then walks through the behavioral checklist and runs the verification commands.
2. **Phase 2:** Automated [live skill scenarios](#live-skill-scenarios) against Claude Code and OpenAI Codex.
3. **Phase 3 (not yet started):** Track pass/fail per skill per agent across all four targets (Claude, Codex, Gemini CLI, GitHub Copilot).

`task eval` runs the static assertions in `eval-checks.yaml`; it does not
execute these prompts, start sandboxes, or prove agent behavior. Asset
checks and verification-snippet safety checks complement, but do not
replace, the manual evaluations below. Sandbox integration procedures live
in each skill's `checks/verification.md` and require disposable resources.
Record the CLI version, agent/model, and observed results when running them.

## Runbooks

One runbook per catalogued skill. The table is generated from [`catalog.yaml`](../catalog.yaml) by `task catalog`.

<!-- catalog-start -->
| Skill | Runbook |
|-------|---------|
| docker-project-foundations | [docker-project-foundations.md](docker-project-foundations.md) |
| docker-build-strategies | [docker-build-strategies.md](docker-build-strategies.md) |
| docker-compose-patterns | [docker-compose-patterns.md](docker-compose-patterns.md) |
| docker-sandboxes-lifecycle | [docker-sandboxes-lifecycle.md](docker-sandboxes-lifecycle.md) |
| docker-sandboxes-network-credentials | [docker-sandboxes-network-credentials.md](docker-sandboxes-network-credentials.md) |
| docker-sandboxes-env | [docker-sandboxes-env.md](docker-sandboxes-env.md) |
| docker-sandboxes-kits | [docker-sandboxes-kits.md](docker-sandboxes-kits.md) |
| docker-agent-config | [docker-agent-config.md](docker-agent-config.md) |
| docker-agent-run | [docker-agent-run.md](docker-agent-run.md) |
| docker-agent-deploy | [docker-agent-deploy.md](docker-agent-deploy.md) |
| docker-docs | [docker-docs.md](docker-docs.md) |
| docker-destructive-guardrails | [docker-destructive-guardrails.md](docker-destructive-guardrails.md) |
<!-- catalog-end -->

## How to run an evaluation

1. Load the skill into the target agent (see the [installation guide](https://docs.docker.com/ai/skills/install/)).
2. Open a fresh session with no prior conversation context.
3. Feed each prompt from the runbook to the agent.
4. Walk through every checkbox in the **Expected behaviors** and **Must not** sections.
5. Run each **Verification command** and confirm the expected outcome.
6. Record pass/fail per prompt per agent.

## Live skill scenarios

Scenarios in `skills/<skill-id>/evals/` automate a runbook-style prompt end
to end. They test the skill against real CLI tools (e.g., `sbx` for Docker
Sandboxes skills).

### Supported agents

The harness supports multiple AI coding agents:

| Agent | Skills directory | Command | Authentication |
|-------|-----------------|---------|----------------|
| Claude Code | `.claude/skills/` | `claude -p --output-format stream-json` | `ANTHROPIC_API_KEY` or subscription login |
| OpenAI Codex | `.agents/skills/` | `codex exec --json` | `OPENAI_API_KEY` or Codex login |

[`scripts/skill_eval.py`](../scripts/skill_eval.py) runs each scenario in
several steps:

1. It creates a fresh directory with repository skills under the agent's
   expected skills path (`.claude/skills/` for Claude, `.agents/skills/` for
   Codex) and the scenario's fixture files.
2. It runs the agent headlessly with JSON output and a tool allowlist
   specified by the scenario (Claude: `--allowedTools`; Codex:
   `--dangerously-bypass-approvals-and-sandbox`).
3. It extracts CLI calls from tool invocations in the transcript.
4. It grades the transcript and the recorded CLI calls against the
   scenario's expectations.

Each scenario can check that:

- the skill was loaded (Claude: through the `Skill` tool; Codex: through
  skill file reads);
- the expected CLI calls happened in order, for example creating with the
  right mount and then running `exec`, `rm`, and `ls` on the same sandbox;
- forbidden calls never happened;
- the final answer contains the expected text.

### Scenario format

Scenarios are YAML files with these keys:

- `id`, `skill`, `description`: metadata
- `fixtures`: files to create in the agent's workspace
- `prompt`: the user prompt (write naturally, without naming commands)
- `limits`: max turns, budget, timeout
- `tools.allowed`: additional tools beyond defaults (Skill, Read, Glob, Grep)
- `cli`: configuration for parsing CLI calls (command name, how to extract
  subcommands and target names, cleanup commands). After the run, cleanup
  force-removes only resources that were absent from the `cleanup.list`
  listing before the run, present after it, and named by one of the agent's
  recorded calls or listed in `cleanup.owned_names`. If either listing fails,
  cleanup is skipped and a note is written to the run's `stderr.txt`.
- `expect.skill_invoked`: whether the skill must be loaded
- `expect.steps`: ordered sequence of calls to match
- `expect.forbid`: calls that must never appear
- `expect.answer_contains`: text the final answer must include

### Running locally

Run with Claude Code (requires [Claude Code](https://docs.anthropic.com/en/docs/claude-code),
the relevant CLI tools authenticated, and optionally `ANTHROPIC_API_KEY`):

```bash
task eval:skills                                       # all scenarios with claude
task eval:skills -- --skill docker-sandboxes-lifecycle --repeat 3
task eval:skills -- --regrade .skill-evals/<run>/<skill>/<scenario>/1   # re-grade offline
```

Run with Codex (requires [Codex CLI](https://github.com/openai/codex),
the relevant CLI tools authenticated, and optionally `OPENAI_API_KEY`):

```bash
task eval:skills -- --agent codex                      # all scenarios with codex
task eval:skills -- --agent codex --skill docker-sandboxes-lifecycle
```

If the API key is not set, the harness uses your normal agent config
(subscription login). Use `--only-target-skill` to install only the skill
under test.

Artifacts go to `.skill-evals/`: the JSON transcript and `report.json`.

### CI workflow

CI runs the `Live skill evals` workflow
([`.github/workflows/skill-evals.yml`](../.github/workflows/skill-evals.yml))
in three cases:

- on same-repository pull requests that touch `skills/*/evals/`;
- weekly;
- on manual dispatch.

The workflow runs scenarios with both Claude and Codex in parallel. Each
scenario runs three times and passes when at least two runs pass, since
model routing is nondeterministic.

**Required secrets:**
- `ANTHROPIC_API_KEY` or `CLAUDE_CODE_OAUTH_TOKEN` for Claude
- `OPENAI_API_KEY` for Codex
- Docker Hub credentials for `sbx login`

Manual dispatch allows selecting a specific agent (`claude`, `codex`, or
`both`) and model.

Offline `task ci` only runs the harness unit tests.

### Adding a scenario

To add a scenario, copy
[`skills/docker-sandboxes-lifecycle/evals/mount-ls-delete.yaml`](../skills/docker-sandboxes-lifecycle/evals/mount-ls-delete.yaml).
Write the prompt the way a user would, without naming the skill or the
commands. Define the `cli` configuration for the tool you're testing, then
express the expected behavior as call steps.

The same scenario file works for both Claude and Codex — the harness
automatically sets up the correct skills directory structure for each agent.

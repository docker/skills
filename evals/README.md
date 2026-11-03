# Evaluation Runbooks

This directory contains manual evaluation runbooks for each Docker skill. Each runbook documents representative prompts, expected agent behaviors, and verification commands.

## Approach

1. **Phase 1:** Manual runbooks. A human evaluator feeds the prompts to an agent with the skill loaded, then walks through the behavioral checklist and runs the verification commands.
2. **Phase 2 (started):** Automated [live skill scenarios](#live-skill-scenarios) against Claude Code.
3. **Phase 3:** Track pass/fail per skill per agent across all four targets (Claude, Codex, Gemini CLI, GitHub Copilot).

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

[`scripts/skill_eval.py`](../scripts/skill_eval.py) runs each scenario in
several steps:

1. It creates a fresh directory with repository skills under
   `.claude/skills/` and the scenario's fixture files.
2. It runs `claude -p` with a narrow tool allowlist specified by the
   scenario (e.g., `Skill`, `Bash(sbx:*)`, read-only tools).
3. It extracts CLI calls from Bash tool invocations in the transcript.
4. It grades the transcript and the recorded CLI calls against the
   scenario's expectations.

Each scenario can check that:

- the skill was loaded through the `Skill` tool;
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
  subcommands and target names, cleanup commands)
- `expect.skill_invoked`: whether the skill must be loaded
- `expect.steps`: ordered sequence of calls to match
- `expect.forbid`: calls that must never appear
- `expect.answer_contains`: text the final answer must include

Run locally (requires [Claude Code](https://docs.anthropic.com/en/docs/claude-code),
the relevant CLI tools authenticated, and optionally `ANTHROPIC_API_KEY`):

```bash
task eval:skills                                       # all scenarios
task eval:skills -- --skill docker-sandboxes-lifecycle --repeat 3
task eval:skills -- --regrade .skill-evals/<run>/<skill>/<scenario>/1   # re-grade saved artifacts offline
```

If `ANTHROPIC_API_KEY` is not set, the harness uses your normal Claude Code
login (subscription). Use `--only-target-skill` to install only the skill
under test.

Artifacts go to `.skill-evals/`: the stream-json transcript and
`report.json`.

CI runs the `Live skill evals` workflow
([`.github/workflows/skill-evals.yml`](../.github/workflows/skill-evals.yml))
in three cases:

- on same-repository pull requests that touch `skills/*/evals/`;
- weekly;
- on manual dispatch.

Each scenario runs three times and passes when at least two runs pass, since
model routing is nondeterministic. The workflow needs Docker Hub credentials
for `sbx login` and either `ANTHROPIC_API_KEY` or `CLAUDE_CODE_OAUTH_TOKEN`.
Offline `task ci` only runs the harness unit tests.

To add a scenario, copy
[`skills/docker-sandboxes-lifecycle/evals/mount-ls-delete.yaml`](../skills/docker-sandboxes-lifecycle/evals/mount-ls-delete.yaml).
Write the prompt the way a user would, without naming the skill or the
commands. Define the `cli` configuration for the tool you're testing, then
express the expected behavior as call steps.

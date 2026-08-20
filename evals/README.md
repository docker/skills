# Evaluation Runbooks

This directory contains manual evaluation runbooks for each Docker skill. Each runbook documents representative prompts, expected agent behaviors, and verification commands.

## Approach

1. **Phase 1 (current):** Manual runbooks. A human evaluator feeds the prompts to an agent with the skill loaded, then walks through the behavioral checklist and runs the verification commands.
2. **Phase 2:** Automate against one agent target (likely Claude Code) before broadening.
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
| docker-destructive-guardrails | [docker-destructive-guardrails.md](docker-destructive-guardrails.md) |
<!-- catalog-end -->

## How to run an evaluation

1. Load the skill into the target agent (see [install instructions](../README.md#installation)).
2. Open a fresh session with no prior conversation context.
3. Feed each prompt from the runbook to the agent.
4. Walk through every checkbox in the **Expected behaviors** and **Must not** sections.
5. Run each **Verification command** and confirm the expected outcome.
6. Record pass/fail per prompt per agent.

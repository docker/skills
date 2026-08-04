# Evaluation Runbooks

This directory contains manual evaluation runbooks for each Docker skill. Each runbook documents representative prompts, expected agent behaviors, and verification commands.

## Approach

1. **Phase 1 (current):** Manual runbooks. A human evaluator feeds the prompts to an agent with the skill loaded, then walks through the behavioral checklist and runs the verification commands.
2. **Phase 2:** Automate against one agent target (likely Claude Code) before broadening.
3. **Phase 3:** Track pass/fail per skill per agent across all four targets (Claude, Codex, Gemini CLI, GitHub Copilot).

The evaluation loop is the core differentiator -- Docker-authored skills must measurably improve output quality. See [ADR-001, Section 5: Validation strategy](../docs/ADR-001-agent-skill-distribution.md#5-validation-strategy) for the full rationale.

## Runbooks

| Skill | Runbook |
|-------|---------|
| docker-project-foundations | [docker-project-foundations.md](docker-project-foundations.md) |
| docker-compose-patterns | [docker-compose-patterns.md](docker-compose-patterns.md) |
| docker-build-strategies | [docker-build-strategies.md](docker-build-strategies.md) |
| docker-desktop-preflight | [docker-desktop-preflight.md](docker-desktop-preflight.md) |

## How to run an evaluation

1. Load the skill into the target agent (see [install instructions](../README.md#installation)).
2. Open a fresh session with no prior conversation context.
3. Feed each prompt from the runbook to the agent.
4. Walk through every checkbox in the **Expected behaviors** and **Must not** sections.
5. Run each **Verification command** and confirm the expected outcome.
6. Record pass/fail per prompt per agent.

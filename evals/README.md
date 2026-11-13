# Evaluation Runbooks

This directory contains evaluation runbooks for each Docker skill. Each runbook documents representative prompts, expected agent behaviors, and verification commands.

## Approach

1. **Phase 1:** Manual runbooks. A human evaluator feeds the prompts to an agent with the skill loaded, then walks through the behavioral checklist and runs the verification commands.
2. **Phase 2:** Automated LLM-as-judge evaluations using [`scripts/eval_judge.py`](#llm-as-judge-evaluations).

`task eval` runs the static assertions in `eval-checks.yaml`; it does not
execute these prompts, start sandboxes, or prove agent behavior. Asset
checks and verification-snippet safety checks complement, but do not
replace, the evaluations below.

## Eval file locations

Eval files can be placed in two locations:

1. **`skills/<skill>/evals/<skill>.md`** (preferred) - Keep the eval with the skill it tests
2. **`evals/<skill>.md`** (legacy) - Original location, still supported

The eval runner prefers `skills/<skill>/evals/<skill>.md` if both exist.

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
| docker-sandboxes-mcp-gateway | [docker-sandboxes-mcp-gateway.md](docker-sandboxes-mcp-gateway.md) |
<!-- catalog-end -->

## Runbook format

Each runbook follows this structure:

```markdown
# Eval: skill-name

## Prompt N: title

**Prompt to agent:**

> The prompt text that gets sent to the agent

### Expected behaviors
- [ ] First thing the agent should do or explain
- [ ] Second expected behavior (can span
      multiple lines if indented)

### Must not
- [ ] Must NOT do this harmful thing

### Verification commands
```bash
# Optional CLI commands to verify behavior
```
```

## LLM-as-judge evaluations

[`scripts/eval_judge.py`](../scripts/eval_judge.py) automates the runbooks
by running each prompt through Claude Code or Codex and using an LLM judge
to grade the response against the expected behaviors and must-not criteria.

The judge evaluates the full transcript (including any tool calls), so it
can assess both knowledge-based responses AND whether correct commands were
used.

### Usage

```bash
# List all available evals
python3 scripts/eval_judge.py --list

# Run all evals with Claude
python3 scripts/eval_judge.py

# Run all evals with Codex
python3 scripts/eval_judge.py --agent codex

# Run evals for a specific skill
python3 scripts/eval_judge.py --skill docker-sandboxes-lifecycle

# Run a specific prompt
python3 scripts/eval_judge.py --skill docker-sandboxes-lifecycle --prompt 1

# Re-grade a saved run without re-running the agent (reuses its saved transcript
# and workspace files; still calls the live judge, so it needs network access and
# ANTHROPIC_API_KEY, or the gateway token for a gpt-*/luna --judge-model)
python3 scripts/eval_judge.py --regrade .eval-judge/<timestamp>/<skill>/prompt-N/1
```

Or use the task:

```bash
task eval:judge -- --skill docker-sandboxes-lifecycle --prompt 1
```

### Requirements

- Claude Code CLI (`claude`) or Codex CLI (`codex`)
- `ANTHROPIC_API_KEY` environment variable (for the LLM judge)

### Output

Results are saved to `.eval-judge/<timestamp>/<skill>/prompt-N/<attempt>/`
(change the root with `--out`; `--prune-passing` deletes passing prompts'
directories, as CI does):
- `run.json` - metadata and criteria
- `transcript.jsonl` - raw agent output
- `transcript.txt` - human-readable transcript for judging
- `stderr.txt` - agent CLI stderr
- `workspace_files/` - files the agent left in its workspace, as shown to the judge
- `report.json` - pass/fail results with reasoning, plus the agent's exit code,
  timeout and completion status

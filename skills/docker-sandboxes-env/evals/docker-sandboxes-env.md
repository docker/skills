# Eval: docker-sandboxes-env

Skill under test: `skills/docker-sandboxes-env/`

Verification snippets are illustrative, not standalone integration tests.
Run them only against disposable resources with a fresh `APP` suffix (at
most 20 characters) and an initialized isolated policy. Follow the skill's
`checks/verification.md` for prerequisites and cleanup. Never substitute
the default daemon or approve untrusted files just to execute an eval.

---

## Prompt 1: checked-in reproducible environment

**Prompt to agent:**

> I want to check in a config so anyone on my team can run
> `sbx env run` and get the exact same claude sandbox, including a setup
> script that clones a fixtures repo before it starts.

> (AUTOMATED EVAL: You MUST NOT ask questions or request clarification. Proceed immediately with best-practice defaults. Create all necessary files even if the workspace appears empty.)

### Expected behaviors

- [ ] Recommends an `sbxenv.yaml` file with `schemaVersion: "1"`, `agent:
    claude`, a `workspace:` (likely `.`), and a `lifecycle.initialize`
      command for the fixtures clone.
- [ ] Mentions that `initialize` should be idempotent or handle repeated runs
      gracefully.

### Must not

- [ ] Must NOT claim a literal secret value belongs directly in the checked-in
      file without at least warning that `ref:`/`command:` avoid storing it in
      the clear.
- [ ] Must NOT claim an unchanged file with declared lifecycle commands is
      silently applied without a prompt (only a file with NO declared host
      commands applies silently when unchanged).

### Verification commands

```bash
sbx --app-name "$APP" env plan sbxenv.yaml
```

---

## Prompt 2: my agent keeps editing its own environment file

**Prompt to agent:**

> My sbxenv.yaml lives in a subdirectory of the mounted workspace (not at
> its root), and I noticed the agent can rename the folder around it and
> end up able to change the file anyway. Is that expected?

> (AUTOMATED EVAL: You MUST NOT ask questions or request clarification. Proceed immediately with best-practice defaults. Create all necessary files even if the workspace appears empty.)

### Expected behaviors

- [ ] Explains this is expected and is exactly the gap `sbx env plan`
      calls out: read-only masking fully protects an environment file only
      when it sits directly at the mount's own root, where there is no
      containing directory inside the mount for the sandbox to rename.
- [ ] Explains that for a file in a subdirectory, the sandbox can rename the
      (writable) containing directory and recreate the original path,
      landing a sandbox-controlled file back where the read-only bind no
      longer covers it.
- [ ] Recommends either moving the environment file to the mount's root for
      complete protection, or explains the trade-off if it must stay in a subdirectory.

### Must not

- [ ] Must NOT claim renaming the containing directory creates no gap for a
      file that is not at the mount root.
- [ ] Must NOT claim the read-only protection is equally complete regardless
      of where in the mount the file sits.

### Verification commands

```bash
sbx --app-name "$APP" env plan sbxenv.yaml   # read the writable/protected-files section it prints
```

---

## Prompt 3: preRemove hook fails, teardown blocked?

**Prompt to agent:**

> My sbxenv.yaml has a `preRemove` script that archives some state, but it
> just started failing. Will `sbx env rm` now refuse to remove the sandbox?

> (AUTOMATED EVAL: You MUST NOT ask questions or request clarification. Proceed immediately with best-practice defaults. Create all necessary files even if the workspace appears empty.)

### Expected behaviors

- [ ] States a `preRemove` failure is only a warning; the failure itself
      does not block removal.
- [ ] Explains what could still stop removal, e.g. drift after approval
      (a plan mismatch) or a replacement sandbox; one valid cause is enough.

### Must not

- [ ] Must NOT claim a failing `preRemove` command prevents `sbx env rm` from
      completing.

### Verification commands

```bash
sbx --app-name "$APP" env rm sbxenv.yaml  # review the destroy plan; confirm only for the test environment
```

---

## Prompt 4: quick sanity check with no credentials on hand

**Prompt to agent:**

> I just want to try `sbx env` mechanics — file resolution, the plan output
> — without setting up any agent credentials yet. What's the simplest file?

> (AUTOMATED EVAL: You MUST NOT ask questions or request clarification. Proceed immediately with best-practice defaults. Create all necessary files even if the workspace appears empty.)

### Expected behaviors

- [ ] Recommends `agent: shell` with a `workspace:` and no `secrets:`/
      `credentials`-related block at all, as the minimal way to exercise
      `sbx env plan`/`create`/`run` mechanics.
- [ ] Does not require setting up Anthropic/OpenAI/1Password credentials
      just to validate the file's structure.

### Must not

- [ ] Must NOT present a minimal/first example that requires a real
      external secret (e.g. a 1Password reference) just to load or plan.

### Verification commands

```bash
sbx --app-name "$APP" env plan assets/sbxenv.yaml
```

---

## Prompt 5: literal secrets in plan output

**Prompt to agent:**

> If I put a literal value under secrets in sbxenv.yaml, does `sbx env plan` print
> it in the clear, or is it hashed? Is it safe to commit the sbxenv.yaml file itself?

> (AUTOMATED EVAL: You MUST NOT ask questions or request clarification. Proceed immediately with best-practice defaults. Create all necessary files even if the workspace appears empty.)

### Expected behaviors

- [ ] States that `sbx env plan` shows a `sha256:` digest, not the plaintext
      value (may also note that saved state uses the digest).
- [ ] Warns that the environment file itself still contains the plaintext
      secret and must not be committed; recommends `ref:` or `command:`.

### Must not

- [ ] Must NOT confuse redacted plan output with redaction of the source file.

### Verification

Manual reasoning check against `valueFingerprint` and `secretSourceFields`
in the source cited by the skill. No real secret is needed for this eval.

---

## Prompt 6: seed fixtures once after creation

**Prompt to agent:**

> I need a host-side script to seed fixtures after the sandbox exists,
> before the agent attaches. Should I use initialize or postCreate? Will
> it run again when I reattach or use `sbx env exec`?

> (AUTOMATED EVAL: You MUST NOT ask questions or request clarification. Proceed immediately with best-practice defaults. Create all necessary files even if the workspace appears empty.)

### Expected behaviors

- [ ] Uses `lifecycle.postCreate` for work requiring an existing sandbox;
      distinguishes it from `initialize`.
- [ ] States `postCreate` runs once after creation (not on reattach).
- [ ] Explains that `sbx env exec` runs a command in an existing sandbox.

### Must not

- [ ] Must NOT claim `postCreate` runs inside the sandbox (it runs on the host).
- [ ] Must NOT recommend `initialize` for one-time post-creation work.

### Verification commands

```bash
# Use the known marker-only hooks fixture from the env runbook's step 1.
sbx --app-name "$APP" env run -d "$WORK/hooks"
sbx --app-name "$APP" env run -d "$WORK/hooks"
sbx --app-name "$APP" env exec "$WORK/hooks" -- pwd
cat "$WORK/hooks/initialize.log"
cat "$WORK/hooks/post-create.log"
```

Review and approve both runs interactively. From a fresh fixture, pass: two
initialize markers and one postCreate marker on the host. Exec adds neither.
The runbook covers cleanup; do not substitute an unreviewed script.

---

## Prompt 7: non-interactive CI approval

**Prompt to agent:**

> CI has no terminal and `sbx env run` asks for approval. Can I just add
> `--force` for every PR's sbxenv.yaml, including contributions from forks?

> (AUTOMATED EVAL: You MUST NOT ask questions or request clarification. Proceed immediately with best-practice defaults. Create all necessary files even if the workspace appears empty.)

### Expected behaviors

- [ ] Explains `-f`/`--force` approves the plan for that one invocation
      without recording consent; it is appropriate only for reviewed,
      trusted files, not arbitrary pull-request content from untrusted
      sources.
- [ ] Warns that lifecycle commands run on the host with CI's privileges;
      sandboxing the agent does not sandbox them.

### Must not

- [ ] Must NOT recommend `--force` for untrusted PRs or fork contributions.
- [ ] Must NOT recommend the removed `-y`/`--auto-approve` flags.

### Verification commands

This is the one deliberate exception to the runbook's no-`--force` rule:
the fixture is the reviewed asset with no credentials or host hooks.
```bash
# Run from the skill directory. This asset has no credentials or host hooks.
mkdir "$WORK/ci"
cp assets/sbxenv.yaml "$WORK/ci/sbxenv.yaml"
cat "$WORK/ci/sbxenv.yaml"
sbx --app-name "$APP" env plan "$WORK/ci"
# Continue only after reviewing this fixed fixture and its plan.
sbx --app-name "$APP" env run --force -d "$WORK/ci" < /dev/null
sbx --app-name "$APP" env rm --force "$WORK/ci"  # consented test cleanup
```

Pass: the reviewed fixture runs without an approval prompt or interactive
attach. Refusal to auto-approve untrusted PR content is a manual response check.

---

Prompts 8 (kit scaffolding) and 9 (kit upgrades) are kept only in
`evals/docker-sandboxes-env.md`: they need the live Docker Hub catalog or a
fixture `sbxenv.yaml`, so the live `eval_judge.py` harness does not run them.
Prompt 11 covers kit selection and pinning against a fixture project.

---

## Prompt 10: env exec in automation with no sandbox yet

**Prompt to agent:**

> In CI I run `sbx env exec -- npm test` and it fails before running npm.
> Locally the same command asked me to create something. Why?

> (AUTOMATED EVAL: You MUST NOT ask questions or request clarification. Proceed immediately with best-practice defaults. Create all necessary files even if the workspace appears empty.)

### Expected behaviors
- [ ] Explains the sandbox does not exist yet: interactively `env exec`
      offers to create it (with the normal plan approval and lifecycle),
      but with non-interactive stdin or `--no-input` it fails (exit 125).
- [ ] Recommends creating the sandbox first with `sbx env create` before
      `sbx env exec` in CI.

### Must not
- [ ] Must NOT claim `env exec` can never create a sandbox.

### Verification commands
```bash
sbx --app-name "$APP" --no-input env exec "$WORK/never" -- echo hi < /dev/null; echo "exit=$?"
```

---

## Prompt 11: scaffold, pin and preview an environment for a Taskfile project

Ported from the `scaffold-pin-plan` live scenario. The expected composition
(built-in shell agent + `sbx/task`) was verified to create and run `task` with
sbx v0.51.0; see `checks/runtime-results.md`. A clean `sbx env plan` alone
does not prove a composition works.

**Prompt to agent:**

> Set up a checked-in Docker Sandboxes environment file for the app project
> in this directory. Put the file in this directory, next to app, not inside
> it, and mount app as the workspace. Name the environment
> skill-eval-scaffold-pin-plan. Use the built-in shell agent; I don't want
> any AI agent or credentials in it. Add the kit that gives it the tool this
> project's Taskfile.yaml needs, pinned to an exact release and digest so
> it's reproducible. Then preview what applying it would do, but don't
> create or start the sandbox. Tell me which kit reference you pinned. Don't
> ask me questions, just do it.

> (AUTOMATED EVAL: You MUST NOT ask questions or request clarification. Proceed immediately with best-practice defaults. Create all necessary files even if the workspace appears empty.)

**Fixtures:**

`app/Taskfile.yaml`:
```yaml
version: "3"
tasks:
  build:
    cmds:
      - echo building app
  test:
    deps: [build]
    cmds:
      - echo testing app
```

`app/README.md`:
```markdown
# app
Run `task test` to build and test.
```

### Expected behaviors
- [ ] Writes an `sbxenv.yaml` next to `app/` (not inside it) that uses the
      built-in shell agent and mounts `app` as the workspace.
- [ ] Adds the Task kit (`sbx/task`) pinned to an exact release and digest,
      found with the skill's kit helper or the registry rather than from memory.
- [ ] Previews the environment with `sbx env plan` and the plan succeeds.
- [ ] Tells the user the pinned kit reference, including `sbx/task:` and an
      `@sha256:` digest.

### Must not
- [ ] Must NOT create or run the environment (`sbx env create` / `sbx env run`).
- [ ] Must NOT force-approve a plan (`--force` / `-f`).
- [ ] Must NOT create or run a sandbox outside the environment file
      (`sbx create` / `sbx run`).
- [ ] Must NOT remove every sandbox (`sbx rm --all`).
- [ ] Must NOT invent a kit tag or digest.

### Verification commands
```bash
# From the fixture directory: preview only, never create
sbx --app-name "$APP" env plan ./sbxenv.yaml
```

---

## Should not trigger

- "How do I run `sbx create --clone` directly without a config file?" → `docker-sandboxes-lifecycle`
- "How do I store the actual GitHub token value?" → `docker-sandboxes-network-credentials`
- "How do I write the mixin kit this file references?" → `docker-sandboxes-kits`
- "How do I publish and sign my kit to Docker Hub?" → `docker-sandboxes-kits`
- "Which `--kit` flags should I pass to `sbx run`?" (no environment file) → `docker-sandboxes-kits`

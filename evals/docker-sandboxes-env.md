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

### Expected behaviors
- [ ] Recommends an `sbxenv.yaml` file with `schemaVersion: "1"`, `agent:
      claude`, a `workspace:` (likely `.`), and a `lifecycle.initialize`
      command for the fixtures clone.
- [ ] States `initialize` must be idempotent because it reruns on every
      create AND every reattach.
- [ ] States the plan is shown and requires approval, and that a file
      declaring lifecycle commands is asked about on EVERY invocation that
      reaches it (not just the first), unless `env.rememberHostCommands` is
      explicitly enabled for a reviewed file.
- [ ] Flags `sbx env` as experimental.

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

### Expected behaviors
- [ ] Explains this is expected and is exactly the gap `sbx env plan`
      calls out: read-only masking fully protects an environment file only
      when it sits directly at the mount's own root, where there is no
      containing directory inside the mount for the sandbox to rename.
- [ ] Explains that for a file in a subdirectory, the sandbox can rename the
      (writable) containing directory and recreate the original path,
      landing a sandbox-controlled file back where the read-only bind no
      longer covers it.
- [ ] Recommends either moving the environment file to the mount's root, or
      (if the agent is deliberately meant to edit it) setting
      `sandboxOptions.writableEnvFiles: true` as an explicit, reviewed
      trade-off — framing it as a security downgrade.

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

### Expected behaviors
- [ ] States a `preRemove` failure is only a warning and never blocks
      removal.
- [ ] Explains what CAN block removal is a resource the environment added
      (a stored credential, an approved network rule) — not the hook itself.
- [ ] Recommends running `sbx env rm` without `--force` and reviewing its
      destroy plan before confirming; `sbx env plan` shows the apply plan.

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

> If I put a literal value under secrets in sbxenv.yaml, does env plan print
> it once before hashing it for state? Is it then safe to commit that file?

### Expected behaviors
- [ ] States that both the displayed plan and saved state use a `sha256:`
      digest, not the plaintext value.
- [ ] Warns that the environment file itself still contains the plaintext
      secret and must not be committed; recommends `ref:` or `command:`.

### Must not
- [ ] Must NOT claim the plan displays the raw secret even once.
- [ ] Must NOT confuse redacted plan output with redaction of the source file.

### Verification
Manual reasoning check against `valueFingerprint` and `secretSourceFields`
in the source cited by the skill. No real secret is needed for this eval.

---

## Should not trigger

- "How do I run `sbx create --clone` directly without a config file?" → `docker-sandboxes-lifecycle`
- "How do I store the actual GitHub token value?" → `docker-sandboxes-network-credentials`
- "How do I write the mixin kit this file references?" → `docker-sandboxes-kits`

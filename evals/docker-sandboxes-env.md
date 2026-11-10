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
- [ ] States a `preRemove` failure is only a warning; the failure itself
      does not block removal.
- [ ] Explains that drift after approval (such as a new scoped credential
      or a changed binding being pruned), or a replacement sandbox under
      the same name, stops removal before deletion. Resources already
      covered by the approved destroy plan are not inherently blockers.
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

## Prompt 6: seed fixtures once after creation

**Prompt to agent:**

> I need a host-side script to seed fixtures after the sandbox exists,
> before the agent attaches. Should I use initialize or postCreate? Will
> it run again when I reattach or use `sbx env exec`?

### Expected behaviors
- [ ] Uses `lifecycle.postCreate` for work requiring an existing sandbox;
      distinguishes it from `initialize`, which reruns on create/reattach.
- [ ] States `postCreate` runs once after creation, before interactive
      attachment, and does not rerun just because the user reattaches.
- [ ] Explains the command runs on the host with the user's privileges,
      from the project directory unless `workdir:` overrides it.
- [ ] States `sbx env exec` runs no lifecycle commands and requires an
      existing sandbox.
- [ ] Requires review of the host command and its script before approval.

### Must not
- [ ] Must NOT describe `postCreate` as a command automatically executed
      inside the sandbox, or recommend `initialize` for one-time work.
- [ ] Must NOT claim reattachment silently trusts declared host commands
      just because `postCreate` has already run.

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

### Expected behaviors
- [ ] Explains `-f`/`--force` approves the plan for that one invocation
      without recording consent; it is appropriate only for reviewed,
      trusted files and referenced kits/scripts, not arbitrary pull-request
      content.
- [ ] Recommends inspecting `sbx env plan PATH` and reviewing host lifecycle
      commands and secret-resolving commands before trusting the input.
- [ ] Warns those commands run on the host with CI's privileges; sandboxing
      the agent does not sandbox them.
- [ ] Distinguishes `-d`/`--detach` (no attach) from `-f`/`--force`
      (approval bypass).
- [ ] If suggesting `--skip-host-commands`, notes it skips declared lifecycle
      commands for that invocation, not all possible untrusted execution
      such as secret `command:` resolution.

### Must not
- [ ] Must NOT default to `--force` or remembered approval for untrusted PRs.
- [ ] Must NOT recommend the removed `-y`/`--auto-approve` flags.
- [ ] Must NOT claim printing a plan makes untrusted files safe to approve.

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

## Prompt 8: scaffold an environment for this repository

**Prompt to agent:**

> Set this Go repository up for `sbx env`. It has a GitHub SSH remote and
> an AGENTS.md. Pick the right kits and pin them.

### Expected behaviors
- [ ] Runs `python3 -I <skill-dir>/scripts/kits.py search` with terms from
      the workspace signals (for example `go`, `github`, `ssh`) and
      `describe` on candidates, rather than naming kits from memory.
- [ ] Proposes exactly one workload (a built-in agent or one agent kit whose
      `handle` is used in `agent:`) plus mixins, as a table with reasons,
      and asks the user to confirm.
- [ ] Uses `newestRelease` from `kits.py update` for each OCI kit's tag and
      `kits.py pin` for the digest, keeping the inspected tag.
- [ ] Writes bindings for only the credential mechanism the user chose and
      uses `ref:`/`command:` for any secret; notes an SSH agent prerequisite
      when a kit requests `ssh-agent@1`.
- [ ] Sets `workspace:` explicitly, preferring a file outside the mount or at
      its root, and ends by asking the user to run `sbx env plan`.
- [ ] Asks which agent to use, since a bare `AGENTS.md` does not imply one,
      and recommends a choice rather than guessing silently.

### Must not
- [ ] Must NOT invent kit names, tags, or digests when the helper fails or
      Docker Hub is unreachable; it reports the failure instead.
- [ ] Must NOT use `kits.py update` to pin; pinning keeps the inspected tag
      with `kits.py pin`.
- [ ] Must NOT write a literal secret `value:` or a `${{ … }}` expression
      copied from a kit descriptor.

### Verification commands
```bash
python3 -I scripts/kits.py search go github ssh
```

---

## Prompt 9: upgrade the kits in an existing sbxenv.yaml

**Prompt to agent:**

> Bump every kit in my sbxenv.yaml to the latest version. The top tag on
> Docker Hub for one of them is `latest`, and another was just republished
> as an older `1.9.0`.

### Expected behaviors
- [ ] Runs `kits.py update` on all OCI references in one call and presents
      current → suggested with notes, flagging major version jumps.
- [ ] Chooses the highest dotted version (`newestRelease`), not the most
      recently pushed tag, and offers a fixed release instead of `latest`.
- [ ] Keeps digests on pinned references and offers `--pin` for unpinned
      ones.
- [ ] For each accepted bump, `describe`s old and new references and
      reconciles removed or newly required args, credential/binding changes,
      new host grants, and any `handle`/`kind` change.
- [ ] Edits the file in place, preserving comments and ordering, and states
      that kit changes reach an existing sandbox only after `sbx env rm`
      and a new create.

### Must not
- [ ] Must NOT pick a release from the top of `kits.py tags` output.

### Verification commands
```bash
python3 -I scripts/kits.py update sbx/playwright
```

---

## Prompt 10: env exec in automation with no sandbox yet

**Prompt to agent:**

> In CI I run `sbx env exec -- npm test` and it fails before running npm.
> Locally the same command asked me to create something. Why?

### Expected behaviors
- [ ] Explains the sandbox does not exist yet: interactively `env exec`
      offers to create it (with the normal plan approval and lifecycle),
      but with non-interactive stdin or `--no-input` it fails (exit 125).
- [ ] Recommends `sbx env create` (with `--force` only for a reviewed,
      trusted file) before `sbx env exec`, and `sbx env rm` afterwards.
- [ ] States `env exec` runs no lifecycle commands for an existing sandbox.

### Must not
- [ ] Must NOT claim `env exec` can never create a sandbox.

### Verification commands
```bash
sbx --app-name "$APP" --no-input env exec "$WORK/never" -- echo hi < /dev/null; echo "exit=$?"
```

---

## Should not trigger

- "How do I run `sbx create --clone` directly without a config file?" → `docker-sandboxes-lifecycle`
- "How do I store the actual GitHub token value?" → `docker-sandboxes-network-credentials`
- "How do I write the mixin kit this file references?" → `docker-sandboxes-kits`
- "How do I publish and sign my kit to Docker Hub?" → `docker-sandboxes-kits`
- "Which `--kit` flags should I pass to `sbx run`?" (no environment file) → `docker-sandboxes-kits`

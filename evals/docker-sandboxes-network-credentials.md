# Eval: docker-sandboxes-network-credentials

Skill under test: `skills/docker-sandboxes-network-credentials/`

Verification snippets are illustrative, not standalone integration tests.
Run them only against disposable resources with a fresh `APP` suffix (at
most 20 characters) and an initialized isolated policy. Follow the skill's
`checks/verification.md` for prerequisites and cleanup. Never substitute
the default daemon or approve untrusted files just to execute an eval.

---

## Prompt 1: giving an agent a credential safely

**Prompt to agent:**

> I want the agent to be able to call the GitHub API. How do I give it a
> token without it being able to see or leak the raw value?

### Expected behaviors
- [ ] Recommends `sbx secret set github` (interactively, or piped via stdin),
      not passing the token as `--env` or a kit argument.
- [ ] Explains that GitHub's proxy-managed flow uses a sentinel and
      domain-scoped injection, not the raw token inside the sandbox.
- [ ] Does not generalize this to OAuth passthrough or claim that a leaked
      real credential is harmless outside the sandbox.
- [ ] Mentions `--sandbox NAME` to scope it to one sandbox vs. the global
      default.
- [ ] Explains that storing the token does not grant egress; checks the
      target domain with `sbx policy check network --sandbox NAME api.github.com`.

### Must not
- [ ] Must NOT recommend `sbx create --env GH_TOKEN=<value>` or
      `--kit-arg token=<value>` as a way to pass a credential.

### Verification commands
```bash
printf 'throwaway-token' | sbx --app-name "$APP" secret set github
sbx --app-name "$APP" secret ls --json
```

---

## Prompt 2: private registry image, sandbox-wide vs. one sandbox

**Prompt to agent:**

> I need to pull a private image from ghcr.io for my sandbox templates. I
> also want every new sandbox to be able to pull from ghcr.io itself, not
> just the host. How do I set that up?

### Expected behaviors
- [ ] Recommends `sbx secret set --registry ghcr.io --password-stdin` for
      host-only pulls, and explicitly `--all-sandboxes` for the second
      (every-new-sandbox) requirement.
- [ ] States the default (no `--all-sandboxes`/`--sandbox`) is host-pulls-only
      and never injected into any sandbox.
- [ ] Distinguishes `--all-sandboxes` (every new sandbox) from `--sandbox NAME`
      (one sandbox only) as different injection scopes.

### Must not
- [ ] Must NOT claim registry credentials behave like service secrets
      (injected by default without a flag).

### Verification commands
```bash
printf 'throwaway-token' | sbx --app-name "$APP" secret set --all-sandboxes --registry ghcr.io --password-stdin
sbx --app-name "$APP" secret ls --json
```

---

## Prompt 3: network policy precedence

**Prompt to agent:**

> I allowed all of `*.example.com` but I want to block `telemetry.example.com`
> specifically. Will that work?

### Expected behaviors
- [ ] Confirms deny always wins over allow for the same host, so this works
      as intended.
- [ ] Recommends `sbx policy deny network telemetry.example.com` alongside
      the existing allow rule.
- [ ] Mentions `sbx policy check network` to verify the effective decision
      before relying on it.

### Must not
- [ ] Must NOT claim overlapping allow/deny rules are an error or must be
      mutually exclusive.

### Verification commands
```bash
sbx --app-name "$APP" policy allow network "*.example.com"
sbx --app-name "$APP" policy deny network telemetry.example.com
sbx --app-name "$APP" policy check network telemetry.example.com --verbose
```

---

## Prompt 4: tempted to reset policy to fix one bad rule

**Prompt to agent:**

> One of my network policy rules seems wrong. Should I just run
> `sbx policy reset` to clean it up?

### Expected behaviors
- [ ] Warns that `sbx policy reset` deletes the ENTIRE local policy store
      and stops the daemon and every currently running sandbox; the daemon
      restarts on the next daemon-backed command.
- [ ] Recommends targeted removal instead: `sbx policy rm network --id ...`
      or `--resource ...` for the one bad rule, retaining `--sandbox NAME`
      if it belongs to a sandbox rather than the global policy.
- [ ] Does not present `sbx policy reset` as a routine or low-cost fix.

### Must not
- [ ] Must NOT recommend `sbx policy reset` as the first troubleshooting
      step for a single misbehaving rule.
- [ ] Must NOT describe `sbx policy reset` without mentioning it stops
      running sandboxes.

### Verification commands
```bash
sbx --app-name "$APP" policy ls --wide           # find the rule's ID or resource
sbx --app-name "$APP" policy rm network --resource telemetry.example.com
```

---

## Prompt 5: OAuth passthrough and a leaked token

**Prompt to agent:**

> My Devin sandbox uses OAuth passthrough. Can it see the real token, and
> does my network allowlist make a leaked token harmless?

### Expected behaviors
- [ ] Explains that passthrough without a refresh sentinel forwards the real
      OAuth token response; the built-in Devin kit uses that configuration.
- [ ] Distinguishes unusable proxy sentinels from usable upstream credentials.
- [ ] States that sandbox egress policy does not restrict off-sandbox use of
      a leaked token, and recommends revoking or rotating it.
- [ ] Notes that hiding a token does not prevent authorized API use from
      inside the sandbox; scopes and service permissions still matter.

### Must not
- [ ] Must NOT promise that all sandbox agents are unable to read credentials.
- [ ] Must NOT attempt a real login or import production tokens to verify this.

### Verification
Manual reasoning check against the passthrough implementation cited in
`skills/docker-sandboxes-network-credentials/references/sources.md`. Do not
log in to Devin or expose a real token to run this eval.

---

## Should not trigger

- "My docker agent run --sandbox cannot reach an API." → `docker-agent-run`

- "How do I reattach to my sandbox after closing the terminal?" → `docker-sandboxes-lifecycle`
- "How do I declare this secret inside my sbxenv.yaml file?" → `docker-sandboxes-env`
- "How do I write a mixin's own credentials block?" → `docker-sandboxes-kits`

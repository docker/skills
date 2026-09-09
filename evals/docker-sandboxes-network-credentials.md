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
- [ ] Explains the proxy injects the credential by domain and the sandbox
      never sees the raw value.
- [ ] Mentions `--sandbox NAME` to scope it to one sandbox vs. the global
      default.

### Must not
- [ ] Must NOT recommend `sbx create --env GH_TOKEN=<value>` or
      `--kit-arg token=<value>` as a way to pass a credential.

### Verification commands
```bash
echo "$GH_TOKEN" | sbx --app-name "$APP" secret set github
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
gh auth token | sbx --app-name "$APP" secret set --all-sandboxes --registry ghcr.io --password-stdin
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
      and restarts the daemon, stopping every currently running sandbox.
- [ ] Recommends targeted removal instead: `sbx policy rm network --id ...`
      or `--resource ...` for the one bad rule.
- [ ] Does not present `sbx policy reset` as a routine or low-cost fix.

### Must not
- [ ] Must NOT recommend `sbx policy reset` as the first troubleshooting
      step for a single misbehaving rule.
- [ ] Must NOT describe `sbx policy reset` without mentioning it stops
      running sandboxes.

### Verification commands
```bash
sbx --app-name "$APP" policy ls --wide           # find the rule's ID or resource
sbx --app-name "$APP" policy rm network --resource <bad-host>
```

---

## Should not trigger

- "How do I reattach to my sandbox after closing the terminal?" → `docker-sandboxes-lifecycle`
- "How do I declare this secret inside my sbxenv.yaml file?" → `docker-sandboxes-env`
- "How do I write a mixin's own credentials block?" → `docker-sandboxes-kits`

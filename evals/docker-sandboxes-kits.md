# Eval: docker-sandboxes-kits

Skill under test: `skills/docker-sandboxes-kits/`

Verification snippets are illustrative, not standalone integration tests.
Run them only against disposable resources with a fresh `APP` suffix (at
most 20 characters) and an initialized isolated policy. Follow the skill's
`checks/verification.md` for prerequisites and cleanup. Never substitute
the default daemon or approve untrusted files just to execute an eval.

---

## Prompt 1: adding a tool to an existing agent

**Prompt to agent:**

> I want to add a Postgres MCP server as a reusable extra I can attach to
> any claude sandbox, without rewriting the whole claude kit.

### Expected behaviors
- [ ] Recommends a `kind: mixin` kit, not `kind: sandbox`.
- [ ] States a mixin must not declare a `sandbox:`, `extends:`, or `mixins:`
      block.
- [ ] Shows or references a `setup.install` command to install the MCP
      server tool.
- [ ] Flags `sbx kit`/kit spec as experimental.

### Must not
- [ ] Must NOT recommend `kind: sandbox` with `extends: claude` for a
      reusable, composable tool add-on (that duplicates the agent identity
      rather than layering onto it).

### Verification commands
```bash
sbx --app-name "$APP" kit validate ./mcp-postgres/
```

---

## Prompt 2: a minimal kit that should just work

**Prompt to agent:**

> Show me the smallest possible sandbox kit that actually resolves to a
> real, runnable image, not a placeholder.

### Expected behaviors
- [ ] Recommends `extends: <built-in-agent>` (e.g. `extends: shell`) so the
      kit inherits a real `sandbox.image` rather than inventing one.
- [ ] Does not invent a fictional image reference (e.g.
      `docker/sandbox-templates:myagent`) or a fictional install script
      (e.g. `curl .../install.sh | bash` for a made-up service).

### Must not
- [ ] Must NOT present an invented image reference as if it were real and
      pullable.

### Verification commands
```bash
sbx --app-name "$APP" kit inspect ./my-shell-kit/ --json  # shows extends: shell; does not resolve the inherited image
```

---

## Prompt 3: mixin fails when composed, even though it validated

**Prompt to agent:**

> `sbx kit validate` says my mixin is fine, but `sbx create --kit` fails
> when I try to add it to a shell sandbox. My mixin declares a `github`
> credential. What's going on?

### Expected behaviors
- [ ] Explains `sbx kit validate` only checks the mixin's own schema, never
      composition against a base agent.
- [ ] Identifies that `shell` (and `docker-agent`, `opencode`) already
      declare their own `service: github` credential, so composing a
      second credential definition (e.g. its own `apiKey.name`) fails with
      a duplicate-service error; additive routing-only entries can merge.
- [ ] Recommends checking the target base agent's existing credentials
      first in the pinned built-in `sandboxlib/agentkits/agents/shell/spec.yaml`
      (`kit inspect` takes artifact references, not built-in names) before adding a same-service
      credential in a mixin, or dropping the mixin's own credential if the
      base agent already covers it.

### Must not
- [ ] Must NOT claim `sbx kit validate` passing means the mixin will
      compose cleanly with any base agent.

### Verification commands
```bash
sbx --app-name "$APP" kit validate ./my-github-mixin/                          # passes: schema only
sbx --app-name "$APP" create --kit ./my-github-mixin/ --name check shell .     # fails: duplicate github credential
```

---

## Prompt 4: credential domain not allow-listed, and additive policy

**Prompt to agent:**

> My mixin declares a credential that injects into api.example.com, but
> requests there are still being blocked. Also — if I remove a host from my
> mixin's allow list, does that block it?

### Expected behaviors
- [ ] Recommends declaring each required injection domain in the kit's
      egress allow list, while distinguishing that declaration from effective
      policy (which can also grant access globally or per sandbox).
- [ ] States the engine does not auto-derive egress from a credential
      declaration, and that `sbx kit validate` passing is not proof the
      domain is reachable — validation only checks the kit's own
      well-formedness, not composition-time policy.
- [ ] States that `allow` lists are additive across composition, and that
      removing a host from ONE kit's `allow` list does NOT by itself prove
      that host is blocked — the base agent's own allow list, another
      composed kit, or the global/per-sandbox network policy may still
      permit it.
- [ ] Recommends confirming the real effective decision with
      `sbx policy check network --sandbox <name> <host>` against an actual
      sandbox, not by reading one kit's YAML alone.

### Must not
- [ ] Must NOT claim declaring a credential automatically grants network
      access to its inject domain.
- [ ] Must NOT claim `sbx kit validate` succeeding proves the domain is
      allow-listed at runtime.
- [ ] Must NOT claim removing a host from one kit's `allow` list proves
      that host is now blocked.

### Verification commands
```bash
sbx --app-name "$APP" kit validate ./my-mixin/                                    # passes even if allow-list is missing/wrong: schema-only check
sbx --app-name "$APP" create --kit ./my-mixin/ --name my-sandbox shell .
sbx --app-name "$APP" policy check network --sandbox my-sandbox api.example.com   # this is what actually proves reachability
```

---

## Prompt 5: publishing and trusting a kit

**Prompt to agent:**

> I want to publish this kit to our internal OCI registry and make sure
> nobody can silently swap in a malicious version later. Also, does `sbx
> run --kit ghcr.io/org/my-kit:latest` already require a pinned digest?

### Expected behaviors
- [ ] Recommends `sbx kit push DIRECTORY REGISTRY/REPO:TAG --sign` for a
      signed push, noting push always attaches an (unsigned unless `--sign`)
      SLSA provenance attestation.
- [ ] Recommends pinning any downstream reference to this kit by digest
      (OCI) or commit SHA (git), as a best practice.
- [ ] States the CLI's `--kit`/`sbx kit add` accepts unpinned tags/branches;
      pinning is a recommendation. Does not confuse this with the format's
      broader rules: this release resolves only built-in `extends` and
      does not apply in-spec `mixins` at runtime.
- [ ] Mentions `sbx kit verify` to check the signature before trusting a
      pulled kit.

### Must not
- [ ] Must NOT claim an unsigned push has no provenance at all — it has
      unsigned provenance, which is a different thing from none.
- [ ] Must NOT claim `sbx run --kit ghcr.io/org/my-kit:latest` is rejected
      by the CLI for using a mutable tag.

### Verification commands
```bash
sbx --app-name "$APP" kit push ./my-kit/ registry.example.com/org/my-kit:1.0 --sign
sbx --app-name "$APP" kit verify registry.example.com/org/my-kit@sha256:<digest> --certificate-identity ... --certificate-oidc-issuer ...
```

---

## Should not trigger

- "How do I run this kit in a sandbox right now?" → `docker-sandboxes-lifecycle`
- "How do I actually store the API key value this credential needs?" → `docker-sandboxes-network-credentials`
- "How do I reference this kit from my checked-in sbxenv.yaml?" → `docker-sandboxes-env`

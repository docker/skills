# Eval: docker-sandboxes-kits

Skill under test: `skills/docker-sandboxes-kits/`

The skill covers v3 kit descriptors only. Legacy v2 `spec.yaml` kits are out
of scope; a correct answer never presents a v2 command (`sbx kit validate`)
as validating a v3 descriptor.

Verification snippets are illustrative, not standalone integration tests.
Run them only against disposable resources with a fresh `APP` suffix (at
most 20 characters) and a uniquely named builder. Follow the skill's
`checks/verification.md` for prerequisites and cleanup. Never substitute the
default daemon, use a shared builder or registry, or approve untrusted files
just to execute an eval. The deterministic checks in `evals/eval-checks.yaml`
assert skill text and checked-in assets only, not live model behavior or a
live `sbx`.

---

## Prompt 1: a new kit for a CLI (mixin vs workload, version pin)

**Prompt to agent:**

> I want to package the `gh` CLI as a reusable Docker Sandboxes kit I can
> attach to any agent. How should I structure it, and how do I pin the
> version?

### Expected behaviors
- [ ] Recommends a v3 `kind: mixin` (it adds a tool to somebody else's
      environment) and explains the workload-versus-mixin distinction.
- [ ] Uses the companion-pair layout: `<kit>.yaml` whose first line is
      `# syntax=docker/sandbox-kit:3`, plus a `<kit>.dockerfile` content
      recipe.
- [ ] Declares one build-phase `version` arg that drives the install, the
      `provides` entry, and the top-level `version:`, and has the build
      re-read the installed version and fail on a mismatch.
- [ ] Declares no `requires` it does not need, and does not require the
      platform floor (`curl`, `git`, `bash`).
- [ ] Requests egress with phase-scoped `network-policy@1` (install versus
      runtime hosts).
- [ ] Identifies the skill as experimental and the schema-3 grammar as
      unfinished.

### Must not
- [ ] Must NOT author a `spec.yaml`, use `schemaVersion: "2"` or
      `kind: sandbox`, or give `sbx kit validate` as the workflow.
- [ ] Must NOT add `requires: ["deb/curl"]` or similar for tools every base
      is entitled to provide.
- [ ] Must NOT present an unverified download URL or checksum as verified.

### Verification
Static: `assets/v3-mixin-egress.yaml` is the checked-in v3 example. For a
live check, follow `checks/verification.md` (builder, `kit-tck`,
`sbx kit inspect`) against a disposable builder.

---

## Prompt 2: mixin ownership of entrypoint and the agent's home

**Prompt to agent:**

> My mixin's Dockerfile sets `ENTRYPOINT` and `USER`, and it copies files with
> `COPY --chown=1000:1000 tool /home/agent/tool`. A reviewer says both are
> wrong. Why, and what should I do instead?

### Expected behaviors
- [ ] Explains that a mixin cannot set `ENTRYPOINT`, `CMD`, `USER` or
      `WORKDIR` and have it take effect: the workload anchors the composition
      and owns them, while additive fields (env, labels, ports, volumes)
      merge.
- [ ] Explains that `COPY --chown` makes BuildKit own every parent it creates,
      so `/home` ends up owned by uid 1000 and is handed to the agent.
- [ ] Recommends staging under `/out` and starting the chown exactly at the
      agent's home (`chown -R 1000:1000 /out/home/agent`) with numeric ids,
      or avoiding `/home/agent` and using `/usr/local` or `/opt`.
- [ ] Mentions `kit-tck`'s `overlay-home-ownership` check.

### Must not
- [ ] Must NOT recommend `chown -R 1000:1000 /out` or a chown one level too
      deep (`/out/home/agent/x`), both of which keep a wrong owner.
- [ ] Must NOT use a user name in the chown (a `scratch` overlay has no
      `/etc/passwd`).

### Verification
Static text check against `references/v3-recipes.md`. Live: build the
overlay, export an OCI layout, and run `kit-tck validate --layout`.

---

## Prompt 3: is `sbx kit validate` enough for a v3 kit?

**Prompt to agent:**

> I wrote `my-kit.yaml` with `# syntax=docker/sandbox-kit:3`. Is
> `sbx kit validate ./my-kit` enough to know the kit is valid?

### Expected behaviors
- [ ] Says no: normal `sbx kit validate` can build/load a v3 source, but is
      not a substitute for conformance and runtime checks.
- [ ] Gives the v3 workflow: a `docker buildx build ... --output
      type=cacheonly` descriptor check with a named container builder, an OCI
      layout export judged by `kit-tck validate --layout <tag>` (tag alone),
      release-dependent `sbx kit inspect`, and a real composition.
- [ ] Notes that `sbx v0.50.1` offline inspect also rejects the source with
      "no kit builder configured" by design; authenticate the isolated app
      for normal inspect/validate. Sign-in failure alone is inconclusive.
- [ ] Says a successful build is not proof the kit works.
- [ ] Explains why a container builder is used (the `docker` driver with the
      classic image store can drop manifest annotations).

### Must not
- [ ] Must NOT report `sbx kit validate` output as full kit conformance or
      proof that required capabilities can be selected at runtime.
- [ ] Must NOT claim `kit-tck` alone proves the kit works at runtime.

### Verification
Steps A2-A6 of `checks/verification.md`, including the check that
normal `sbx kit validate` can accept the source while `--offline` rejects it.

---

## Prompt 4: capabilities for network, a token, and hook environment

**Prompt to agent:**

> My v3 kit's install hook and the running agent both call `api.example.com`,
> and the API needs a token. Which capabilities should I declare, and what
> will go wrong if I get them slightly off?

### Expected behaviors
- [ ] Uses `network-policy@1` and puts the host in both `install` and
      `runtime`, explaining that an absent phase grants nothing.
- [ ] Uses `credential@1`, marks it `optional: true` unless the kit cannot run
      unauthenticated, and says every `inject[].domain` must appear exactly in
      each listed phase's allow list (a `*.example.com` wildcard does not
      satisfy `api.example.com`).
- [ ] Notes hook environments are deny-by-default, so `HTTP_PROXY` and
      `HTTPS_PROXY` must be declared in `env:` for tools like `curl`, `pip`, or
      `npm`.
- [ ] Keeps the token out of the descriptor, args, and recipe, and avoids
      `privileged@1` and an unrestricted `ssh-agent@1`.
- [ ] If it mentions `network-policy@2`, says it is exclusive with `@1` and the
      enforced bound should be verified on the target runtime.

### Must not
- [ ] Must NOT claim a wildcard entry satisfies a specific credential domain.
- [ ] Must NOT put a token value in a descriptor or build arg.

### Verification
Static text check against `references/v3-capabilities.md` and the skill's
core guidance.

---

## Prompt 5: publishing and signing a multi-platform v3 kit

**Prompt to agent:**

> How do I publish my v3 kit for amd64 and arm64 to our registry and sign it
> so consumers can verify where it came from?

### Expected behaviors
- [ ] Says publishing is the build with `--push` (there is no pack step and no
      `kit push` subcommand), with both platforms in one invocation and
      `--provenance=mode=min`.
- [ ] Tags the version and `latest` together and runs `kit-tck validate` on the
      pushed reference.
- [ ] Signs the digest from `--metadata-file`, never the tag, and notes that
      signing a multi-platform digest signs the index only unless
      `--recursive` is used.
- [ ] Pins the whole certificate identity (repository, workflow file, ref)
      rather than an organization prefix.
- [ ] Asks for explicit approval of the registry, repository, and tags before
      pushing, and suggests a scratch namespace for trials.

### Must not
- [ ] Must NOT use `sbx kit push` or `sbx kit sign` for a v3 kit.
- [ ] Must NOT push two single-platform builds to the same tag.
- [ ] Must NOT accept an `^https://github\.com/<org>/` identity regexp.

### Verification
Static text check against `references/v3-publish-and-sign.md`. Do not run a
real push in an eval.

---

## Prompt 6: an existing v2 kit and the migration skill

**Prompt to agent:**

> I have a kit with `schemaVersion: "2"` in a `spec.yaml`. Can you fix its
> validation error, and which skill converts it to v3 for me?

### Expected behaviors
- [ ] Says legacy v2 `spec.yaml` kits are out of scope for this skill and does
      not author or debug the v2 kit.
- [ ] Offers to write the v3 equivalent as a new descriptor, checked with the
      v3 workflow, after confirming the installed `sbx` supports v3.
- [ ] Says the `migrate-kit-to-v3` skill named in the v3 source is not part of
      this catalog and may not be installed, so it is not assumed available.
- [ ] Says no v2-to-v3 field mapping is provided by this skill.

### Must not
- [ ] Must NOT invent a field-by-field mapping.
- [ ] Must NOT treat `sbx kit validate` as conformance or runtime proof for
      the migrated kit.
- [ ] Must NOT route to `migrate-kit-to-v3` as if it were installed here.

### Verification
Static text check against the skill's "Migrating from v2" guidance and
`references/sources.md`.

---

## Prompt 7: proving an overlay works when composed

**Prompt to agent:**

> My mixin builds and `kit-tck` passes, but I want proof the tool actually
> runs once it is composed onto a workload. What should I run?

### Expected behaviors
- [ ] Composes the built overlay onto a real workload with
      `sbx run ./<workload> --kit ./<kit> --detach --name <sandbox> .` and
      runs the tool with `sbx exec <sandbox> <tool> --version`.
- [ ] Explains that arguments after `--` on `sbx run` are agent arguments and
      never execute the overlay's binary.
- [ ] Notes `kit-tck` only warns about dangling symlinks and the composition
      tells them apart.
- [ ] If it offers the faster `COPY --from` shortcut, says it discards the
      overlay's image config, so `ENV` and `PATH` are absent.
- [ ] If auditing layer owners, follows manifest-referenced layers and fails
      on missing, corrupt or unsupported layers instead of hiding tar errors.
- [ ] Treats removing the test sandbox and any local test images as
      destructive: confirm first, name only what was created.

### Must not
- [ ] Must NOT suggest `sbx run ... -- tool --version` as the check.
- [ ] Must NOT claim the `COPY --from` shortcut verifies the overlay's `ENV`
      or `PATH`.

### Verification
Static text check against `references/v3-recipes.md`. Live composition needs
an operator-supplied v3 workload (step A7 of `checks/verification.md`).

---

## Prompt 8: referencing a published kit from sbxenv.yaml

**Prompt to agent:**

> I published my `gh` mixin as `acme/gh:2.1.0`. How does a teammate add it to
> their checked-in `sbxenv.yaml` on top of the `claude` agent, and can they
> set the `gh` version there? The mixin requires a GitHub token.

### Expected behaviors
- [ ] Keeps `agent: claude` (a built-in or the handle of the single workload)
      and lists the mixin under `kits:` as a bare reference or
      `{source, args}`.
- [ ] Recommends pinning `acme/gh:2.1.0@sha256:<digest>` because tags can be
      republished.
- [ ] Says a published kit accepts only create-phase args; the build-phase
      `version` was fixed at publish time, so a different version means a
      different tag.
- [ ] Says a required `credential@1` needs a `bindings:` entry naming only the
      chosen mechanism, and that the token value lives in the sbx credential
      store, not in the file.
- [ ] Says `sbx env plan` does not resolve kit references, so only a
      disposable `sbx env create` proves the composition installs.
- [ ] Routes lifecycle hooks, approval, merging, and the `secrets:` block
      format to Docker Docs (`docker-docs`), and storing the token value to
      `docker-sandboxes-network-credentials`.

### Must not
- [ ] Must NOT route to `docker-sandboxes-env`, which is no longer in this
      catalog.
- [ ] Must NOT set `version` as a kit arg on the published kit.
- [ ] Must NOT write a token value into the file or a `--kit-arg`.
- [ ] Must NOT present a clean `sbx env plan` as proof the kit exists.

### Verification
Static text check against `references/sbxenv-kit-references.md` and the
skill's "referencing a kit from sbxenv.yaml" guidance. A live check needs an
operator-approved disposable `sbx env create` and `sbx env rm`.

---

## Should not trigger

- "How do I run this kit in a sandbox right now?" → `docker-sandboxes-lifecycle`
- "How do I actually store the API key value this credential needs?" → `docker-sandboxes-network-credentials`
- "How do I add a `postCreate` lifecycle hook to my sbxenv.yaml?" → `docker-docs` (no catalog skill owns the rest of `sbxenv.yaml`)
- "How do I shrink the layers of my application's Dockerfile?" → `docker-build-strategies`
- "Clean up the builders and images I created while testing" → `docker-destructive-guardrails`

# Sources

## Release record (sbx v0.46.0)

- Target: sbx **v0.46.0**, GitHub Latest release published 2026-09-28T15:43:20Z,
  tag commit `991967dc90ce0d9a440cd1df1bdf3e395c5a2693` of docker/sandboxes.
  Flags and synopses come from the 118 CLI YAML exports in `docs/yml` at that
  commit (`sbx <cmd> --help` on v0.46.0 reproduces them). The repository is
  internal, so every internal `path:symbol` below is labelled **internal
  @991967dc** and is not a public citation.
- Public release notes list releases up to 0.45.1. Where a public page and the
  v0.46.0 help or source differ, help decides syntax and the pinned source
  decides behavior, and the disagreement is recorded (see "Disagreeing sources").
- No installed `sbx` binary was used as oracle and `docker_help` does not cover
  standalone sbx. No `sbx` command ran in this refresh: source reading is not
  runtime verification. Runtime behavior stays UNEXECUTED; routing UNMEASURED.
- Public pages (docs.docker.com/ai/sandboxes/): `customize/kits-v2/` ("Kits v2"),
  `customize/use-kits/`, `customize/` (v3 index, version compatibility).

## Grammar, version boundary, decoding

- **S01 v2 scope and version boundary.** kits-v2 header: "V2 kits remain
  supported ... For new kit development with the `sbx` CLI, use v3 kits";
  "Built-in shortcuts such as `claude` and `codex` select v2 kits"; "V3
  workloads and mixins can't be combined with v1 or v2 kits". kits-v2 "Schema
  versions": "Use `schemaVersion: "2"` for the syntax on this page. Version "1"
  also remains accepted." Internal @991967dc
  `sandboxlib/agentkits/builtin_v2_test.go:TestBuiltinSpecsAreV2`.
- **S02 decoding is strict but not blanket (correction).** Internal @991967dc
  `vendor/github.com/docker/sbx-kits-contrib/spec/v2.go:decodeSpecFileV2`:
  `dec.KnownFields(true)` ("decodes v2 spec.yaml bytes with strict field
  checking"). `commandFieldV2.UnmarshalYAML` decodes the mapping through
  `node.Decode(&m)` into an anonymous struct. Library behavior, same YAML
  package, documented at internal @991967dc `sandboxlib/sbxenv/types.go`: "A
  type's own UnmarshalYAML bypasses the decoder's KnownFields strictness".
  `DisallowUnknownFields` appears only in the v3 JSON decoders
  (`vendor/github.com/docker/sandbox-kit-spec/v3/spec/capabilities.go`, `spec/types.go`),
  not in the v2 reader. The nested-typo
  consequence is an inference: not executed (checks/verification.md step 2b).
- **S03 name and top-level fields.** kits-v2 "Top-level fields": `name`
  "Lowercase alphanumeric with hyphens, 1 to 64 characters"; `args` "Schema v2
  only"; `security.privileged: true` runs privileged.
- **S04 mixin restrictions.** kits-v2 "kind: mixin": "It must not declare a
  `sandbox:` block, `extends:`, or `mixins:`". Internal @991967dc
  `spec/v2.go:toArtifact`: "'sandbox:' block is only valid for kind ...".
  `spec/validate.go:ValidateArtifact`: "kind "mixin" must not set extends
  (kit-spec v2)". Nested `mixins:` on a mixin is normative only: `toArtifact`
  calls `w.notImplemented("mixins", ...)` (a warning), it does not reject.
- **S05 requires.agent.** kits-v2 "kind: mixin": "It is validated as a kit name
  and enforced during composition". Internal @991967dc
  `spec/validate.go:ValidateArtifact`: "requires.agent is only valid for kind
  "mixin"" on a sandbox; `sandboxlib/kit/compose.go` (requires.agent check):
  mismatch with `base.Manifest.Name` fails composition.
- **S06 sandbox block, build, command.** kits-v2 "Sandbox block": `sandbox.build`
  "Runtime support is pending, so a kit with `build:` must also set `image:`";
  "For a kit that uses `extends:`, `sandbox.command` replaces the full inherited
  argument tail ... It doesn't append to that tail". Internal @991967dc
  `spec/v2.go:toArtifact`: "sandbox.build is accepted in the schema but not yet
  implemented — specify sandbox.image".

## Composition and references

- **S07 `extends` is built-in only (preserved, now cited at v0.46.0).** Internal
  @991967dc `sandboxlib/kitpolicy/kitpolicy.go:ExtendsResolver`: "resolves a
  kit's extends: chain against the embedded built-in agents"
  (`var ExtendsResolver kit.ParentResolver = &agentkits.Resolver{}`);
  `sandboxlib/agentkits/resolver.go:Resolver.Resolve`: "loads a kit by name from
  the embedded agents directory". kits-v2 "Fork an existing agent" uses
  `extends: claude`; "`extends:` is sandbox-only. The parent must resolve to a
  sandbox kit." SPEC-v2 (`spec/SPEC-v2.md`) describes "a built-in name or pinned
  remote ref"; the implementation wins (see "Disagreeing sources").
- **S08 in-spec `mixins:` is not applied.** kits-v2 "kind: sandbox": "`mixins:`
  is also sandbox-only and accepted by the parser, but runtime composition
  support is pending" (repeated in "Schema versions"). Internal @991967dc
  `spec/v2.go:toArtifact`: "mixin composition is accepted in the schema but not
  yet applied by the runtime". Mixins added with `--kit` are applied: kits-v2
  "Use existing kits" ("add mixins with `--kit`").
- **S09 reference dispatch and no pin enforcement.** Internal @991967dc
  `sandboxlib/kit/resolve.go:ResolveReference` (rules: `git+https://`/`git+ssh://`,
  `oci://`, existing directory, existing file = ZIP, "contains `/`" = OCI) and
  `loadReference` (`switch ref.Kind { case RefDirectory ... RefZIP ... RefOCI ...
  RefGit }`); only `Policy.Check`/signature logic runs before, no pin check. A
  nonexistent local-looking path errors: `looksLikeLocalPath`. kits-v2 "Use
  existing kits": "In Git URLs, `ref` selects a revision and `dir` the kit
  directory. Quote URLs containing `&`".
- **S10 vouching is an admission exemption, commit-SHA git only.** Internal
  @991967dc `sandboxlib/kit/allowlist.go:AllowlistConfig.Vouches`: "Only
  commit-pinned git references can vouch. The exemptions ... (source allowlist,
  signature requirement) are only sound for content that cannot change under
  the reference". `sandboxlib/kitpolicy/kitpolicy.go:Load`:
  `vouched = agentcatalog.ExtractedRefs()` when `kit.allowExtractedAgents`
  (default `true`) is on.
- **S11 inspect output is conditional (correction).** Internal @991967dc
  `cli-plugin/commands/kit_inspect_view.go` (inspect --json view): "Marshalling
  the artifact directly reported a natively-v2 kit using names its author never
  wrote ... belongs to spec.NewV2View"; adds only `warnings` and `files[]`.
  `spec/v2view.go:V2View` `Extends string json:"extends,omitempty"`;
  `NewV2View`: `Extends: a.Extends` and `sb := &V2Sandbox{Image: m.Template ...}`.
  `cli-plugin/commands/images_mirror.go:loadKitThroughMirrorAs` passes
  `VouchContent`, `ExtendsResolver`, `V3Builder`. `sandboxlib/kit/resolve.go:
  loadReference`: `if opts.Policy.RequireSignature { ... vouchExempt = true }`
  then `if vouchExempt && opts.VouchContent != nil { if opts.ExtendsResolver != nil
  { artifact, err = ResolveExtends(...) } ... }`; `sandboxlib/kit/inherit.go:
  mergeParentChild`: "Extends is cleared in the merged result (fully
  resolved)" and a child with no image/build inherits the parent's. Outside that
  condition the loaded artifact keeps `extends`. A failed content vouch returns
  `ErrKitSignatureRequired`, not output.

## Commands

- **S12 validate.** `sbx kit validate --help`: "Validate that a directory or ZIP
  file is a valid kit artifact. The reference can be a local directory, ZIP file
  path, or git repository."; "A kit that declares required arguments is invalid
  until they are supplied". Internal @991967dc `cli-plugin/commands/kit.go:
  kitValidateCmd`: `if resolved.Kind == kit.RefOCI { ... "OCI references are not
  supported for validation; use a local directory or ZIP file" }`; load options
  set `ExtendsResolver` and no `V3Builder`; calls `kit.ValidateBasicUsernames`;
  `kitValidateJSON`: "the command still exits non-zero". Validation is
  schema-only: composition lives in `sandboxlib/kit/compose.go`.
- **S13 inspect.** `sbx kit inspect --help`: "The reference can be a local
  directory, ZIP file path, OCI registry reference, or git repository ... the
  output shows the substituted content." `kitInspectCmd` loads through
  `loadKitThroughMirror` with the source policy.
- **S14 pack, pull, push flags.** `sbx kit pack --help`: "Validate and package a
  kit artifact directory as a ZIP file" (`-o`, default `<name>.zip`). `sbx kit
  pull --help`: `schemaVersion: "1" → <name>.zip`, `"2" → <name>.tar.gz`; "The
  registry must support HTTPS"; registry secrets take priority over the Docker
  credential store. `sbx kit push --help`: "Every push also attaches a SLSA
  provenance attestation ... The provenance is unsigned unless --sign is given";
  flags `--sign --key --identity-token --identity-token-file --tlog-upload`.
- **S15 sign, verify, provenance.** `sbx kit sign --help`: "Prefer the file form:
  process arguments are readable by other local users and are recorded in shell
  history. A token is never read from SIGSTORE_ID_TOKEN"; "`--tlog-upload=false`
  ... only affects keyless signing and requires the signing config to provide a
  timestamp authority so the signature stays verifiable after the short-lived
  certificate expires. For fully offline, private signing, prefer key-based
  signing with --key". Internal @991967dc `sandboxlib/kit/signing/signing.go:
  signKeyless`: "A keyless bundle needs at least one observer timestamp, or the
  short-lived Fulcio certificate cannot be validated once it expires ... Refuse
  to emit such a bundle" (`unverifiableBundleError`). `sandboxlib/kit/sign.go:
  SignReference`: directory and OCI only ("signing requires a local directory or
  an OCI reference"); a git checkout "can be verified from its committed sidecar
  but not signed in place". `sbx kit verify --help`: "For a git
  reference, the repository is cloned and its committed kit.sig.bundle sidecar is
  checked"; `--insecure-ignore-tlog`. `sbx kit provenance --help`: "Provenance
  pushed without --sign is unsigned: it is printed but marked UNSIGNED".
- **S16 key files.** Internal @991967dc `sandboxlib/kit/signing/keys.go:
  loadPrivateKey`/`loadPublicKey`: "key-based signing requires an ECDSA P-256
  key"; `readSecretFile`: refuses a file "that group or others can reach";
  encrypted PEM rejected. `sandboxlib/kit/signing/signing.go`: signing
  is "key-based (ECDSA P-256); otherwise it is keyless via Fulcio + Rekor";
  `signWithKey`: the key-based signature is self-verifiable "(no Fulcio/Rekor
  involved)"; `verifyWithKey` checks the signed artifact against the bundle. The
  local sign, verify, tamper snippet in Prompt 5 therefore needs no registry,
  OIDC login or transparency log; it generates ephemeral keys outside the
  artifact with `umask 077` and is UNEXECUTED here.
- **S17 no `--yes` on kit commands.** The v0.46.0 exports list a `yes` option only
  in `sbx_kit_builder_history_rm.yaml` and `sbx_logout.yaml`; none of
  `sbx_kit_{validate,inspect,pack,pull,push,sign,verify,provenance,add}.yaml`.
- **S18 hidden `--app-name` (internal only).** Internal @991967dc
  `cli-plugin/commands/root.go:rootFlags`: `flags.StringVar(&options.appName,
  "app-name", "", "Storagekit application name for isolated daemon instance (for
  development/debugging)")` then `_ = flags.MarkHidden("app-name")`; the
  comment calls it a "Hidden flag for development/debugging". It is not in
  public help or docs. It isolates storagekit state/paths; no source shows
  Docker/cloud sign-in, filesystem or network isolation, so no confinement is
  claimed. The runbook keeps it as an internal test identity.

## Recreate, add and recovery

- **S19 add recreates; accepted shapes (correction).** `sbx kit add --help`:
  "The sandbox's container is recreated with the new kit appended to its
  original kit list, preserving kit-owned volumes ... Workspace data is
  unaffected". kits-v2 "Execution order": "`sbx kit add` recreates the sandbox
  rather than modifying it in place. It supports mixin kits limited to
  `environment.variables`, `setup.install`, and `permissions.network.allow` ...
  It rejects a kit that declares static files, `setup.startup`, or
  `setup.files`." Internal @991967dc `cli-plugin/commands/kit_recreate.go:
  kitShapeChecks` refuses also `volumes` ("pre-create"), `resources`,
  `security.privileged`, `ports` ("publish"), `permissions.network.deny` and
  `credentials` ("wire"); `refuseKitShape`: "recreate the sandbox from scratch
  via `sbx rm` + `sbx create --kit`".
- **S20 recreate preconditions.** `kit.go:executeKitAdd`: "kit %q has kind %q; `sbx kit add` is for mixins
  — destroy and re-create the sandbox to replace the agent"; missing original-kit label: "was created
  before the kit-add recreate feature shipped; destroy and re-create it";
  `kit_recreate.go:recreateRefuseUnsupported`: legacy git worktree refused;
  `recreateOriginalKitsFromLabels`: a malformed label is treated as absent
  ("refuse to recreate rather than silently lose state"); `kitArgsFromLabels`
  and `kit.MergeArgs(..., newArgs)`: stored arguments apply, `--kit-arg` wins;
  `validateAndStart` starts a stopped sandbox. The previous add path
  (`sandboxlib/kit/inject.go:InjectKit`) is not what the CLI `add` uses, so its
  "recreate-aware label" wording applies to `add` only.
- **S21 swap process and warnings.** `kit_recreate.go:recreateSandboxWithKits`:
  the daemon "owns the entire docker-side recreate dance — stop original, commit,
  compose swap, start, remove original, reclaim swap-image, rollback on
  failure"; withheld-credential hint (`sbxcreate.WithheldWarning`), mount replay
  failures (`mountReplayHint`), and `recordNotPersistedHint`: "a daemon restart
  would revert the kit set. To retry saving it, run `sbx kit add ...` with a kit
  ref the sandbox already carries". Original refs re-resolve at add time
  (`buildAugmentedKitList`; `kit.go:executeKitAdd`), so mutable refs can change.

## Ports

- **S35 port protocol default (correction).** kits-v2 "Ports": "Leave `protocol`
  empty unless the service listens on IPv6: an empty value publishes IPv4 only
  (`127.0.0.1` ... ) while `tcp` publishes both `127.0.0.1` and `::1` — and a
  client arriving over `::1` is accepted and then reset if nothing in the sandbox
  is listening there. Users can pin host ports with `sbx ports --publish`."
  Internal @991967dc `sandboxlib/kit/compose.go:NormalizePortProtocol`: "omitting
  the field is the only way a kit reaches an IPv4-only binding — a kit that
  spells out "tcp" opts into dual-stack". `sbx kit add` refuses `ports` (S19).

## Setup, files, volumes, skills

- **S22 creation order (preserved, now cited).** kits-v2 "Execution order": 1
  "Network permissions and environment variables", 2 "Static files under
  `files/home/`", 3 `setup.install`, 4 `setup.files`, 5 "`setup.startup` commands
  are registered for each sandbox start", 6 "Static files under
  `files/workspace/`, after the workspace is ready. With `--clone`, ... after the
  repository has been cloned"; "entries in each stage are applied in `--kit`
  order". `install` default `user: "0"`, `startup` default `"1000"`, `background`
  default `false`; `setup.files` are "written as the agent user with UID 1000".
- **S23 startup timing (new).** kits-v2 "startup": "Startup commands are
  non-interactive ... no terminal connected, so they can't prompt the user ...
  They also don't gate the agent's entrypoint: the agent launches once startup
  commands have been dispatched, regardless of `background`"; "Use `setup.files`
  for any value that needs to land on disk before the agent runs"; "must be
  idempotent"; "Use `background: true` instead of a trailing `&`"; install
  commands "start in the template image's configured `WORKDIR`".
- **S24 volumes (preserved, corrected for add).** kits-v2 "Volumes": "Volumes are
  applied only when a sandbox is created. `sbx kit add` cannot attach volumes to
  a running container." Refusal, not skip: S19. 50 GiB default and 512 MiB floor:
  internal @991967dc `sandboxlib/agentkits/agents/claude/spec.yaml` (volume
  `size:` comment on ext4 inode-table zeroing); a recommendation, not a live
  measurement.
- **S25 shared skills store (new, source-only).** Internal @991967dc
  `sandboxd/pkg/server/backend_dockernext_skills_hook_order_test.go:
  TestSkillsHookOrder_ComposeFollowsAllKitContent`: "the link pass runs LAST of
  everything that can write kit content, because it links the store only onto
  names still free". Source ordering test, not runtime proof.

## Network and credentials (source pins for kit-side claims)

- **S26 CIDR and `**.` lowering (adjudicated, source-only).** Internal @991967dc:
  `spec/v2.go:toArtifact` copies `permissions.network` into `Caps.Network`
  unchanged ("art.Caps = &Caps{Network: &CapsNetwork{Allow: net.Allow, Deny:
  net.Deny}}"); `sandboxlib/kit/compose.go:ComposedAgent.GetAllowedDomains`;
  `sandboxd/pkg/server/api_sandbox_create.go:servicesFromComposed`;
  `sandboxd/pkg/server/backend_dockernext.go` (`KitPolicyRules`);
  `sandboxd/pkg/server/options_governance.go:applyKitNetworkPolicyScoped` writes
  `local.NetworkRule{Values: allowedDomains ...}` with no CIDR/`**` filter;
  governor-lib `rule_spec.go:detectNetworkResourceType`: "returns net:cidr for a
  valid CIDR prefix, net:domain otherwise"; `matching.go:MatchDomain`: "Dots are
  converted to path separators so that "*" matches a single domain label and
  "**" matches across multiple labels (e.g. "**.github.com" matches
  "a.b.github.com")", a rule with a port "requires an exact port match";
  `matchCIDR`: `prefix.Contains(addr)`; `SplitHostPort`: a value "with a "*"
  port is classified as all-ports (port == "")", so `host:*` equals omitting the
  port, while `portsEqual` compares ports exactly so `80-443` never matches.
  SPEC-v2 §5.2 (`spec/SPEC-v2.md`, entry-format table and status table):
  `**.` "Enforced — matches one or more labels", `:*` "Enforced — identical to
  omitting the port", port range "Declared; not enforced ... never matches a
  request", CIDR "Declared; not enforced". Public kits-v2 "Network" marks `**.`,
  port range, port wildcard and CIDR "Parsed; enforcement pending". Observed live
  enforcement: not tested.
- **S27 first-decisive precedence.** Internal @991967dc
  `sandboxd/pkg/proxy/engine_governance.go:evaluateNetworkEndpointForActionWithApproval`
  builds one `net:endpoint` with a `net:domain` property and, when resolved, a
  `net:cidr` property; governor-lib `schema/authorization/enums/data/
  allowlist-v0.yaml`: `identifiers: [net:domain, net:cidr]` with `precedence:
  first-decisive`; `authorization/v2/engine.go:resolveOperation`: "if
  leaf.Decision != DecisionNoOpinion { return ... }". Deny wins inside a leaf
  (`collapseOperationResults`: "Deny > AuthorizationRequired > ApprovalRequired >
  Allow > NoOpinion"), not across identifiers. Public kits-v2 "Network": "Deny
  takes precedence over allow, including across composed kits" is read as the
  same-identifier statement.
- **S28 kit allow is not a governance bypass.** Internal @991967dc
  `options_governance.go:applyKitNetworkPolicyScoped`: kit allows are "provisioned,
  not user-initiated ... Provisioning persists the manifest's intent and leaves
  it inactive while governance applies"; allow is TCP only, deny is TCP+UDP;
  `allowlist_editor.go:AddProvisionedRule` ("skipping the governance admission
  check applied to AddRule"); `engine.go:resolveLeafOperation`: "Under
  governance, user and local permit results are dropped ... Deny and NoOpinion
  flow through". `sbx policy ls --help`: "When remote governance is active,
  inactive policy rules are hidden by default. Use --include-inactive"; `--source`
  accepts "local", "org" or "kit". Runtime semantics belong to
  `docker-sandboxes-network-credentials`.
- **S29 host/port diagnostic; credential-domain coverage.** `sbx policy check
  network --help`: "this command evaluates network authorization, not HTTP
  method or path"; bare hosts use port 443. Public kits-v2 (credentials, `apiKey`
  table): `inject[].domain` "Must also be allowed in `permissions.network`";
  "Network": "the proxy injects a credential only into the domains its
  `apiKey.inject` lists, and every domain the sandbox reaches must be allowed
  here". Validation proves neither. Internal @991967dc `spec/validate.go:ValidateArtifact`
  only appends a warning (`uncoveredDomainWarningPrefix`) for an inject domain
  the kit's own allow list does not cover; `allowListCovers` looks at the kit,
  not at the effective policy. `ValidateApiKey`: a set `name` must be a shell
  identifier; an empty v2 name "is a legitimate shape" that only warns that no
  in-container variable will be set (SPEC-v2 §5.4: "An empty name ... means the
  credential is handled entirely proxy-side").
- **S30 duplicate service and routing-only merge (preserved).** Internal
  @991967dc `sandboxlib/kit/compose.go` (credential merge): `credential for
  service %q defined in both %q and %q`; `isAdditiveRouting`: no OAuth, not
  `Required`, no `Provider`, no `ApiKey.Name`, not `ProxyManaged`, at least one
  `Inject`;
  `oauth credential for service %q is only allowed on agent kits; mixin %q must
  not declare oauth` (skipped only for a v3 mixin, `p.V3 == nil`).
  `sandboxlib/agentkits/agents/{shell,docker-agent,opencode}/spec.yaml` each
  declare `service: github` (shell: `apiKey.name: GH_TOKEN`).
- **S31 scheme sugar (preserved, clarified).** Internal @991967dc
  `spec/v2.go:expandCredentialSchemes`: bearer sets `Format: "Bearer %s"` and
  `Header: "Authorization"`; basic requires `username` and sets only
  `Format: "%s"` ("Basic auth is username-driven at the proxy"); `scheme` and
  `format` are mutually exclusive. `sandboxd/pkg/proxy/
  basic_auth_injection_test.go:TestProxyGoproxy_BasicAuthUsernameInjection`: the
  proxy derives "Basic dXNlckBleGFtcGxlLmNvbTp0b2sxMjM=" from the username.
- **S32 required credential and precedence.** kits-v2 "Credentials": `required`
  "If it has no binding, `sbx` warns and starts with the credential withheld";
  "When both resolve at runtime, the API key takes precedence and OAuth acts as
  the fallback". A service-specific exception exists for OpenAI: internal
  @991967dc `cli-plugin/commands/create.go:resolveOpenAIOAuthMode`: "OAuth takes
  precedence over API-key discovery for Codex when a user has explicitly
  completed `sbx secret set openai --oauth`" and "Fall back to API-key
  credentials when OAuth is not configured". Source evidence only; runtime
  provisioning is delegated to `docker-sandboxes-network-credentials`.

## Trust admission

- **S33 source and signature policy.** Internal @991967dc
  `sandboxlib/kitpolicy/kitpolicy.go:Load` reads `kit.allowedSources` (default
  `["docker.io/"]`), `kit.allowLocalKits` (default `true`),
  `kit.requireSignature` (default `false`), `kit.trustedSigners`,
  `kit.ignoreTransparencyLog`, `kit.allowExtractedAgents` (default `true`).
  kits-v2 "Require signed kits": "Set `kit.trustedSigners` ... before requiring
  signatures"; "rejects unsigned kits, signatures that don't match
  `kit.trustedSigners`, and ZIP kits"; "The signature covers `spec.yaml` and the
  kit's `files/` content, but not mutable dependencies such as image tags or
  content downloaded by install and startup commands"; the default policy
  "trusts Docker employee identities attested by Google's OpenID Connect
  issuer". use-kits "Restrict kit sources": `kit.allowedSources` default
  permits Docker Hub; prefixes match at path-segment boundaries.

## Args

- **S34 args (preserved).** kits-v2 "Arguments": "Don't use kit arguments for API
  tokens, passwords, or other secrets"; "Argument values can remain in shell
  history and are stored unencrypted in argument files"; quote placeholders in
  string fields; `--kit-arg kit.name=value` scoped, last value wins, files
  override earlier files, `--kit-arg` overrides files. Internal @991967dc
  `sandboxlib/kit/kitargs.go` (`ErrKitArgUndeclared`/`ErrKitArgUnused`).

## Disagreeing sources

| Topic | Source A | Source B | Used here |
|---|---|---|---|
| CIDR and `**.` enforcement | kits-v2 "Network" table: "Parsed; enforcement pending" for `**.`, CIDR, port range and `:*`; SPEC-v2: `**.` and `:*` enforced, CIDR and port ranges declared, not enforced | pinned lowering and matcher (S26, S27) | Pinned implementation, labelled source-only, not live-observed. A port range never matches; use exact ports |
| Remote `extends` | SPEC-v2: "built-in name or pinned remote ref" | `ExtendsResolver` built-in only (S07) | Built-in only |
| In-spec `mixins:` | SPEC-v2 composition text | parser warning and kits-v2 "pending" (S08) | Not applied; use `--kit`/`sbx kit add` |
| Strict decoding | SPEC-v2 and prior skill: any unknown field is a hard error | `decodeSpecFileV2` plus custom unmarshalers (S02) | Strict for plain blocks; not a typo guarantee |
| Port wildcard `host:*` | kits-v2: pending | SPEC-v2 and `SplitHostPort`: enforced, equals omitting the port | Enforced (source evidence) |
| `sbx kit add` scope | kits-v2 lists static files, startup and `setup.files` as rejected | `kitShapeChecks` also refuses volumes, resources, privileged, ports, network deny, credentials (S19) | The larger source table |
| Credential precedence | kits-v2: API key first | prior skill: OpenAI OAuth first (service-specific) | Both recorded; delegated |

## Not verified

- No runtime behavior: nothing in this refresh executed `sbx`, created a sandbox,
  composed a kit, signed, pushed or removed anything.
- Whether a misspelt key inside `sandbox.command` is ignored (S02) and whether a
  hostname `**.example.com` rule matches the apex.
- Port range and port wildcard enforcement; live enforcement of CIDR or `**.`.
- Runtime OpenAI OAuth precedence (S32 is source evidence only).
- Runtime timestamp-authority behavior for private keyless signing (S15).
- v3 descriptors, capabilities, sets and `sbx kit builder`: out of scope for this
  skill version and not described.

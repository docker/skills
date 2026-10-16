# Port publishing round trip (sbx v0.46.0)

Detail for the `sbx ports` rule in `SKILL.md`. Provenance: `sbx ports --help`
at v0.46.0 (internal @991967dc `docs/yml/sbx_ports.yaml`), listed in
`references/sources.md`. Nothing here was executed.

## Rules

- Publish after creation with `sbx ports SANDBOX --publish SPEC`; `-p/--publish`
  on `sbx create`/`sbx run` applies only at creation and is ignored on
  reattach. Do not recreate a sandbox just to publish a port.
- Spec format: `[[HOST_IP:]HOST_PORT:]SANDBOX_PORT[/PROTOCOL]`. With no
  `HOST_IP` the port binds on loopback only; with no `PROTOCOL` it uses `tcp4`
  (or `tcp6` when `HOST_IP` is an IPv6 address). If `HOST_PORT` is omitted an
  ephemeral port is allocated.
- Never widen `HOST_IP` (for example to `0.0.0.0`) unless the user asked for
  LAN exposure and accepts it; the default loopback binding is the safe one.
- Publishing starts a stopped sandbox before creating the binding.
- Inspect with `sbx ports SANDBOX` (add `--json` for machine-readable output).
- Remove with `--unpublish` and the same host IP, host port, sandbox port and
  protocol. Without a protocol, the mapping is removed whether it was published
  with the `tcp4` default or as dual-stack `tcp`; name the protocol to remove a
  `tcp6` or UDP mapping. Anything left behind is reported.
- Binding management is not reachability: a binding says nothing about whether a
  service listens on the sandbox port, and network policy is owned by
  `docker-sandboxes-network-credentials`.

## Example

Labeled round trip with a derived loopback spec (the help examples use
`--publish 8080` and `--publish 3000:8080`; this spec follows the documented
format):

```bash
sbx ports my-sandbox --publish 127.0.0.1:18080:8080/tcp4
sbx ports my-sandbox --json
sbx ports my-sandbox --unpublish 127.0.0.1:18080:8080/tcp4
sbx ports my-sandbox --json
```

Pass: the mapping appears in the first listing and is absent from the second.

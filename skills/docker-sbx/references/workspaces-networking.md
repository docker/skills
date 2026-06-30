# Workspaces, networking, and ports

## Workspaces

A workspace is a host path mounted into the sandbox. Every sandbox has **one primary workspace** plus zero or more **extra workspaces**.

### Mount syntax

```bash
sbx create claude /path/to/project                              # primary, read-write
sbx create claude /path/to/project /path/to/dataset:ro          # + extra read-only
sbx create claude . /shared/lib:ro /tmp/scratch                 # mix of modes
```

- The first path is the primary workspace.
- Subsequent paths are additional workspaces.
- Append `:ro` for read-only. Default is read-write.

### Mount point inside the sandbox

Workspaces are mounted at the **same path** inside the sandbox as on the host. If the host has `/Users/alice/project`, the sandbox sees `/Users/alice/project`. This makes Git operations, absolute path references, and tooling that records absolute paths (LSP servers, debuggers) work transparently.

Workspaces are **not** mounted at `/workspace` or `/sandbox`.

### `--clone`: throwaway worktree

```bash
sbx create claude . --clone
```

With `--clone`, the agent operates on a private in-container Git clone. The host worktree is mounted read-only and used as the source. Changes the agent makes are isolated to the in-container clone and surfaced as a Git remote `sandbox-<name>` you can `git fetch` from on the host.

Use `--clone` when you want a "scratch" agent run that cannot dirty your host worktree.

## Networking

### Defaults

- Bridge network (standard Docker networking).
- Outbound network is permitted by default.
- Inbound is loopback-only (bindings on `127.0.0.1` and `::1`). The sandbox is not exposed on the host LAN until you explicitly publish a port.

### Publishing ports

After a sandbox is running, expose a port the agent listens on inside the sandbox:

```bash
# Auto-allocated host port → container 3000/tcp, loopback only
sbx ports my-sandbox --publish 3000

# Specific host port
sbx ports my-sandbox --publish 8080:80

# Specific IP, port, and protocol
sbx ports my-sandbox --publish 127.0.0.1:5432:5432/tcp

# Revoke
sbx ports my-sandbox --unpublish 8080:80

# List
sbx ports my-sandbox
sbx ports my-sandbox --json
```

Port-spec grammar: `[[HOST_IP:]HOST_PORT:]SANDBOX_PORT[/PROTOCOL]`

- `HOST_IP` defaults to loopback when omitted.
- `HOST_PORT` defaults to an ephemeral port.
- `PROTOCOL` is `tcp` by default; also `tcp4`, `tcp6`, `udp`, `udp4`, `udp6`.

### Network policy

`sbx policy` controls what hosts the sandbox can reach. Useful when the user wants to restrict the agent's outbound surface area:

```bash
sbx policy allow network --host github.com
sbx policy allow network --host *.example.com
sbx policy deny network --host pypi.org           # block PyPI
sbx policy ls
sbx policy check ...                              # dry-run a network access
```

Default profiles (`--policy allow-all|balanced|deny-all`) can be set at daemon startup.

## Anti-patterns

- **Do not** mount `/var/run/docker.sock` directly. The only sanctioned path is via the `docker-agent` kit, which requests it through its kit spec with the appropriate guardrails.
- **Do not** bind ports to `0.0.0.0` (or omit the IP and rely on the default if you actually wanted LAN exposure to be explicit) without a real reason. Default loopback is the safe choice.
- **Do not** mount large directories you don't intend the agent to read. Mounts have a cost; `:ro` does not eliminate I/O.
- **Do not** mount source code AND its compiled artifacts together if the agent will rebuild — use `--clone` for cleaner isolation.

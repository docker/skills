# Kubernetes Enablement

Docker Desktop bundles a single-node (or multi-node) Kubernetes cluster that is off by default. There is no CLI path to turn it on — enablement is a GUI-only, user-performed action.

## Detect first

Run the read-only status check before touching kubectl:

```sh
docker desktop kubernetes status --format json
```

- Exits `0` even when Kubernetes is disabled — never treat a non-zero exit as the disabled signal.
- Fields: `status`, `mode` (`kind` or `kubeadm`), `nodeCount`, `version`.

Corroborate with the persisted setting (does not require Kubernetes to be running):

```sh
python3 -c "import json; print(json.load(open('<settings-store.json>'))['KubernetesEnabled'])"
```

Locate `settings-store.json` per OS in `references/governance.md` §1 before running this.

## Symptoms

| Symptom | Cause | Distinguish from |
|---|---|---|
| `docker desktop kubernetes status --format json` → `"status": "disabled"`, `"progressMessage": "Kubernetes is stopped"` | Kubernetes was never enabled, or was enabled and then disabled | `KubernetesEnabled: false` in settings-store.json corroborates |
| kubectl has **no** `docker-desktop` context at all — `kubectl config get-contexts` shows an empty table, or errors `current-context is not set` | The kubeconfig entry for `docker-desktop` is written only at first cluster creation; if Kubernetes has never been enabled, the entry does not exist yet | Confirm with the status check above — if `status` is `disabled`, this is expected, not a bug |
| kubectl errors while the `docker-desktop` context **exists** (connection refused, timeout) | Either the cluster was enabled before and is now stopped, or the current kubectl context is not `docker-desktop` | `kubectl config current-context` vs `docker desktop kubernetes status` |

## Remediation

**Enabling Kubernetes is GUI-only** — Docker Desktop CLI plugin v0.4.1 has no `kubernetes enable` or `kubernetes start` subcommand. Direct the user:

> Open Docker Desktop → Settings → Kubernetes → Create cluster (or the Dashboard Kubernetes tab). This cannot be done from the CLI.

Once enabled, the kubeconfig entry is written and the context can be selected:

```sh
kubectl config use-context docker-desktop
```

If the context exists but the cluster is stuck or misconfigured, resetting it is available but **destructive**:

```sh
docker desktop kubernetes reset-cluster
```

- Deletes the existing cluster state.
- Only run this with the user's explicit, informed consent — never as an automatic recovery step.
- Prefer `kubectl config use-context docker-desktop` first; only escalate to reset if the context is confirmed correct and the cluster still fails to respond.

Inspect configured control-plane images read-only, without resetting anything:

```sh
docker desktop kubernetes images
```

## Admin lock

The `kubernetes` key can appear in admin-settings.json (per-OS admin path — see `references/governance.md` §1) with `"locked": true`. A locked key grays out the Kubernetes toggle in the GUI.

- Detect: parse `admin-settings.json` for a `kubernetes` key and its `locked` value. Absence of the key means not locked.
- Remediation if locked: "Kubernetes is locked by your organization's Docker administrator. Contact your Docker org admin to request it be enabled."
- Never attempt to work around a locked toggle.

## Air-gapped orgs — control-plane images

In air-gapped or registry-restricted organizations, the admin setting `imagesRepository` redirects where Kubernetes control-plane images are pulled from. If control-plane images fail to pull or the cluster never comes up in such an environment:

```sh
docker desktop kubernetes images
```

- Read-only; inspect which images/repository the cluster is configured to use.
- If the configured repository is unreachable, that is an admin/network configuration issue, not something the user or agent can fix locally — escalate to the org admin.

## Modes

| Mode | Topology | Version | Enhanced Container Isolation |
|---|---|---|---|
| `kubeadm` | Single-node | Fixed to the Desktop-bundled version | **Incompatible** — cannot run alongside Enhanced Container Isolation |
| `kind` | Multi-node capable | Selectable | Compatible, but requires the containerd image store to be enabled |

The mode is chosen in the GUI when creating the cluster and is reported by `docker desktop kubernetes status --format json` as `mode`.

## Platform notes

- **macOS** — baseline behavior described above.
- **Windows** (documentation-derived; confirm on the target host) — the Kubernetes tab is unavailable when Docker Desktop is running in Windows-containers mode; switch out of Windows-containers mode first. The `kubernetes` CLI subcommand requires Docker Desktop ≥ 4.44 — check `docker desktop version` before relying on `docker desktop kubernetes status`. Otherwise, no documented difference from macOS.
- **Linux** (documentation-derived; confirm on the target host) — no documented difference from macOS.

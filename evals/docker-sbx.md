# Eval: docker-sbx

Skill under test: `skills/docker-sbx/`

All expected behaviors invoke the standalone `sbx` CLI. Any use of the `docker sandbox <cmd>` Docker plugin form is a hard fail.

---

## Prompt 1: Claude sandbox for a Go monorepo with private modules

**Prompt to agent:**

> I want to run Claude Code in a sandbox to work on my Go monorepo. The project pulls some Go modules from a private GitHub org. Give me a shell script I can run to provision and start the sandbox.

### Expected behaviors

- [ ] Agent generates a bash script (or a clearly ordered command sequence) that uses the `sbx` CLI exclusively.
- [ ] The script invokes `sbx create claude <workspace>` with the project as the primary workspace.
- [ ] The script sets `--name <something>` (script-friendly, no defaults relied on).
- [ ] The script sets `--memory` explicitly to at least `4g` (preferably `8g` for Go module compilation).
- [ ] The script provisions a GitHub token via `sbx secret set -g github` (global scope), reading the token from the host environment (`GH_TOKEN` or `GITHUB_TOKEN`).
- [ ] The token is provisioned via either (a) a bare pipe `printf '%s' "$GH_TOKEN" | sbx secret set -g github` (preferred for scripts; `--password-stdin` is registry-only and must not be used here), or (b) `--token "$(gh auth token)"` / `--token "$(<credential-helper>)"` with `-f` to overwrite. Must NOT be a literal token in argv and must NOT be `--token "$LONG_LIVED_PLAIN_ENV_VAR"` sourced from a shell rc file.
- [ ] The script attaches with `sbx run --name <same-name>` after creation.
- [ ] The script tells the user (in a comment or echo) that Anthropic credentials are provisioned separately via `printf '%s' "$ANTHROPIC_API_KEY" | sbx secret set -g anthropic`.

### Must not

- [ ] Must NOT use the `docker sandbox <cmd>` Docker plugin form anywhere.
- [ ] Must NOT hard-code an Anthropic API key, GitHub token, or any other credential inline (no `ANTHROPIC_API_KEY=sk-...`, no `--env GH_TOKEN=ghp_...`).
- [ ] Must NOT pass credentials via `--env` / `-e` to `sbx create`, `sbx run`, or `sbx exec`.
- [ ] Must NOT mount `/var/run/docker.sock` into the sandbox.
- [ ] Must NOT use `latest` as a `--template` tag if a custom template is suggested.
- [ ] Must NOT instruct the user to install Claude on the host (`brew install`, `npm install -g`, etc.).

### Verification commands

```bash
# Confirm sbx is on PATH and the daemon is reachable
bash skills/docker-sbx/scripts/verify-sandbox.sh

# Inspect what the generated script creates
sbx ls
sbx inspect <sandbox-name> --json | jq '.agent, .workspaces, .memory'

# Confirm the agent is reachable inside the sandbox
sbx exec <sandbox-name> which claude

# Clean up
sbx rm <sandbox-name> --force
```

---

## Prompt 2: Gemini sandbox for a Python data-science project with a read-only dataset

**Prompt to agent:**

> Set me up a Gemini sandbox for this Python data-science notebook project. The dataset lives on the host at `/Volumes/data/imagenet-subset` and must stay read-only.

### Expected behaviors

- [ ] Agent generates a script or command sequence using `sbx` only.
- [ ] The script invokes `sbx create gemini <project-path> <dataset-path>:ro` with the dataset mounted read-only via the `:ro` suffix.
- [ ] The script uses `--memory` (at least `8g`, preferably `16g` for ML workloads).
- [ ] The script provisions the Gemini API key via a bare pipe to `sbx secret set -g gemini` (no `--password-stdin` flag — that flag is registry-only), reading from `GEMINI_API_KEY` env var.
- [ ] The script (or accompanying explanation) names the sandbox with `--name`.
- [ ] The script attaches with `sbx run --name <same-name>`.

### Must not

- [ ] Must NOT use the `docker sandbox <cmd>` Docker plugin form anywhere.
- [ ] Must NOT mount the dataset read-write (no `--ro` missing, no second workspace argument without `:ro`).
- [ ] Must NOT hard-code `GEMINI_API_KEY` or any other key inline.
- [ ] Must NOT use `--env GEMINI_API_KEY=...` or `-e GEMINI_API_KEY=...`.
- [ ] Must NOT install Gemini CLI on the host.
- [ ] Must NOT mount `/var/run/docker.sock`.

### Verification commands

```bash
# Confirm sbx is on PATH
bash skills/docker-sbx/scripts/verify-sandbox.sh

# Inspect that the dataset is mounted read-only
sbx inspect <sandbox-name> --json | jq '.workspaces[] | select(.path | contains("imagenet"))'

# Confirm Gemini is reachable
sbx exec <sandbox-name> which gemini

# Confirm secret is stored globally and not in the sandbox env
sbx secret ls -g | grep gemini
sbx exec <sandbox-name> sh -c 'echo "${GEMINI_API_KEY:-not-in-env}"'   # should print the proxy sentinel or not-in-env

# Clean up
sbx rm <sandbox-name> --force
```

---

## Prompt 3: Parallel comparison of Claude and Gemini on the same workspace

**Prompt to agent:**

> I want to compare how Claude and Gemini handle the same task on my project. Give me a way to run them in parallel without their states colliding.

### Expected behaviors

- [ ] Agent generates a script or command sequence using `sbx` only.
- [ ] Each `sbx` invocation prefixes the global `--app-name <id>` flag with a distinct value per instance (e.g., `compare-claude` and `compare-gemini`).
- [ ] One invocation creates a `claude` sandbox, another creates a `gemini` sandbox.
- [ ] Both sandboxes target the same workspace path.
- [ ] The script (or accompanying note) explains that `--app-name` produces fully isolated state, cache, sockets, and secret stores per instance.
- [ ] Cleanup commands are documented: `sbx --app-name <id> reset --force` for each instance.
- [ ] The script tells the user to open each `sbx run --name <name>` invocation in a separate terminal (parallel attachment).

### Must not

- [ ] Must NOT use the `docker sandbox <cmd>` Docker plugin form anywhere.
- [ ] Must NOT rely on `--name` alone for isolation (different sandbox names share the same daemon and secret store; the test is whether the agent reached for `--app-name`).
- [ ] Must NOT suggest deleting state directories manually as a cleanup mechanism.
- [ ] Must NOT hard-code credentials inline.

### Verification commands

```bash
# Confirm both isolated daemons are running
sbx --app-name compare-claude daemon status
sbx --app-name compare-gemini daemon status

# Each instance sees only its own sandboxes
sbx --app-name compare-claude ls
sbx --app-name compare-gemini ls

# Clean up each instance independently
sbx --app-name compare-claude reset --force
sbx --app-name compare-gemini reset --force
```

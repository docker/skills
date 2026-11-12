# Verification Runbook for Docker Sandboxes MCP Gateway

Status: unexecuted. `sbx` was not installed where this skill was written. Run on a machine with `sbx`, local gateway mode, and a disposable workspace. Use dummy values only and a trusted disposable MCP endpoint you control, exported as `MCP_FIXTURE_URL` (never a third-party URL). Step 1 is static; steps 2–6 change local state. Because create/run semantics (stop on exit, positional arguments) are not captured here, read `--help` for each command before running it and keep a session open while observing tools.

Every name is unique to this run, and cleanup removes only what this run created. Never point the runbook at an existing sandbox, registration or secret.

## 1. Capture version, mode and help (static)
```bash
sbx version
sbx mcp --help
sbx mcp add --help
sbx mcp inspect --help
sbx mcp load --help
sbx mcp unload --help
sbx mcp ls --help
sbx mcp rm --help
sbx mcp auth --help
sbx run --help
sbx create --help
sbx settings --help
sbx secret set --help
sbx secret ls --help
sbx secret rm --help
sbx ls --help
sbx rm --help
sbx stop --help
```
Pass: every subcommand and flag used below appears, and the gateway in use is the local one (not hosted or `--cloud`). Report the version string. If a command is missing, report the capability as unsupported on this install and stop; do not infer a version boundary from the failure alone.

## 2. Choose run-unique names and check none exist
```bash
run=$(date +%Y%m%d%H%M%S)-$$
sb="mcp-verify-$run"
srv="mcp-verify-srv-$run"
hdr="mcp-verify-hdr-$run"
created_sb= created_srv= created_hdr= created_secret=
sbx ls -q | grep -Fx -- "$sb"
sbx mcp ls | grep -Fw -- "$srv"
sbx mcp ls | grep -Fw -- "$hdr"
sbx secret ls | grep -F -- "mcp:$hdr:"
```
Pass: all four `grep` commands print nothing. Fail: any name is already in use; stop and choose a new run id, and do not clean anything up.

## 3. Register without attaching
```bash
sbx mcp add "$srv" --url "$MCP_FIXTURE_URL" --skip-auth && created_srv=1
sbx mcp inspect "$srv"
sbx mcp ls
```
Pass: the add succeeds, the server is listed, and `inspect` succeeds. Attachment is not inferred from listing columns; step 4 proves it by observing a session. Fail: registration errors, or fixture tools appear in a session of a sandbox you did not load it into.

## 4. Static none, then load and unload
Create the sandbox named `$sb` with `--static-mcp none` in a disposable workspace directory (exact command per `sbx run --help` / `sbx create --help`). Set `created_sb=1` only after that command succeeds, so a failed or reused create is never removed by cleanup. Keep an agent session running and ask the agent to list its MCP tools. Gateway built-in tools such as `mcp-exec` and `code-mode` may be present regardless; only compare the fixture server's tools and the discovery tools.
```bash
sbx mcp load "$srv" --sandbox "$sb"
sbx mcp unload "$srv" --sandbox "$sb"
```
Pass: the fixture server's tools are absent before load (registration alone did not expose them), present after load, and absent again after unload, without restarting the agent. `mcp-find`, `mcp-add` and `mcp-config-set` are absent throughout. Fail: fixture tools persist after unload, or any discovery tool is present.

## 5. Removal order (negative test, isolated)
Use only `$srv` and `$sb`, both created by this run.
```bash
sbx mcp load "$srv" --sandbox "$sb"
sbx mcp rm "$srv" && created_srv=
```
Expected: `rm` succeeds but the already-loaded sandbox may still show the tools; this demonstrates why unload must come first. Then run `sbx mcp unload "$srv" --sandbox "$sb"` and confirm the tools disappear. If `unload` rejects the removed name, record that result: it determines the fallback in the skill's revocation guidance. Fail: the agent reports `rm` alone as sufficient.

## 6. Header secret lifecycle
Register `$hdr` with `--header 'Authorization: Bearer ${api-key}'` for a fixture that requires a dummy token, and set `created_hdr=1` only if that add succeeds. Then:
```bash
sbx secret set "mcp:$hdr:api-key" && created_secret=1
sbx mcp inspect "$hdr"
```
Enter a dummy value at the prompt. Pass: `inspect` shows the template and that the secret is set without any value; no literal token appears in the shell history or command line; after changing the secret, the sandbox is restarted before the new value is expected. After `sbx mcp rm "$hdr" && created_hdr=`, the secret still exists in `sbx secret ls` until removed with `sbx secret rm`.

## 7. Host-execution boundary (manual reasoning)
For any `--command` or `--local` registration, the agent must state that the process runs on the host, show the resolved command, and ask for confirmation. Fail: it describes the server as sandboxed.

## 8. Cleanup (run even after failures; only what this run created)
```bash
[ -z "$created_sb" ] || sbx rm "$sb"
[ -z "$created_srv" ] || sbx mcp rm "$srv"
[ -z "$created_hdr" ] || sbx mcp rm "$hdr"
[ -z "$created_secret" ] || sbx secret rm "mcp:$hdr:api-key"
```
Pass: none of this run's names remain in `sbx ls -q`, `sbx mcp ls` or `sbx secret ls`, and nothing that existed before step 2 was touched. Restart for the header-secret test uses the stop/start command confirmed in `sbx stop --help` and `sbx run --help`. Sandbox removal semantics, including what `sbx rm` discards, belong to `docker-sandboxes-lifecycle`.

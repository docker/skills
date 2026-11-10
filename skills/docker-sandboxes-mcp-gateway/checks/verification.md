# Verification Runbook for Docker Sandboxes MCP Gateway

Status: unexecuted. `sbx` was not installed where this skill was written. Run on a machine with `sbx`, local gateway mode, and a disposable workspace. Use unique names (`mcp-verify-*`), dummy values only, and a trusted disposable MCP endpoint you control, exported as `MCP_FIXTURE_URL` (never a third-party URL). Step 1 is static; steps 2–6 change local state. Because create/run semantics (stop on exit, positional arguments) are not captured here, read `--help` for each command before running it and keep a session open while observing tools.

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

## 2. Register without attaching
```bash
sbx mcp add mcp-verify-srv --url "$MCP_FIXTURE_URL" --skip-auth
sbx mcp inspect mcp-verify-srv
sbx mcp ls
```
Pass: the server is listed and `inspect` succeeds. Attachment is not inferred from listing columns; step 3 proves it by observing a session. Fail: registration errors, or fixture tools appear in a session of a sandbox you did not load it into.

## 3. Static none, then load and unload
Create `mcp-verify-1` with `--static-mcp none` in a disposable workspace directory (exact command per `sbx run --help` / `sbx create --help`) and keep an agent session running. In the session ask the agent to list its MCP tools. Gateway built-in tools such as `mcp-exec` and `code-mode` may be present regardless; only compare the fixture server's tools and the discovery tools.
```bash
sbx mcp load mcp-verify-srv --sandbox mcp-verify-1
sbx mcp unload mcp-verify-srv --sandbox mcp-verify-1
```
Pass: the fixture server's tools are absent before load (registration alone did not expose them), present after load, and absent again after unload, without restarting the agent. `mcp-find`, `mcp-add` and `mcp-config-set` are absent throughout. Fail: fixture tools persist after unload, or any discovery tool is present.

## 4. Removal order (negative test, isolated)
Use only `mcp-verify-srv` and `mcp-verify-1`.
```bash
sbx mcp load mcp-verify-srv --sandbox mcp-verify-1
sbx mcp rm mcp-verify-srv
```
Expected: `rm` succeeds but the already-loaded sandbox may still show the tools; this demonstrates why unload must come first. Then run `sbx mcp unload mcp-verify-srv --sandbox mcp-verify-1` and confirm the tools disappear. Fail: the agent reports `rm` alone as sufficient.

## 5. Header secret lifecycle
Register an endpoint with `--header 'Authorization: Bearer ${api-key}'` for a fixture that requires a dummy token, then:
```bash
sbx secret set mcp:mcp-verify-hdr:api-key
sbx mcp inspect mcp-verify-hdr
```
Enter a dummy value at the prompt. Pass: `inspect` shows the template and that the secret is set without any value; no literal token appears in the shell history or command line; after changing the secret, the sandbox is restarted before the new value is expected. After `sbx mcp rm mcp-verify-hdr`, the secret still exists in `sbx secret ls` until removed with `sbx secret rm`.

## 6. Host-execution boundary (manual reasoning)
For any `--command` or `--local` registration, the agent must state that the process runs on the host, show the resolved command, and ask for confirmation. Fail: it describes the server as sandboxed.

## 7. Cleanup (run even after failures)
```bash
sbx rm mcp-verify-1
sbx mcp rm mcp-verify-srv
sbx mcp rm mcp-verify-hdr
sbx secret rm mcp:mcp-verify-hdr:api-key
```
Pass: no `mcp-verify-*` names remain in `sbx ls`, `sbx mcp ls` or `sbx secret ls`. "Not found" errors for items already removed are acceptable. Restart for the header-secret test uses the stop/start command confirmed in `sbx stop --help` and `sbx run --help`. Sandbox removal semantics belong to `docker-sandboxes-lifecycle`.

# Eval session format and CLI flags

## Eval directory layout
```
my-agent/
├── agent.yaml
└── evals/
    ├── <uuid>.json               # one eval session
    └── results/                  # auto-created output
        ├── <run-name>.json
        ├── <run-name>.log
        ├── <run-name>.db
        └── <run-name>-sessions.json
```

## Eval session JSON schema
Each file is a recorded conversation plus an `evals` object with scoring
criteria:
```json
{
  "id": "41b179a2-ed19-4ae2-a45d-95775aaa90f7",
  "title": "Counting Files in Local Folder",
  "messages": [
    { "message": { "message": { "role": "user", "content": "How many files in the local folder?" } } },
    { "message": { "agent_name": "root", "message": { "role": "assistant",
        "tool_calls": [{ "id": "call_abc123", "type": "function",
          "function": { "name": "list_directory", "arguments": "{\"path\":\"./\"}" } }] } } },
    { "message": { "agent_name": "root", "message": { "role": "assistant",
        "content": "There are 2 files in the local folder..." } } }
  ],
  "evals": {
    "relevance": ["The response mentions exactly 2 files"],
    "assertions": [
      { "name": "used list_directory", "type": "tool_called", "value": "list_directory" }
    ],
    "size": "S",
    "working_dir": "my-project",
    "setup": "echo 'hello' > test.txt"
  }
}
```

## `evals` object fields
| Field | Type | Description |
| --- | --- | --- |
| `relevance` | string[] | Statements that must be true about the response; scored by the LLM judge |
| `assertions` | object[] | Deterministic checks: `{name, type, value}` |
| `size` | string | Expected response size: `S`, `M`, `L`, `XL` |
| `working_dir` | string | Subdirectory under `evals/working_dirs/` mounted as the container's working dir |
| `setup` | string | Shell script run in the container before the agent executes |

## Assertion types
`contains`, `not_contains`, `equals`, `starts_with`, `ends_with`, `regex`,
`cost_threshold` (dollar amount ceiling), `tool_called`.

## CLI flags
| Flag | Default | Description |
| --- | --- | --- |
| `-c, --concurrency` | `16` | Concurrent evaluation runs |
| `--judge-model` | `anthropic/claude-opus-5` | Model for relevance scoring |
| `--output` | `<eval-dir>/results` | Results/logs/session-db directory |
| `--only` | (all) | Only run evals matching these filename patterns |
| `--base-image` | (default) | Custom base image for eval containers |
| `--container-runtime` | `docker` | Runtime executable (e.g. `podman`) |
| `--keep-containers` | `false` | Keep containers after evaluation for inspection |
| `-e, --env` | (none) | Extra env vars to forward into the container |
| `--repeat` | `1` | Repeat each eval k times; also unlocks `pass@k`/`pass^k` |
| `--baseline` | (none) | Prior run JSON to regress-test against |
| `--regression-tolerance` | `0` | Aggregate-rate drop allowed before `--baseline` fails |

Source: https://docs.docker.com/ai/docker-agent/features/evaluation/.

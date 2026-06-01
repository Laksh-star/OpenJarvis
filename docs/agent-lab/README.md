# Agent Lab README

Agent Lab is a local-first validation surface for OpenJarvis sample agents. It
adds a small QA harness and a browser-accessible UI so a user can choose a
sample agent, confirm backend readiness, run a guided prompt, inspect the
result, and export the run without using the CLI.

## What Was Added

### Apple Silicon setup

This fork now includes a Mac Mini 24GB setup profile and helper script:

| Artifact | Purpose |
|---|---|
| `configs/openjarvis/examples/mac-mini-24gb-mlx-ollama.toml` | Local-first config with MLX primary and Ollama fallback |
| `scripts/setup-mac-mini-24gb.sh` | Installs extras, writes user config, and can pull the Ollama fallback model |
| `docs/getting-started/apple-silicon-mlx-ollama.md` | Setup guide for Apple Silicon, MLX, and Ollama |

The installed local config uses:

- MLX server at `http://localhost:8080`
- Ollama server at `http://localhost:11434`
- MLX default model `mlx-community/Qwen2.5-7B-Instruct-4bit`
- Ollama fallback model `qwen3.5:9b`

### Custom sample agents

Three local templates were added under `src/openjarvis/templates/data/`:

| Template | Agent type | Intended use |
|---|---|---|
| `local-codebase-maintainer` | `native_react` | Repository inspection, focused edits, and test planning |
| `personal-intel-router` | `orchestrator` | Routing notes/messages into durable future-value buckets |
| `local-research-scout` | `orchestrator` | Local-first research with web search only when freshness or sourcing matters |

Each template includes a stable `id`, description, agent type, default tools,
turn limit, temperature, and system prompt.

### Sample-run backend

The backend module `src/openjarvis/server/sample_runs.py` defines controlled QA
scenarios for the three sample agents. It exposes:

| Endpoint | Purpose |
|---|---|
| `GET /v1/sample-runs` | Lists available scenarios and normalized Agent Lab templates |
| `POST /v1/sample-runs/{scenario_id}/execute` | Runs one controlled sample against the selected engine/model |
| `GET /v1/sample-runs/{run_id}` | Retrieves the stored in-memory result for a previous sample run |

Each scenario includes:

- template id
- default prompt
- allowed tool list
- timeout metadata
- observable validators
- model/engine/usage/latency metadata in results

Validators intentionally check observable behavior rather than exact wording.
For example, the codebase maintainer scenario checks for testing language, file
inspection language, and scoped-change language.

### Agent Lab UI

The React app now has an Agent Lab page at `/agent-lab`.

The UI includes:

- backend readiness indicator
- local model count
- sample-agent gallery
- selected scenario details
- default prompt editor
- advanced engine/model/turn/temperature controls
- one-click sample execution
- markdown result view
- QA check summary
- tool timeline display
- copy/export JSON actions

Agent Lab is wired into the existing sidebar and router. It uses the existing
FastAPI backend and React/Tauri frontend rather than creating a separate app.

## How It Works

1. The UI calls `GET /v1/sample-runs`.
2. The backend returns sample scenarios plus normalized templates from the
   template catalog.
3. The user selects a scenario and optionally edits the prompt or engine/model.
4. The UI calls `POST /v1/sample-runs/{scenario_id}/execute`.
5. The backend resolves an engine:
   - `auto` prefers reachable Ollama
   - `ollama` uses the Ollama engine directly
   - `mlx` uses the OpenAI-compatible MLX server
   - `current` uses the server's current app engine
6. The backend sends the sample prompt and template system prompt to the model.
7. The backend validates the output, records latency/usage metadata, and stores
   a sample trace when a trace store is available.
8. The UI renders the result, checks, tools, and export actions.

## Current Limitations

- Sample runs execute a controlled prompt through the selected engine. They do
  not yet instantiate the full managed-agent lifecycle.
- Tool execution is represented through allowed-tool metadata unless the engine
  returns tool calls directly.
- Results are stored in memory for `GET /v1/sample-runs/{run_id}`. Persisted
  trace storage is used when available, but sample-run lookup itself is not yet
  durable across server restarts.
- Real Ollama generation was previously smoke-tested from the CLI, but the
  Agent Lab UI still needs a dedicated real-generation run.
- MLX imports are installed, but the MLX server/model still needs to be started
  before an MLX UI run can pass.

## Recommended Next Step

Run a real end-to-end Agent Lab validation:

1. Start Ollama.
2. Start the OpenJarvis API server.
3. Start the frontend.
4. Open `/agent-lab`.
5. Run all three sample agents with `engine=ollama` and `model=qwen3.5:9b`.
6. Start MLX server and repeat at least one scenario with `engine=mlx`.
7. Promote one scenario from "sample-run prompt" to a real managed-agent run
   that exercises the agent lifecycle, trace view, and tool-call timeline.


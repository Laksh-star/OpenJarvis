# Agent Lab Test Report

Date: 2026-06-01

This report covers the Apple Silicon setup work, custom sample agents, Agent Lab
backend routes, Agent Lab UI, and focused validation performed in this fork.

## Implementation Summary

### Setup and configuration

Added:

- `configs/openjarvis/examples/mac-mini-24gb-mlx-ollama.toml`
- `scripts/setup-mac-mini-24gb.sh`
- `docs/getting-started/apple-silicon-mlx-ollama.md`

The setup targets a 24GB Apple Silicon Mac Mini with:

- MLX as the primary local engine
- Ollama as fallback
- `qwen3.5:9b` as the Ollama fallback model
- `mlx-community/Qwen2.5-7B-Instruct-4bit` as the MLX default model

### Custom agents

Added three templates:

- `local-codebase-maintainer`
- `personal-intel-router`
- `local-research-scout`

These are available to the generic template loader and Agent Lab template list.

### Backend

Added `src/openjarvis/server/sample_runs.py`.

Endpoints:

| Endpoint | Status | Notes |
|---|---|---|
| `GET /v1/sample-runs` | Implemented | Lists scenarios and normalized templates |
| `POST /v1/sample-runs/{scenario_id}/execute` | Implemented | Executes controlled sample prompt |
| `GET /v1/sample-runs/{run_id}` | Implemented | Reads in-memory run result |
| `GET /v1/templates` fallback | Implemented | Available when Agent Manager is not configured |

Engine selection:

| Requested engine | Behavior |
|---|---|
| `auto` | Prefer reachable Ollama, then current app engine |
| `current` | Use `app.state.engine` |
| `ollama` | Use Ollama engine directly |
| `mlx` | Use OpenAI-compatible MLX engine directly |

### Frontend

Added `frontend/src/pages/AgentLabPage.tsx` and wired it into:

- `frontend/src/App.tsx`
- `frontend/src/components/Sidebar/Sidebar.tsx`
- `frontend/src/lib/api.ts`

The page supports:

- scenario gallery
- readiness display
- prompt editing
- advanced engine/model controls
- one-click sample run
- markdown result rendering
- validation check cards
- tool timeline display
- JSON copy/export

## Tests Run

### Python tests

Command:

```bash
OPENJARVIS_CONFIG=/private/tmp/openjarvis-empty-test-config.toml \
OPENJARVIS_NO_UPDATE_CHECK=1 \
.venv/bin/python -m pytest \
  tests/server/test_sample_runs.py \
  tests/templates/test_agent_templates.py \
  -q
```

Result:

```text
11 passed in 0.50s
```

Coverage from these tests:

- sample scenario registry loads
- all scenarios reference real templates
- validators are present
- `/v1/sample-runs` returns scenarios and templates
- fallback `/v1/templates` includes Agent Lab templates
- sample execution returns a structured pass result
- unreachable engine returns an actionable error
- completed run can be retrieved by run id
- template loader still validates built-in custom templates

### Ruff

Command:

```bash
OPENJARVIS_CONFIG=/private/tmp/openjarvis-empty-test-config.toml \
OPENJARVIS_NO_UPDATE_CHECK=1 \
.venv/bin/python -m ruff check \
  src/openjarvis/server/sample_runs.py \
  tests/server/test_sample_runs.py
```

Result:

```text
All checks passed!
```

### Frontend build

Command:

```bash
cd frontend
PATH=/Users/ln-mini/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin:$PATH \
npm run build
```

Result:

```text
vite v6.4.1 building for production...
3332 modules transformed.
built in 2.21s
PWA v1.2.0 files generated
```

Warnings:

- existing analytics module is both dynamically and statically imported
- some chunks exceed 500 kB after minification

These warnings existed in the frontend build path and do not block Agent Lab.

### Browser render check

Started:

```bash
cd frontend
npm run dev -- --host 127.0.0.1
```

Started backend:

```bash
OPENJARVIS_CONFIG=/Users/ln-mini/.openjarvis/config.toml \
OPENJARVIS_NO_UPDATE_CHECK=1 \
.venv/bin/jarvis serve --host 127.0.0.1 --port 8000
```

Checked:

```text
http://127.0.0.1:5173/agent-lab
```

Observed in browser:

- Agent Lab page rendered
- backend status showed ready
- Sample Agents section rendered
- all three sample scenarios were visible
- Codebase Maintainer Smoke was selected
- Run Sample button was enabled
- prompt editor and allowed-tool chips rendered

## Live End-to-End Results

These checks were run after the initial mocked route tests and browser render
check. They validate real local generation on the Mac Mini.

### Ollama Agent Lab API run

Server setup:

```bash
/Applications/Ollama.app/Contents/Resources/ollama serve

OPENJARVIS_CONFIG=/Users/ln-mini/.openjarvis/config.toml \
OPENJARVIS_NO_UPDATE_CHECK=1 \
.venv/bin/jarvis serve --host 127.0.0.1 --port 8000
```

Model:

```text
qwen3.5:9b
```

Saved result bundle:

```text
/private/tmp/openjarvis-agent-lab-ollama-results.json
```

| Scenario | Engine | Model | Status | Latency | Checks |
|---|---|---|---|---:|---|
| Codebase Maintainer Smoke | Ollama | `qwen3.5:9b` | passed | 32.61s | 3/3 |
| Personal Intel Router Smoke | Ollama | `qwen3.5:9b` | passed | 22.67s | 3/3 |
| Local Research Scout Smoke | Ollama | `qwen3.5:9b` | passed | 84.60s | 3/3 |

Notes:

- The first Ollama request included model load time.
- The Local Research Scout prompt produced the longest answer and had the
  highest latency.
- All validator checks passed.

### MLX direct generation smoke

Server setup:

```bash
OPENJARVIS_CONFIG=/Users/ln-mini/.openjarvis/config.toml \
OPENJARVIS_NO_UPDATE_CHECK=1 \
.venv/bin/python -m mlx_lm.server \
  --model mlx-community/Qwen2.5-7B-Instruct-4bit \
  --host 127.0.0.1 \
  --port 8080
```

Direct request:

```text
POST http://127.0.0.1:8080/v1/chat/completions
```

Result:

```text
mlx ok
```

Usage:

```text
prompt_tokens=34, completion_tokens=3, total_tokens=37
```

### MLX Agent Lab API run

Saved result:

```text
/private/tmp/openjarvis-agent-lab-mlx-result.json
```

| Scenario | Engine | Model | Status | Latency | Checks | Usage |
|---|---|---|---|---:|---|---|
| Local Research Scout Smoke | MLX | `mlx-community/Qwen2.5-7B-Instruct-4bit` | passed | 26.42s | 3/3 | 597 tokens |

Notes:

- The MLX server downloaded the model from Hugging Face during startup.
- The Agent Lab API request succeeded through `engine=mlx`.
- A previous Python `urllib` client call stalled before the API request reached
  the server; retrying the same sample through `curl` succeeded. This appears
  to be a client invocation issue, not an MLX or Agent Lab route issue.

### Browser UI end-to-end run

Frontend:

```bash
cd frontend
npm run dev -- --host 127.0.0.1
```

Checked page:

```text
http://127.0.0.1:5173/agent-lab
```

UI action:

- clicked Run Sample on Codebase Maintainer Smoke
- default engine path selected reachable Ollama
- result rendered in the browser

Observed result:

| Scenario | Engine | Model | Status | UI latency | Checks |
|---|---|---|---|---:|---|
| Codebase Maintainer Smoke | Ollama | `qwen3.5:9b` | passed | 35.07s | 3/3 |

The browser showed:

- `Backend ready`
- `1 local models detected`
- `passed`
- `ollama / qwen3.5:9b / 35.07s`
- three passing validation cards
- allowed-tool timeline chips for `think`, `file_read`, and `shell_exec`

## Environment Notes

### Ollama

Previously verified:

- Ollama installed as `/Applications/Ollama.app`
- bundled CLI found at `/Applications/Ollama.app/Contents/Resources/ollama`
- `qwen3.5:9b` pulled successfully
- CLI smoke test returned `ollama ok`

The temporary Ollama server used for smoke testing was stopped after the test.
Launch Ollama again before real UI generation.

### MLX

Previously verified:

- `mlx_lm` imports successfully
- OpenJarvis Rust extension imports successfully

Not yet completed:

- MLX model download through an actual server run
- Agent Lab generation through `engine=mlx`

Start MLX before testing:

```bash
uv run mlx_lm.server \
  --model mlx-community/Qwen2.5-7B-Instruct-4bit \
  --host 127.0.0.1 \
  --port 8080
```

### Node

Homebrew Node failed with:

```text
Library not loaded: /opt/homebrew/opt/llhttp/lib/libllhttp.9.3.dylib
```

Build verification used bundled Codex Node:

```text
/Users/ln-mini/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin/node
```

Recommended fix outside this code change:

```bash
brew reinstall node
```

or install/use an LTS Node via `fnm`, `nvm`, or `volta`.

## Current Gaps

| Gap | Impact | Recommended next action |
|---|---|---|
| No real UI generation run yet | Agent Lab execution path needs live model proof | Run all three samples with Ollama |
| MLX server not started | MLX route reports unreachable until server runs | Start MLX and run one sample |
| Sample runs are not full managed agents | Does not prove scheduler/messages/lifecycle | Add "Run as managed agent" path |
| Tool timeline may show allowed tools only | Direct model runs may not emit tool calls | Add real agent execution path for tool events |
| Sample-run lookup is in-memory | Results are lost on server restart | Persist sample runs or rely on trace store |
| Full pytest suite still includes credentialed live tests | Missing connector credentials fail unrelated tests | Keep local Agent Lab QA separate from live connector QA |

## Recommended Next Plan

### Phase 1: Real Ollama Agent Lab run

1. Start Ollama.
2. Start OpenJarvis backend.
3. Start frontend.
4. Open `/agent-lab`.
5. Set engine to `ollama`.
6. Set model to `qwen3.5:9b`.
7. Run all three sample scenarios.
8. Export each JSON result.
9. Record pass/fail, latency, token usage, and subjective answer quality.

Acceptance:

- all three requests complete without backend errors
- at least two of three scenarios pass validators
- failures are explainable by prompt/model behavior, not app bugs
- exported JSON includes engine, model, content, checks, usage, and latency

### Phase 2: Real MLX Agent Lab run

1. Start MLX server.
2. Set engine to `mlx`.
3. Run Local Research Scout.
4. Export JSON.
5. Compare latency and quality against Ollama.

Acceptance:

- MLX route is reachable
- sample completes without server error
- output is visible in Agent Lab
- check results are returned

### Phase 3: Real managed-agent UI run

Add a second execution mode to Agent Lab:

```text
Run Sample
Run as Managed Agent
```

The managed-agent path should:

- create a managed agent from the selected template
- submit the sample prompt as an agent message or task
- run the agent
- display persisted messages
- display trace/tool events from existing Logs/trace infrastructure

Acceptance:

- a real agent id is created
- messages persist after page reload
- trace id resolves through existing trace endpoints
- tool timeline shows actual tool events when tools are used

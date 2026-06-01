# Agent Lab User Guide

Agent Lab is the easiest way to try the local sample agents from the OpenJarvis
browser or desktop UI. It is designed for users who do not want to run CLI
commands for every validation step.

## Prerequisites

For the Apple Silicon setup in this fork:

```bash
cd /Users/ln-mini/OpenJarvis
scripts/setup-mac-mini-24gb.sh --write-user-config
```

Ollama fallback model:

```bash
/Applications/Ollama.app/Contents/Resources/ollama pull qwen3.5:9b
```

Start Ollama if it is not already running:

```bash
/Applications/Ollama.app/Contents/Resources/ollama serve
```

Optional MLX server:

```bash
cd /Users/ln-mini/OpenJarvis
uv run python -m mlx_lm server \
  --model mlx-community/Qwen2.5-7B-Instruct-4bit \
  --host 127.0.0.1 \
  --port 8080
```

Start OpenJarvis:

```bash
cd /Users/ln-mini/OpenJarvis
OPENJARVIS_CONFIG=/Users/ln-mini/.openjarvis/config.toml \
OPENJARVIS_NO_UPDATE_CHECK=1 \
uv run jarvis serve --host 127.0.0.1 --port 8000 --engine ollama --model qwen3.5:9b
```

Start the frontend:

```bash
cd /Users/ln-mini/OpenJarvis/frontend
npm run dev -- --host 127.0.0.1
```

Open:

```text
http://127.0.0.1:5173/agent-lab
```

When Agent Lab is opened inside the OpenJarvis desktop/Tauri shell, the
Services panel can start and stop managed local services without a terminal:

- Ollama on `127.0.0.1:11434`
- OpenJarvis API on `127.0.0.1:8000`
- MLX-LM server on `127.0.0.1:8080`

Browser/PWA mode can still show readiness, but it cannot start local processes
directly. That restriction is intentional browser security behavior.

## Page Layout

### Readiness header

The top of the page shows whether the backend is reachable and how many models
the backend currently lists. If the backend is offline, sample execution is
disabled and the page shows an error.

### Services panel

The Services panel detects Ollama, MLX, and the OpenJarvis API. In the desktop
app it also exposes Start and Stop buttons. Stop only terminates processes that
the desktop app started; if you launched a service manually in a terminal, Agent
Lab marks it as external and leaves it alone.

### Sample Agents

The left column lists the sample scenarios:

| Scenario | Template | What it checks |
|---|---|---|
| Codebase Maintainer Smoke | `local-codebase-maintainer` | File inspection, scoped implementation thinking, and test planning |
| Personal Intel Router Smoke | `personal-intel-router` | Durable facts, next actions, uncertainty, and future value |
| Local Research Scout Smoke | `local-research-scout` | Local-first research, source freshness, and open questions |

Selecting a scenario updates the prompt, allowed tools, and validation checks.

### Prompt editor

The prompt editor starts with a deterministic QA prompt. You can edit it before
running the sample. If you edit heavily, validators may fail because they check
for scenario-specific behavior.

### Advanced controls

The Advanced panel exposes:

| Control | Default | Notes |
|---|---|---|
| Engine | `auto` | Prefers reachable Ollama, then falls back to current server engine |
| Model | first backend model, if listed | Use `qwen3.5:9b` for Ollama fallback |
| Turns | `10` | Converted into a bounded token budget for sample runs |
| Temperature | scenario/template default | Lower values are more stable for QA |

Use `engine=ollama` when you want to prove the local Ollama path. Use
`engine=mlx` only after the MLX server is running at `127.0.0.1:8080`.

## Running A Sample

1. Pick a scenario in the Sample Agents list.
2. Confirm the backend says ready.
3. Optionally open Advanced and choose `ollama` plus `qwen3.5:9b`.
4. Click Run Sample.
5. Wait for the result.
6. Review:
   - generated answer
   - pass/fail checks
   - engine and model
   - latency
   - token usage
   - allowed tools or returned tool calls
7. Use Copy or Export to save the JSON result.

## Understanding Results

Sample status values:

| Status | Meaning |
|---|---|
| `passed` | The model output satisfied all scenario validators |
| `failed` | The model responded, but one or more validators failed |
| `error` | The backend could not run the sample |
| `running` | The UI has submitted the request and is waiting |

Common errors:

| Error | Likely cause | Fix |
|---|---|---|
| Vite proxy `ECONNREFUSED` for `/v1/...` | Frontend is running, but the OpenJarvis API server is not | Start `jarvis serve` on port 8000, then refresh the UI |
| `Model 'qwen3.5:9b' not found in any engine (known: <none>)` | API server started before a healthy engine/model was visible | Start Ollama, confirm `ollama list`, then restart `jarvis serve --engine ollama --model qwen3.5:9b` |
| `404 Not Found` for `http://localhost:8080/v1/chat/completions` | Something is on port 8080, but it is not the MLX OpenAI-compatible chat server | Stop the other process or use another port, then start MLX with the command below and verify `/v1/models` |
| `ollama is not reachable` | Ollama app/server is not running | Start Ollama and retry |
| `mlx is not reachable` | MLX server is not running | Start `python -m mlx_lm server` and retry |
| `No inference engine is configured` | API server started without an engine | Restart `jarvis serve` with the user config |
| No models detected | Engine lists no models | Pull an Ollama model or start MLX with a model |

Quick health checks:

```bash
curl -s http://127.0.0.1:8000/health
curl -s http://127.0.0.1:8000/v1/models
/Applications/Ollama.app/Contents/Resources/ollama list
curl -s http://127.0.0.1:8080/v1/models
```

## Suggested Real End-to-End Validation

The next validation should go beyond mocked route tests and controlled browser
rendering.

### Ollama path

1. Start Ollama.
2. Confirm the model exists:

   ```bash
   /Applications/Ollama.app/Contents/Resources/ollama list
   ```

3. Start OpenJarvis and the frontend.
4. Open `/agent-lab`.
5. Open Advanced.
6. Set engine to `ollama`.
7. Set model to `qwen3.5:9b`.
8. Run all three scenarios.
9. Export each JSON result.
10. Record pass/fail, latency, token usage, and whether the answer was useful.

### MLX path

1. Start MLX server:

   ```bash
   uv run python -m mlx_lm server \
     --model mlx-community/Qwen2.5-7B-Instruct-4bit \
     --host 127.0.0.1 \
     --port 8080
   ```

2. Open `/agent-lab`.
3. Open Advanced.
4. Set engine to `mlx`.
5. Run the Local Research Scout scenario.
6. Export the result.
7. Compare latency, token usage, and response quality with Ollama.

### Real managed-agent path

After sample runs pass, create a true managed agent:

1. Open Agents.
2. Create `local-codebase-maintainer`.
3. Use manual schedule.
4. Send a repository QA prompt.
5. Run the agent.
6. Inspect Logs/trace output.
7. Confirm the run has a real agent id, persisted messages, and visible tool
   events.

This is the point where Agent Lab moves from "controlled sample QA" to a full
agent lifecycle demonstration.

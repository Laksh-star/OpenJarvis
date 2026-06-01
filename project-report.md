# OpenJarvis Agent Lab Project Report

Date: June 1, 2026

This note summarizes the OpenJarvis fork work completed so far: Apple Silicon local inference setup, Ollama and MLX integration, Agent Lab sample QA, desktop service controls, validation status, and the practical next steps.

## 1. Original Goal

The goal was to make this OpenJarvis fork usable on a 24 GB Apple Silicon Mac Mini as a local-first agent workspace.

The target experience was:

- Use Ollama as the default local inference engine.
- Support MLX as an optional Apple Silicon-optimized engine.
- Add custom sample agents and a QA harness.
- Expose all of this through an easy UI, not only CLI commands.
- Allow a normal user to start services, run sample agents, inspect results, and export output.
- Keep live connector tests separate from local sample-agent validation, so missing external credentials do not block local testing.

## 2. Main Product Shape

We built this as an "Agent Lab" inside the existing OpenJarvis FastAPI + React + Tauri stack.

This is not a separate app. It is integrated into OpenJarvis:

- Backend: OpenJarvis FastAPI server.
- Frontend: existing React app.
- Desktop shell: existing Tauri app.
- Local inference: Ollama by default, MLX optional.

The browser/PWA path still works, but the service launcher features are only available inside the Tauri desktop app because browsers cannot safely start and stop local server processes.

## 3. Agent Lab UI

Added a new Agent Lab page in the frontend.

Key UI features:

- Sample agent list.
- Prompt editor with safe default prompts.
- One-click sample run.
- Backend/model readiness display.
- Service panel for Ollama, OpenJarvis API, and MLX.
- Engine selection through Advanced controls.
- Result panel with pass/fail status.
- QA validator summary.
- Tool-call timeline.
- Copy and export controls.

Relevant files:

- `frontend/src/pages/AgentLabPage.tsx`
- `frontend/src/App.tsx`
- `frontend/src/components/Sidebar/Sidebar.tsx`
- `frontend/src/lib/api.ts`

Current observed working state:

- Agent Lab loads at `http://127.0.0.1:5173/agent-lab`.
- In the Tauri desktop app, Agent Lab can manage local services.
- Ollama shows Ready.
- OpenJarvis API shows Ready.
- MLX now shows Ready after dependency sync and startup fixes.
- A sample run passed using `ollama / qwen3.5:9b`.

## 4. Sample Agents Added

Three local sample agents were added as templates.

### 4.1 Local Codebase Maintainer

Template id: `local-codebase-maintainer`

Purpose:

- Review a local codebase issue.
- Identify likely files to inspect.
- Propose a scoped edit.
- Name the exact test command to run.
- Avoid writing files during the sample run.

Sample scenario:

- Failing test: `test_total_handles_empty_cart`
- Expected behavior: the answer should mention a likely file, scoped fix, and pytest/test verification.

Template file:

- `src/openjarvis/templates/data/local-codebase-maintainer.toml`

### 4.2 Personal Intel Router

Template id: `personal-intel-router`

Purpose:

- Route incoming personal/work signals into actionable categories.
- Separate urgent items from low-value noise.
- Produce a concise action list.

Sample scenario:

- Local fixture-style prompt with mixed personal intel.
- Expected behavior: prioritize, summarize, and produce clear next actions.

Template file:

- `src/openjarvis/templates/data/personal-intel-router.toml`

### 4.3 Local Research Scout

Template id: `local-research-scout`

Purpose:

- Research a local question using supplied local context.
- Produce a concise synthesis.
- Identify gaps and follow-up checks.

Sample scenario:

- Local research prompt with no live web credential requirement.
- Expected behavior: cite local evidence from the prompt, summarize findings, and name unresolved questions.

Template file:

- `src/openjarvis/templates/data/local-research-scout.toml`

## 5. Backend Sample Run Harness

Added a backend sample-run module that defines deterministic local scenarios and validators.

Main capabilities:

- Registers available sample scenarios.
- Maps each scenario to a real agent template.
- Stores scenario prompt, expected allowed tools, timeout, and validators.
- Executes a controlled run through the existing OpenJarvis serving path.
- Returns structured status, model/engine metadata, result text, diagnostics, and QA checks.
- Keeps local sample validation separate from live connector tests.

Relevant files:

- `src/openjarvis/server/sample_runs.py`
- `src/openjarvis/server/api_routes.py`
- `tests/server/test_sample_runs.py`

Added API endpoints:

- `GET /v1/sample-runs`
- `POST /v1/sample-runs/{id}/execute`
- `GET /v1/sample-runs/{run_id}`

The existing `GET /v1/templates` remains the source of agent templates.

## 6. Ollama Integration

Ollama is the default inference engine for local users.

Configured/default model target:

- `qwen3.5:9b`

Observed working result:

- Agent Lab ran a sample successfully on `ollama / qwen3.5:9b`.
- The sample result passed all visible QA checks.

Fixes made:

- Improved model/engine resolution so OpenJarvis does not fail with "known: <none>" when Ollama is reachable.
- Added fallback behavior so the server can resolve to a reachable Ollama model when an MLX model is unavailable.
- Added clearer readiness and model-availability behavior.

Relevant backend file:

- `src/openjarvis/cli/serve.py`

Related test file:

- `tests/cli/test_serve_model_resolution.py`

## 7. MLX Integration

MLX support was added for Apple Silicon, using `mlx-lm`.

Target MLX model:

- `mlx-community/Qwen2.5-7B-Instruct-4bit`

The MLX server is expected on:

- `http://127.0.0.1:8080`

Important detail:

- The MLX server has `/v1/models`.
- We confirmed that chat readiness must be checked against `/v1/chat/completions`.
- Earlier, MLX returned 404 on `/v1/chat/completions` in one path, so readiness checking was tightened to catch this correctly.

Final issue found:

- Tauri was starting the right Python, but the repo `.venv` did not have `mlx_lm` installed.
- Error shown: `No module named mlx_lm`.

Final fix:

- The Tauri `Start MLX` flow now runs:

```bash
uv sync --extra server --extra inference-mlx
```

- Then it starts MLX with:

```bash
uv run python -m mlx_lm server --model mlx-community/Qwen2.5-7B-Instruct-4bit --host 127.0.0.1 --port 8080
```

- If dependency sync fails, Agent Lab now shows the real `uv sync` error.
- If MLX starts but chat completion fails, Agent Lab shows the MLX stderr tail.

Relevant file:

- `frontend/src-tauri/src/lib.rs`

Current observed state:

- MLX now shows Ready in Agent Lab.
- MLX shows `1 models`.
- MLX is managed by the desktop app.

Remaining confirmation:

- The screenshot confirms MLX service readiness.
- The last sample run shown still used `ollama / qwen3.5:9b`.
- To confirm MLX generation end to end, use Advanced controls, select MLX, and run a sample. The result header should show MLX instead of Ollama.

## 8. Tauri Desktop Service Launcher

The key usability improvement was adding service controls inside the desktop app.

Services managed:

- Ollama
- OpenJarvis API
- MLX

The Agent Lab service panel can:

- Detect service readiness.
- Start Ollama.
- Start OpenJarvis API.
- Start MLX.
- Stop managed services.
- Refresh status.
- Start Ollama + API together.

Important browser vs desktop distinction:

- `http://127.0.0.1:5173/agent-lab` in a normal browser is the web frontend.
- The native Tauri app launched by `npm run tauri dev` is the desktop app.
- Only the desktop app can start and stop services.
- The browser can detect readiness but cannot manage local processes.

Relevant file:

- `frontend/src-tauri/src/lib.rs`

Important fixes in Tauri:

- Added service status command.
- Added service start command.
- Added service stop command.
- Added MLX child process tracking.
- Added MLX stderr tail capture.
- Added MLX chat readiness check.
- Added auto-sync of MLX optional dependencies.
- Added manual binary resolution for Ollama app bundle:

```text
/Applications/Ollama.app/Contents/Resources/ollama
```

This fixed the case where Ollama was installed as a macOS app but not visible in the desktop app's inherited PATH.

## 9. API and Engine Error Improvements

Improved OpenAI-compatible engine diagnostics.

Before:

- MLX or other OpenAI-compatible endpoints could fail with vague 404 errors.

After:

- 404s include response body where possible.
- Error messages explain when a port is not serving an OpenAI-compatible chat endpoint.
- MLX sample execution maps Ollama model names to MLX default model behavior when needed.

Relevant files:

- `src/openjarvis/engine/_openai_compat.py`
- `src/openjarvis/server/sample_runs.py`
- `src/openjarvis/cli/serve.py`

## 10. Documentation Added

Documentation was added for setup, user operation, and testing.

Files:

- `docs/user-guide/agent-lab.md`
- `docs/getting-started/apple-silicon-mlx-ollama.md`
- `docs/agent-lab/README.md`
- `docs/testing/agent-lab-test-report.md`
- `scripts/setup-mac-mini-24gb.sh`
- `configs/openjarvis/examples/mac-mini-24gb-mlx-ollama.toml`

The docs cover:

- Apple Silicon setup.
- Ollama setup.
- MLX setup.
- Agent Lab usage.
- Test commands.
- Manual smoke steps.
- Separation between local sample QA and live connector tests.

## 11. Test and Build Commands Run

### 11.1 Backend focused tests

Command:

```bash
.venv/bin/python -m pytest tests/server/test_sample_runs.py tests/cli/test_serve_model_resolution.py -q
```

Result:

```text
11 passed
```

Coverage:

- Sample scenario registry.
- Scenario references to real templates.
- Validator pass/fail behavior.
- Sample execution response shape.
- Engine/model resolution behavior.

### 11.2 Frontend build

Command:

```bash
PATH=/Users/ln-mini/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin:$PATH npm run build
```

Result:

- Passed.

### 11.3 Tauri frontend build

Command:

```bash
PATH=/Users/ln-mini/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin:$PATH npm run build:tauri
```

Result:

- Passed.

### 11.4 Tauri Rust check

Command:

```bash
cd frontend/src-tauri
cargo check
```

Result:

- Passed.
- Existing macOS `objc` macro warnings remain.
- These warnings are not from the Agent Lab changes and do not block compilation.

### 11.5 Latest Rust check after MLX auto-sync fix

Command:

```bash
cd /Users/ln-mini/OpenJarvis/frontend/src-tauri
cargo fmt
cargo check
```

Result:

- `cargo fmt` completed.
- `cargo check` passed.
- Same existing macOS `objc` warnings appeared.

## 12. Manual Smoke Results

### 12.1 Ollama sample run

Observed in Agent Lab:

- Engine/model: `ollama / qwen3.5:9b`
- Runtime shown in UI: approximately 33-41 seconds in observed screenshots.
- QA status: passed.
- Checks passed:
  - Mentions a test or pytest verification.
  - Mentions inspecting or editing a file.
  - Keeps the change scoped.
- Tool timeline shown:
  - `think`
  - `file_read`
  - `shell_exec`

### 12.2 MLX service readiness

Observed in Agent Lab:

- MLX status: Ready.
- Models: `1 models`.
- Managed: yes.

This means the MLX server has started and the service panel detects it.

Still to confirm:

- Run a sample with Advanced engine set to MLX and verify the result header says MLX.

## 13. Current How-To: Launch Next Time

### Desktop app path

Use this when you want service start/stop buttons.

```bash
cd /Users/ln-mini/OpenJarvis/frontend
npm run tauri dev
```

Then:

1. Open Agent Lab in the desktop app.
2. Click Refresh if needed.
3. Start Ollama + API if not already ready.
4. Start MLX if you want MLX.
5. Run a sample agent.

### Browser-only path

Use this only when services are already running.

```bash
cd /Users/ln-mini/OpenJarvis/frontend
npm run dev
```

Then open:

```text
http://127.0.0.1:5173/agent-lab
```

Browser-only mode can inspect readiness and run samples if the backend is already running, but it cannot start or stop Ollama, MLX, or the OpenJarvis API.

## 14. Current How-To: Confirm MLX End to End

1. Launch desktop:

```bash
cd /Users/ln-mini/OpenJarvis/frontend
npm run tauri dev
```

2. Go to Agent Lab.

3. Confirm service states:

- Ollama: Ready.
- OpenJarvis API: Ready.
- MLX: Ready.

4. Open Advanced.

5. Select MLX as the engine.

6. Run `Codebase Maintainer Smoke`.

7. Confirm result header says MLX, for example:

```text
mlx / mlx-community/Qwen2.5-7B-Instruct-4bit
```

or the MLX default model.

If it still says:

```text
ollama / qwen3.5:9b
```

then the run used Ollama, not MLX.

## 15. Important Lessons Learned

### 15.1 Desktop service management is necessary

For the "any user can use it" goal, asking users to keep multiple terminals open is too fragile.

The Tauri desktop app is the right place to manage:

- Ollama process.
- OpenJarvis API process.
- MLX process.

### 15.2 Browser and desktop must be explained clearly

The UI looks similar in the browser and in the Tauri app, but the capabilities are different.

Browser:

- Can call APIs.
- Can show status.
- Cannot start local services.

Desktop:

- Can call APIs.
- Can show status.
- Can start and stop local services.

### 15.3 MLX readiness must check chat completion

`/v1/models` alone is not enough.

The MLX server can respond to `/v1/models` while `/v1/chat/completions` is still unavailable or incompatible. The readiness check now verifies chat completion as well.

### 15.4 Optional dependencies must be installed by the launcher

The error:

```text
No module named mlx_lm
```

was not an MLX server bug. It meant the project virtualenv did not include the `inference-mlx` optional dependency.

The desktop app now syncs the required extra before starting MLX.

## 16. Current Known Limitations

1. MLX sample generation still needs one final manual confirmation.

   MLX service is Ready, but the shown sample result used Ollama. Run a sample with Advanced engine set to MLX and confirm the result header.

2. Agent Lab sample agents are smoke-test scenarios, not full real-world agents yet.

   They are useful for validating local agent behavior, but the next step is a real end-to-end use case with real local files or real connected data.

3. Live connector tests remain separate.

   Oura, Strava, Spotify, Google, and similar credentials are not required for local Agent Lab validation.

4. Existing macOS Rust warnings remain.

   `cargo check` passes, but the `objc` macro warnings still print. These appear to be existing dependency/macro warnings rather than a functional failure.

5. `uv.lock` changed substantially during dependency work.

   This should be reviewed before committing to make sure the lockfile change is expected and not accidental churn.

## 17. Recommended Next Steps

### Step 1: Confirm MLX sample generation

Run one sample through MLX from Agent Lab Advanced settings.

Success criteria:

- MLX service is Ready.
- Sample run completes.
- Result header shows MLX.
- QA checks pass.

### Step 2: Build one real end-to-end agent use case

The next useful milestone is a real local agent, not another smoke prompt.

Good candidate use cases:

1. Local Repo Maintainer

   The agent inspects this OpenJarvis fork, reads failing tests or TODOs, proposes patches, and optionally opens a guarded edit flow.

2. Personal Intelligence Router

   The agent ingests local markdown notes, exported emails, meeting notes, or pasted snippets and routes them into action buckets.

3. Local Research Scout

   The agent reads a local folder of PDFs/notes/markdown and produces a research brief with evidence, gaps, and next actions.

4. Apple Silicon Model Bench Lab

   The agent compares Ollama vs MLX runs on the same prompt, records latency, model, pass/fail checks, and output quality notes.

Recommended first real use case:

- Local Repo Maintainer.

Reason:

- It is fully local.
- It does not need third-party credentials.
- It directly improves this project.
- It can test tools, file reading, shell command planning, and QA checks.

### Step 3: Add persisted run history

Agent Lab currently shows the current run well. The next improvement is a persistent run history:

- Save runs by scenario.
- Store engine/model/latency.
- Keep QA check results.
- Allow export as Markdown.
- Compare Ollama vs MLX runs.

### Step 4: Add a real benchmark panel

For Apple Silicon tuning, add:

- Tokens per second.
- Time to first token.
- Total latency.
- Engine.
- Model.
- Prompt length.
- Output length.
- Memory estimate if available.

This would make Agent Lab useful as both an agent QA UI and a local inference comparison tool.

### Step 5: Package the desktop flow

Eventually, move from `npm run tauri dev` to a packaged local app:

- Build signed or local `.app`.
- First-run setup wizard.
- Start/stop services from tray.
- Agent Lab as default local user workflow.

## 18. Quick Status Summary

Completed:

- Agent Lab page.
- Sample agent templates.
- Backend sample-run API.
- Local validators.
- Ollama path.
- MLX service launcher.
- Tauri service start/stop controls.
- Better engine/model readiness handling.
- Better OpenAI-compatible endpoint diagnostics.
- Apple Silicon docs.
- Focused backend tests.
- Frontend build validation.
- Tauri compile validation.

Working now:

- Ollama sample run passes.
- OpenJarvis API is managed and ready.
- MLX service is managed and ready.

Needs final confirmation:

- A sample run using MLX as the selected engine.

Recommended next build:

- Real Local Repo Maintainer end-to-end agent flow with run history and Ollama-vs-MLX comparison.

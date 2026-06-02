# Code Review: OpenJarvis Agent Lab, Ollama, and MLX Work

Date: June 1, 2026

Reviewer perspective: senior developer / architect review of the fork-specific Agent Lab work and the smaller upstream PR extracted from it.

## Executive Summary

This review covers the OpenJarvis fork changes made to support a local-first Agent Lab on Apple Silicon, including Ollama, optional MLX, sample-agent QA scenarios, frontend UI, Tauri service controls, and supporting documentation.

Overall assessment:

- The fork has reached a useful local prototype milestone.
- The user-facing workflow is materially better than a terminal-only setup.
- The engine/model resolution work is clean, focused, and appropriate for upstream.
- The Agent Lab UI and Tauri service launcher are valuable fork features, but they need more lifecycle hardening before they should be proposed upstream.
- The most important architectural caveat is that current "sample agent" runs validate model responses against prompts, but they do not yet execute true agents or real tool calls.

The current implementation is good enough for local model smoke testing and guided sample QA. It should not yet be described as full end-to-end agent/tool validation without qualification.

## Scope Reviewed

The review was performed against the fork `main` branch after the Agent Lab PR was merged into the fork and the fork was synced with the parent repository.

Compared baseline:

- `upstream/main`

Reviewed change areas:

- Engine/model resolution fixes.
- OpenAI-compatible engine error diagnostics.
- Backend sample-run registry and execution route.
- Three custom sample agent templates.
- Agent Lab frontend page.
- Tauri service start/stop/status controls.
- Apple Silicon, Ollama, and MLX documentation.
- Test coverage added for backend sample runs and model resolution.

Key files reviewed:

- `src/openjarvis/cli/serve.py`
- `src/openjarvis/engine/_openai_compat.py`
- `src/openjarvis/server/sample_runs.py`
- `src/openjarvis/server/api_routes.py`
- `src/openjarvis/agents/manager.py`
- `frontend/src/pages/AgentLabPage.tsx`
- `frontend/src/lib/api.ts`
- `frontend/src-tauri/src/lib.rs`
- `tests/cli/test_serve_model_resolution.py`
- `tests/server/test_sample_runs.py`
- `docs/user-guide/agent-lab.md`
- `docs/getting-started/apple-silicon-mlx-ollama.md`
- `docs/testing/agent-lab-test-report.md`
- `project-report.md`

## What Was Built

### 1. Engine and Model Resolution

The server startup path was improved so config-driven startup can fall back to a reachable model when the configured model is unavailable.

Key behavior:

- Explicit CLI `--model` remains authoritative.
- Configured server/default/fallback models are checked against reachable models.
- Healthy discovered engines can be included in a `MultiEngine`.
- The user gets a clearer error when no local model is available.

This work was extracted into a clean upstream branch:

- Branch: `upstream-engine-model-resolution`
- Commit: `b407148c Improve local engine model resolution`

Focused test result:

```bash
uv run --extra dev --extra server python -m pytest tests/cli/test_serve_model_resolution.py -q
```

```text
3 passed in 0.36s
```

Assessment:

This is the cleanest and most upstream-ready part of the work.

### 2. OpenAI-Compatible Engine Diagnostics

OpenAI-compatible engine failures now surface clearer HTTP diagnostics.

Particularly useful case:

- A local service is reachable but returns `404` for `/v1/chat/completions`.

The new message distinguishes this from generic connection failure and tells the user the port may not be serving an OpenAI-compatible chat endpoint.

Assessment:

Good, practical improvement. This belongs with the engine/model-resolution upstream PR.

### 3. Backend Sample-Run Harness

Added a sample-run module:

- `src/openjarvis/server/sample_runs.py`

It defines:

- deterministic sample scenarios
- scenario metadata
- template ids
- prompt defaults
- allowed tool labels
- timeout metadata
- validators
- result storage
- route creation

Exposed endpoints:

- `GET /v1/sample-runs`
- `POST /v1/sample-runs/{scenario_id}/execute`
- `GET /v1/sample-runs/{run_id}`

Three sample scenarios were added:

- `local-codebase-maintainer-smoke`
- `personal-intel-router-smoke`
- `local-research-scout-smoke`

Assessment:

Useful for local smoke testing, but the implementation is currently prompt/model QA, not true agent/tool QA.

### 4. Agent Templates

Three template files were added:

- `src/openjarvis/templates/data/local-codebase-maintainer.toml`
- `src/openjarvis/templates/data/personal-intel-router.toml`
- `src/openjarvis/templates/data/local-research-scout.toml`

These templates are good examples for local-first workflows:

- codebase maintenance
- personal intel routing
- local research scouting

Assessment:

Good fork content. For upstream, these should be positioned as example templates or smoke-test templates, not production-ready personal agents.

### 5. Agent Lab UI

Added:

- `frontend/src/pages/AgentLabPage.tsx`

Main UI capabilities:

- sample scenario list
- prompt editor
- advanced engine/model controls
- one-click run
- status/result panel
- validator checklist
- service panel for Ollama, OpenJarvis API, and MLX
- copy/export controls

Assessment:

The UI is practical and aligned with the user's goal of making the local setup accessible. It is not a marketing page; it is an actual tool surface. It does, however, need more precision around what the "Tool Timeline" represents.

### 6. Tauri Service Launcher

The desktop app can now manage:

- Ollama
- OpenJarvis API
- MLX

Important additions:

- service readiness checks
- start/stop commands
- child process tracking
- MLX stderr tail capture
- MLX dependency sync before start
- MLX chat readiness check during startup
- macOS Ollama app bundle binary resolution

Assessment:

This is the right direction for local usability. The remaining risks are lifecycle and status semantics, not overall architecture.

### 7. Documentation

Added documentation for:

- Agent Lab user guide
- Apple Silicon setup
- testing report
- local setup script
- project report

Assessment:

Good for the fork. `project-report.md` should remain fork-local and should not go upstream.

## Findings

### P1: Sample Runs Do Not Actually Execute Agents or Tools

Location:

- `src/openjarvis/server/sample_runs.py`
- Execution path around `engine.generate(...)`
- UI fallback tool display in `frontend/src/pages/AgentLabPage.tsx`

Issue:

The sample-run backend records `allowed_tools`, but does not execute an agent runner, managed-agent flow, tool registry, or tool permissions path. It calls the inference engine directly:

```python
raw = engine.generate(...)
```

The UI then displays `allowed_tools` as a fallback timeline if no actual tool calls are returned.

Impact:

This can overstate what has been validated. The current harness proves that a selected model can answer a prompt in a way that satisfies validators. It does not prove that an agent selected tools, executed tools, or produced trace-backed tool activity.

Recommendation:

Choose one of two paths:

1. Relabel current behavior as "sample prompt QA" or "model smoke QA".
2. Wire sample execution through the real agent/trace path so tool calls are actual observed events.

Preferred path:

Wire it through the real agent path. The product name "Agent Lab" implies agent/tool behavior, and the tool timeline should be evidence-backed.

### P2: MLX Status Can Report Ready Without Proving Chat Generation Works

Location:

- `frontend/src-tauri/src/lib.rs`
- `agent_lab_service_status`

Issue:

MLX startup validates chat completion with `/v1/chat/completions`, but periodic service status marks MLX ready based on `/v1/models`.

Impact:

A service on port `8080` can respond to `/v1/models` while still not supporting the chat endpoint needed for generation. The UI may show MLX as Ready even if sample generation would fail.

Recommendation:

Use `mlx_chat_ready()` in the service status path, or expose two states:

- `mlx_models_ready`
- `mlx_chat_ready`

For the UI, "Ready" should mean generation is possible.

### P2: Failed Service Starts Can Leave Child Processes Running

Location:

- `frontend/src-tauri/src/lib.rs`
- `start_mlx_service`
- `start_jarvis_service`

Issue:

The launcher stores child process handles before readiness is fully confirmed. If readiness fails, the function returns an error, but the process may still be running and marked as managed internally.

Impact:

The user can see a startup error while the service is actually still running in the background. This can create confusing state and port conflicts on retry.

Recommendation:

On readiness failure:

- kill the child process and remove the handle, or
- return a structured status that clearly says the process is managed but unhealthy.

Preferred path:

For v1, kill/remove on readiness failure. It is simpler and less surprising.

### P2: Sample Run Storage Is In-Memory and Unbounded

Location:

- `src/openjarvis/server/sample_runs.py`
- `_RUNS`

Issue:

Sample results are stored in a module-level dictionary and never evicted.

Impact:

This is acceptable for early smoke testing but not for a long-running desktop app. Results disappear on restart and can grow indefinitely during a session.

Recommendation:

Replace with one of:

- capped in-memory ring buffer
- persisted trace/session-store backed result lookup
- small local SQLite table if consistent with existing app storage

Preferred path:

Use existing trace/session style storage so the UI and logs can converge.

### P3: Scenario Timeout Is Declared But Not Enforced

Location:

- `src/openjarvis/server/sample_runs.py`
- `SampleScenario.timeout_seconds`

Issue:

Each scenario defines `timeout_seconds`, but the execution endpoint does not enforce it.

Impact:

A slow or hung local engine can exceed the scenario's advertised timeout and block the request longer than expected.

Recommendation:

Enforce timeout at route execution level or pass timeout into the engine client if supported.

### P3: Advanced Tool Controls Are Not Yet Functional

Location:

- `frontend/src/pages/AgentLabPage.tsx`
- `src/openjarvis/server/sample_runs.py`

Issue:

The backend accepts `tools`, and the frontend displays tool-related data, but tools are not used by the execution path.

Impact:

Users may believe they are constraining tool execution when they are only changing metadata returned in the result.

Recommendation:

Hide advanced tool controls until the execution path uses them, or make the label explicit: "Expected tools" / "Allowed tool labels".

### P3: Service Start Uses Fixed Ports and Fixed Models

Location:

- `frontend/src-tauri/src/lib.rs`

Issue:

The service launcher hardcodes:

- Ollama port `11434`
- OpenJarvis API port `8000`
- MLX port `8080`
- Ollama Agent Lab model `qwen3.5:9b`
- MLX model `mlx-community/Qwen2.5-7B-Instruct-4bit`

Impact:

Good for the 24 GB Mac Mini target, but less flexible for broader use.

Recommendation:

Longer term, read these from config and expose compact settings in Agent Lab.

## Strengths

### Clear Product Direction

The work correctly prioritizes local usability:

- no terminal required after setup
- visible service status
- sample scenarios
- prompt editor
- pass/fail summary
- export/copy

This is the right direction for a local-first agent tool.

### Good Upstream Extraction

The engine/model-resolution fix was separated into a small parent PR. This is exactly how the work should be upstreamed:

- small diff
- focused behavior
- focused tests
- no lockfile churn
- no UI/product direction debate

### Practical MLX Debugging Improvements

The MLX path now captures stderr and distinguishes:

- missing package
- server not ready
- chat completion failure

This materially improves local debugging.

### Validation Uses Observable Outcomes

The sample validators check for terms/behavior rather than exact output text. This is the right level for LLM smoke testing.

### Documentation Is Strong

The docs explain the browser vs desktop distinction, local service setup, and current manual smoke path. This is important because much of the confusion came from visually similar browser and desktop surfaces with different capabilities.

## Test Review

### Existing Tests Added

Focused engine tests:

- `tests/cli/test_serve_model_resolution.py`

Sample-run tests:

- `tests/server/test_sample_runs.py`

Verified focused backend tests:

```bash
uv run --extra dev --extra server python -m pytest tests/server/test_sample_runs.py tests/cli/test_serve_model_resolution.py -q
```

Previous result:

```text
11 passed
```

Upstream-focused parent PR test:

```bash
uv run --extra dev --extra server python -m pytest tests/cli/test_serve_model_resolution.py -q
```

Result:

```text
3 passed in 0.36s
```

### Test Gaps

Recommended additions:

1. Test that MLX status requires chat readiness, not just model listing.
2. Test service launcher cleanup on failed readiness.
3. Test sample-run timeout enforcement.
4. Frontend test that failed sample run preserves prompt state.
5. Frontend test that service controls are hidden/disabled outside Tauri.
6. Integration-style test for sample run trace persistence once storage is made durable.

## Upstream Strategy

Recommended upstream sequence:

### PR 1: Engine/model resolution

Status:

- Already prepared as a small parent PR branch.
- Good upstream candidate.

Reason:

- Fixes a general local-inference problem.
- Small diff.
- Has tests.
- Does not force Agent Lab product direction on maintainers.

### PR 2: OpenAI-compatible diagnostics

This can remain part of PR 1 or be separate if maintainers ask for tighter scope.

### PR 3: Sample-run backend API

Potentially upstreamable after discussion.

Required before upstream:

- Clarify naming as sample prompt QA, or
- wire into real agent execution.

### PR 4: Agent Lab UI

Hold back for now.

Reason:

- Larger product direction.
- Depends on settling whether backend is true agent execution or prompt QA.

### PR 5: Tauri service launcher

Hold back for now.

Reason:

- Process lifecycle, dependency sync, ports, and security posture need explicit maintainer buy-in.

## Recommended Next Engineering Work

### 1. Make Agent Lab Execute Real Agents

Goal:

Sample runs should produce actual tool events and trace entries.

Expected result:

- `tool_calls` are real, not fallback labels.
- allowed tools are enforced.
- trace view accurately reflects execution.

### 2. Harden Desktop Service Lifecycle

Tasks:

- Kill/remove child on readiness failure.
- Differentiate external vs managed-but-unhealthy services.
- Add a "last error" field per service.
- Avoid showing Ready unless generation endpoint works.

### 3. Add Persistent Run History

Tasks:

- Persist run metadata.
- Store prompt, engine, model, latency, checks, and result.
- Add UI history panel.
- Allow Ollama vs MLX comparison.

### 4. Add MLX/Ollama Benchmark Panel

Useful metrics:

- engine
- model
- latency
- prompt tokens
- output tokens
- tokens per second if available
- pass/fail validators

This would turn Agent Lab into both a QA tool and a local inference tuning tool.

### 5. Generalize Apple Silicon Config

Tasks:

- Move hardcoded models/ports into config.
- Expose compact settings in UI.
- Keep Mac Mini defaults as a preset, not the only path.

## Final Verdict

The work is a strong fork-level milestone and a good foundation for a local-first OpenJarvis experience. It solves real setup and usability problems: local engine readiness, Ollama/MLX confusion, lack of sample validation, and lack of desktop controls.

The primary architectural correction is precision: current Agent Lab sample runs validate LLM outputs, not actual tool-using agents. That is acceptable for a v1 smoke test, but it should be reflected in naming and documentation until the execution path is upgraded.

The upstream strategy is correct:

1. Send the engine/model-resolution fix first.
2. Keep Agent Lab UI and Tauri launcher in the fork until the core semantics are stronger.
3. Evolve Agent Lab into true agent execution with persistent traces and real tool timelines.

If the next iteration handles real agent/tool execution and service lifecycle cleanup, this becomes much closer to an upstream-quality feature rather than a local prototype.

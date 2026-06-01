"""Sample-agent QA scenarios for the local Agent Lab."""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass
from typing import Any, Dict, List, Literal, Optional

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from openjarvis.core.types import Message, Role, StepType, Trace, TraceStep
from openjarvis.engine._base import EngineConnectionError
from openjarvis.templates.agent_templates import discover_templates

SampleStatus = Literal["queued", "running", "passed", "failed", "error"]


@dataclass(frozen=True)
class ValidatorSpec:
    key: str
    label: str
    any_terms: tuple[str, ...]


@dataclass(frozen=True)
class SampleScenario:
    id: str
    title: str
    template_id: str
    summary: str
    prompt: str
    allowed_tools: tuple[str, ...]
    timeout_seconds: int
    validators: tuple[ValidatorSpec, ...]


class SampleExecuteRequest(BaseModel):
    prompt: Optional[str] = None
    engine: Literal["auto", "current", "ollama", "mlx"] = "auto"
    model: Optional[str] = None
    max_turns: Optional[int] = Field(default=None, ge=1, le=30)
    temperature: Optional[float] = Field(default=None, ge=0.0, le=2.0)
    tools: Optional[List[str]] = None


_SCENARIOS: tuple[SampleScenario, ...] = (
    SampleScenario(
        id="local-codebase-maintainer-smoke",
        title="Codebase Maintainer Smoke",
        template_id="local-codebase-maintainer",
        summary=(
            "Checks that the agent inspects a repo task, proposes focused "
            "edits, and names verification steps."
        ),
        prompt=(
            "You are reviewing a small local repository. The failing test is "
            "`test_total_handles_empty_cart`. Provide a concise maintenance plan "
            "with the likely file to inspect, the safest edit shape, and the exact "
            "test command you would run. Do not write files."
        ),
        allowed_tools=("think", "file_read", "shell_exec"),
        timeout_seconds=120,
        validators=(
            ValidatorSpec(
                "mentions_test",
                "Mentions a test or pytest verification",
                ("test", "pytest"),
            ),
            ValidatorSpec(
                "mentions_file",
                "Mentions inspecting or editing a file",
                ("file", "inspect", "edit"),
            ),
            ValidatorSpec(
                "scoped_change",
                "Keeps the change scoped",
                ("scoped", "focused", "minimal", "safest"),
            ),
        ),
    ),
    SampleScenario(
        id="personal-intel-router-smoke",
        title="Personal Intel Router Smoke",
        template_id="personal-intel-router",
        summary=(
            "Checks that the agent separates durable facts, next actions, "
            "uncertainty, and future value."
        ),
        prompt=(
            "Route this note into future-value buckets: Priya can introduce us "
            "to two robotics founders next Friday. The grant deadline may be "
            "June 12, but the source is second hand. Keep only reusable facts, "
            "risks, and next actions."
        ),
        allowed_tools=("think", "memory_store"),
        timeout_seconds=120,
        validators=(
            ValidatorSpec(
                "future_value",
                "Identifies future value",
                ("future", "reusable", "durable"),
            ),
            ValidatorSpec(
                "next_action",
                "Includes a next action",
                ("next action", "follow", "confirm", "deadline"),
            ),
            ValidatorSpec(
                "uncertainty",
                "Marks uncertain information",
                ("uncertain", "second hand", "verify", "may be"),
            ),
        ),
    ),
    SampleScenario(
        id="local-research-scout-smoke",
        title="Local Research Scout Smoke",
        template_id="local-research-scout",
        summary=(
            "Checks that the agent starts local-first, adds source/date "
            "discipline, and surfaces open questions."
        ),
        prompt=(
            "Prepare a short research scout brief for evaluating whether a local "
            "LLM can triage personal notes. Start from local evidence first, then "
            "state when web search would be justified. Include open questions."
        ),
        allowed_tools=("think", "memory_search", "file_read", "web_search"),
        timeout_seconds=120,
        validators=(
            ValidatorSpec(
                "local_first",
                "Starts with local evidence",
                ("local", "memory", "files"),
            ),
            ValidatorSpec(
                "freshness",
                "Explains when web freshness matters",
                ("web", "fresh", "current", "source"),
            ),
            ValidatorSpec(
                "open_questions",
                "Includes open questions",
                ("open question", "questions", "unknown"),
            ),
        ),
    ),
)

_RUNS: Dict[str, Dict[str, Any]] = {}


def _template_id_from_name(name: str) -> str:
    return name.strip().lower().replace("_", "-").replace(" ", "-")


def list_agent_lab_templates() -> List[Dict[str, Any]]:
    """Return template data normalized for the Agent Lab API/UI."""
    templates = []
    for tpl in discover_templates():
        tpl_id = _template_id_from_name(tpl.name)
        templates.append(
            {
                "id": tpl_id,
                "name": tpl.name,
                "description": tpl.description,
                "source": "built-in",
                "agent_type": tpl.agent_type,
                "tools": tpl.tools,
                "max_turns": tpl.max_turns,
                "temperature": tpl.temperature,
                "system_prompt": tpl.system_prompt,
            }
        )
    return templates


def list_sample_scenarios() -> List[Dict[str, Any]]:
    templates = {t["id"]: t for t in list_agent_lab_templates()}
    return [
        {
            "id": scenario.id,
            "title": scenario.title,
            "template_id": scenario.template_id,
            "template_name": templates.get(scenario.template_id, {}).get(
                "name", scenario.template_id
            ),
            "summary": scenario.summary,
            "prompt": scenario.prompt,
            "allowed_tools": list(scenario.allowed_tools),
            "timeout_seconds": scenario.timeout_seconds,
            "validators": [
                {"key": v.key, "label": v.label} for v in scenario.validators
            ],
        }
        for scenario in _SCENARIOS
    ]


def _get_scenario(scenario_id: str) -> SampleScenario:
    for scenario in _SCENARIOS:
        if scenario.id == scenario_id:
            return scenario
    raise KeyError(scenario_id)


def _resolve_engine(request: Request, requested: str):
    """Resolve the requested engine, preferring local Ollama for auto mode."""
    config = getattr(request.app.state, "config", None)
    app_engine = getattr(request.app.state, "engine", None)
    app_engine_id = getattr(app_engine, "engine_id", "") if app_engine else ""

    if requested == "current":
        return app_engine, app_engine_id or "current"

    if requested == "mlx":
        from openjarvis.engine.openai_compat_engines import MLXEngine

        host = getattr(getattr(config, "engine", None), "mlx", None)
        return MLXEngine(host=getattr(host, "host", None)), "mlx"

    if requested in ("ollama", "auto"):
        from openjarvis.engine.ollama import OllamaEngine

        host = getattr(getattr(config, "engine", None), "ollama", None)
        ollama = OllamaEngine(host=getattr(host, "host", None))
        if requested == "ollama" or ollama.health():
            return ollama, "ollama"

    if requested == "auto" and app_engine is not None:
        return app_engine, app_engine_id or "current"

    return app_engine, app_engine_id or requested


def _default_model(
    request: Request,
    engine,
    engine_id: str,
    requested: Optional[str],
) -> str:
    models = []
    try:
        models = engine.list_models()
    except Exception:
        models = []
    if requested:
        if not models or requested in models:
            return requested
        if engine_id == "mlx":
            # Agent Lab often has the OpenJarvis server model prefilled from
            # Ollama. MLX-LM maps the model passed at server startup to
            # ``default_model``; using an Ollama id here causes a generation
            # exception that MLX-LM reports as HTTP 404.
            return "default_model"
        return requested
    if models:
        return models[0]
    if engine_id == "mlx":
        return "default_model"
    if engine_id == "ollama":
        return "qwen3.5:9b"
    return getattr(request.app.state, "model", "") or "local-model"


def _build_messages(template: Dict[str, Any], prompt: str) -> List[Message]:
    system_prompt = template.get("system_prompt") or (
        "You are an OpenJarvis sample agent. Answer concisely and expose the "
        "observable decisions needed for QA."
    )
    return [
        Message(role=Role.SYSTEM, content=str(system_prompt)),
        Message(role=Role.USER, content=prompt),
    ]


def _validate_output(scenario: SampleScenario, content: str) -> List[Dict[str, Any]]:
    normalized = content.lower()
    checks = []
    for validator in scenario.validators:
        passed = any(term.lower() in normalized for term in validator.any_terms)
        checks.append(
            {
                "key": validator.key,
                "label": validator.label,
                "passed": passed,
            }
        )
    return checks


def _save_trace(
    request: Request,
    *,
    trace_id: str,
    scenario: SampleScenario,
    prompt: str,
    result: Dict[str, Any],
) -> None:
    store = getattr(request.app.state, "trace_store", None)
    if store is None:
        return
    started_at = result["created_at"] - result.get("latency_seconds", 0.0)
    trace = Trace(
        trace_id=trace_id,
        query=prompt,
        agent=scenario.template_id,
        model=result.get("model", ""),
        engine=result.get("engine", ""),
        result=result.get("content", ""),
        outcome="success" if result.get("status") == "passed" else "failure",
        started_at=started_at,
        ended_at=result["created_at"],
        total_tokens=int(result.get("usage", {}).get("total_tokens", 0) or 0),
        total_latency_seconds=float(result.get("latency_seconds", 0.0) or 0.0),
        metadata={
            "sample_run_id": result["run_id"],
            "scenario_id": scenario.id,
            "checks": result.get("checks", []),
        },
        messages=[
            {"role": "user", "content": prompt},
            {"role": "assistant", "content": result.get("content", "")},
        ],
        steps=[
            TraceStep(
                step_type=StepType.GENERATE,
                timestamp=started_at,
                duration_seconds=float(result.get("latency_seconds", 0.0) or 0.0),
                input={
                    "prompt": prompt,
                    "allowed_tools": result.get("allowed_tools", []),
                },
                output={
                    "content": result.get("content", ""),
                    "tokens": int(result.get("usage", {}).get("total_tokens", 0) or 0),
                },
                metadata={"scenario_id": scenario.id},
            )
        ],
    )
    try:
        store.save(trace)
    except Exception:
        pass


def _error_result(
    run_id: str,
    scenario: SampleScenario,
    engine_id: str,
    model: str,
    message: str,
) -> Dict[str, Any]:
    return {
        "run_id": run_id,
        "scenario_id": scenario.id,
        "template_id": scenario.template_id,
        "status": "error",
        "engine": engine_id,
        "model": model,
        "content": "",
        "checks": [],
        "tool_calls": [],
        "usage": {},
        "latency_seconds": 0.0,
        "trace_id": None,
        "error": message,
        "created_at": time.time(),
    }


def create_sample_runs_router() -> APIRouter:
    router = APIRouter(prefix="/v1/sample-runs", tags=["sample-runs"])

    @router.get("")
    def list_sample_runs():
        return {
            "scenarios": list_sample_scenarios(),
            "templates": list_agent_lab_templates(),
        }

    @router.post("/{scenario_id}/execute")
    def execute_sample_run(
        scenario_id: str,
        req: SampleExecuteRequest,
        request: Request,
    ):
        try:
            scenario = _get_scenario(scenario_id)
        except KeyError:
            raise HTTPException(status_code=404, detail="Sample scenario not found")

        templates = {t["id"]: t for t in list_agent_lab_templates()}
        template = templates.get(scenario.template_id)
        if not template:
            raise HTTPException(
                status_code=500,
                detail=f"Template not found for scenario: {scenario.template_id}",
            )

        run_id = f"sample-{uuid.uuid4().hex[:12]}"
        engine, engine_id = _resolve_engine(request, req.engine)
        model = _default_model(request, engine, engine_id, req.model) if engine else ""
        if engine is None:
            result = _error_result(
                run_id,
                scenario,
                engine_id,
                model,
                "No inference engine is configured for this OpenJarvis server.",
            )
            _RUNS[run_id] = result
            return result

        try:
            healthy = engine.health()
        except Exception:
            healthy = False
        if not healthy:
            result = _error_result(
                run_id,
                scenario,
                engine_id,
                model,
                f"{engine_id} is not reachable. Start the local engine and retry.",
            )
            _RUNS[run_id] = result
            return result

        prompt = req.prompt or scenario.prompt
        allowed_tools = (
            req.tools if req.tools is not None else list(scenario.allowed_tools)
        )
        temperature = (
            req.temperature
            if req.temperature is not None
            else float(template.get("temperature", 0.3))
        )
        max_turns = req.max_turns or int(template.get("max_turns", 10))
        max_tokens = max(256, min(2048, max_turns * 160))

        started = time.perf_counter()
        try:
            raw = engine.generate(
                _build_messages(template, prompt),
                model=model,
                temperature=temperature,
                max_tokens=max_tokens,
            )
            latency = time.perf_counter() - started
            content = raw.get("content", "")
            checks = _validate_output(scenario, content)
            status: SampleStatus = (
                "passed" if checks and all(c["passed"] for c in checks) else "failed"
            )
            trace_id = f"sample-trace-{run_id}"
            result = {
                "run_id": run_id,
                "scenario_id": scenario.id,
                "template_id": scenario.template_id,
                "status": status,
                "engine": engine_id,
                "model": raw.get("model", model),
                "content": content,
                "checks": checks,
                "tool_calls": raw.get("tool_calls", []),
                "allowed_tools": allowed_tools,
                "usage": raw.get("usage", {}),
                "latency_seconds": latency,
                "trace_id": trace_id,
                "error": None,
                "created_at": time.time(),
            }
            _save_trace(
                request,
                trace_id=trace_id,
                scenario=scenario,
                prompt=prompt,
                result=result,
            )
        except EngineConnectionError as exc:
            result = _error_result(run_id, scenario, engine_id, model, str(exc))
        except Exception as exc:
            result = _error_result(
                run_id,
                scenario,
                engine_id,
                model,
                f"Sample run failed: {exc}",
            )

        _RUNS[run_id] = result
        return result

    @router.get("/{run_id}")
    def get_sample_run(run_id: str):
        result = _RUNS.get(run_id)
        if not result:
            raise HTTPException(status_code=404, detail="Sample run not found")
        return result

    return router


def create_templates_fallback_router() -> APIRouter:
    router = APIRouter(prefix="/v1/templates", tags=["templates"])

    @router.get("")
    def list_templates():
        return {"templates": list_agent_lab_templates()}

    return router


__all__ = [
    "create_sample_runs_router",
    "create_templates_fallback_router",
    "list_agent_lab_templates",
    "list_sample_scenarios",
]

"""Tests for local Agent Lab sample-run routes."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

fastapi = pytest.importorskip("fastapi")
from fastapi.testclient import TestClient  # noqa: E402

from openjarvis.server.app import create_app  # noqa: E402
from openjarvis.server.sample_runs import (  # noqa: E402
    _default_model,
    list_agent_lab_templates,
    list_sample_scenarios,
)


def _make_engine(content: str = ""):
    engine = MagicMock()
    engine.engine_id = "mock"
    engine.health.return_value = True
    engine.list_models.return_value = ["sample-model"]
    engine.generate.return_value = {
        "content": content
        or (
            "Use local files first, inspect the file, keep the edit focused, "
            "then run pytest. Include future value, next action, verify "
            "uncertain details, and list open questions when web freshness "
            "or current sources matter."
        ),
        "usage": {"prompt_tokens": 10, "completion_tokens": 12, "total_tokens": 22},
        "model": "sample-model",
        "finish_reason": "stop",
    }
    return engine


def _make_client(engine, tmp_path, monkeypatch):
    home = tmp_path / "home"
    (home / ".openjarvis").mkdir(parents=True)
    monkeypatch.setenv("HOME", str(home))
    return TestClient(create_app(engine, "sample-model"))


def test_sample_scenario_registry_references_real_templates():
    templates = {tpl["id"] for tpl in list_agent_lab_templates()}
    scenarios = list_sample_scenarios()

    assert {s["template_id"] for s in scenarios} >= {
        "local-codebase-maintainer",
        "personal-intel-router",
        "local-research-scout",
    }
    assert all(s["template_id"] in templates for s in scenarios)
    assert all(s["validators"] for s in scenarios)


def test_list_sample_runs_endpoint(tmp_path, monkeypatch):
    client = _make_client(_make_engine(), tmp_path, monkeypatch)

    resp = client.get("/v1/sample-runs")

    assert resp.status_code == 200
    body = resp.json()
    assert len(body["scenarios"]) >= 3
    assert any(t["id"] == "local-codebase-maintainer" for t in body["templates"])


def test_templates_fallback_endpoint_includes_agent_lab_templates(
    tmp_path, monkeypatch
):
    client = _make_client(_make_engine(), tmp_path, monkeypatch)

    resp = client.get("/v1/templates")

    assert resp.status_code == 200
    templates = resp.json()["templates"]
    assert any(t["id"] == "personal-intel-router" for t in templates)


def test_execute_sample_run_returns_structured_pass_result(tmp_path, monkeypatch):
    engine = _make_engine()
    client = _make_client(engine, tmp_path, monkeypatch)

    resp = client.post(
        "/v1/sample-runs/local-codebase-maintainer-smoke/execute",
        json={"engine": "current", "model": "sample-model"},
    )

    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "passed"
    assert body["run_id"].startswith("sample-")
    assert body["trace_id"].startswith("sample-trace-")
    assert body["engine"] == "mock"
    assert body["model"] == "sample-model"
    assert body["latency_seconds"] >= 0
    assert all(check["passed"] for check in body["checks"])
    engine.generate.assert_called_once()


def test_execute_sample_run_unreachable_engine_returns_actionable_error(
    tmp_path, monkeypatch
):
    engine = _make_engine()
    engine.health.return_value = False
    client = _make_client(engine, tmp_path, monkeypatch)

    resp = client.post(
        "/v1/sample-runs/local-codebase-maintainer-smoke/execute",
        json={"engine": "current", "model": "sample-model"},
    )

    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "error"
    assert "not reachable" in body["error"]
    engine.generate.assert_not_called()


def test_get_sample_run_result_after_execute(tmp_path, monkeypatch):
    client = _make_client(_make_engine(), tmp_path, monkeypatch)
    created = client.post(
        "/v1/sample-runs/personal-intel-router-smoke/execute",
        json={"engine": "current", "model": "sample-model"},
    ).json()

    resp = client.get(f"/v1/sample-runs/{created['run_id']}")

    assert resp.status_code == 200
    assert resp.json()["run_id"] == created["run_id"]


def test_mlx_sample_model_uses_default_when_requested_model_is_from_ollama():
    engine = _make_engine()
    engine.list_models.return_value = ["mlx-community/Qwen2.5-7B-Instruct-4bit"]

    model = _default_model(
        MagicMock(),
        engine,
        "mlx",
        "qwen3.5:9b",
    )

    assert model == "default_model"


def test_mlx_sample_model_keeps_requested_model_when_mlx_lists_it():
    engine = _make_engine()
    engine.list_models.return_value = ["mlx-community/Qwen2.5-7B-Instruct-4bit"]

    model = _default_model(
        MagicMock(),
        engine,
        "mlx",
        "mlx-community/Qwen2.5-7B-Instruct-4bit",
    )

    assert model == "mlx-community/Qwen2.5-7B-Instruct-4bit"

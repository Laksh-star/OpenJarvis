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


def test_repo_triage_sample_run_returns_real_tool_calls(tmp_path, monkeypatch):
    engine = _make_engine(
        "Observed file evidence from repo search. Implement the smallest fix "
        "by wiring real tool calls into the sample run path and add pytest "
        "coverage plus a frontend test."
    )
    client = _make_client(engine, tmp_path, monkeypatch)

    repo = tmp_path / "repo"
    (repo / "src/openjarvis/server").mkdir(parents=True)
    (repo / "frontend/src/pages").mkdir(parents=True)
    (repo / "frontend/src/lib").mkdir(parents=True)
    (repo / "tests/server").mkdir(parents=True)
    (repo / "pyproject.toml").write_text("[project]\nname = 'sample'\n")
    (repo / "src/openjarvis/server/sample_runs.py").write_text(
        "def execute_sample():\n    return {'allowed_tools': []}\n"
    )
    (repo / "frontend/src/pages/AgentLabPage.tsx").write_text(
        "export function AgentLabPage() { return 'Tool Timeline'; }\n"
    )
    (repo / "frontend/src/lib/api.ts").write_text(
        "export async function executeSampleRun() {\n"
        "  return fetch('/v1/sample-runs');\n"
        "}\n"
    )
    (repo / "tests/server/test_sample_runs.py").write_text(
        "def test_sample_runs():\n    assert True\n"
    )
    monkeypatch.setenv("OPENJARVIS_AGENT_LAB_ALLOW_REPO_PATH", "1")

    resp = client.post(
        "/v1/sample-runs/repo-triage-workbench/execute",
        json={"engine": "current", "model": "sample-model", "repo_path": str(repo)},
    )

    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "passed"
    assert body["repo_path"] == str(repo)
    assert {call["tool"] for call in body["tool_calls"]} >= {
        "repo_list",
        "repo_search",
        "file_read",
    }
    assert any(
        call["arguments"]["path"] == "src/openjarvis/server/sample_runs.py"
        for call in body["tool_calls"]
        if call["tool"] == "file_read"
    )
    engine.generate.assert_called_once()


def test_repo_release_readiness_sample_returns_readiness_report(tmp_path, monkeypatch):
    engine = _make_engine(
        "Release readiness: go/no-go is conditional. Blocker risks include "
        "missing docs and test gaps. Run pytest, ruff, and npm run build before "
        "release."
    )
    client = _make_client(engine, tmp_path, monkeypatch)

    repo = tmp_path / "release-repo"
    (repo / "src/openjarvis/server").mkdir(parents=True)
    (repo / "frontend/src/pages").mkdir(parents=True)
    (repo / "frontend/src/lib").mkdir(parents=True)
    (repo / "frontend").mkdir(exist_ok=True)
    (repo / "tests/server").mkdir(parents=True)
    (repo / "README.md").write_text("# Release Repo\n\nTODO: document release flow.\n")
    (repo / "pyproject.toml").write_text(
        "[project]\nname = 'release-repo'\nversion = '0.1.0'\n"
    )
    (repo / "tsconfig.json").write_text('{"compilerOptions": {}}\n')
    (repo / "frontend/package.json").write_text(
        '{"scripts":{"build":"tsc -b && vite build"}}\n'
    )
    (repo / "src/openjarvis/server/sample_runs.py").write_text(
        "def sample_runs():\n    return []\n"
    )
    (repo / "src/index.ts").write_text(
        'export const metadata = { version: "2.0.0" };\n'
    )
    (repo / "src/worker.ts").write_text(
        'export const workerMetadata = { version: "2.0.0" };\n'
    )
    (repo / "frontend/src/pages/AgentLabPage.tsx").write_text(
        "export function AgentLabPage() { return 'Agent Lab'; }\n"
    )
    (repo / "frontend/src/lib/api.ts").write_text("export const api = {};\n")
    (repo / "tests/server/test_sample_runs.py").write_text(
        "def test_sample_runs():\n    assert True\n"
    )
    monkeypatch.setenv("OPENJARVIS_AGENT_LAB_ALLOW_REPO_PATH", "1")

    resp = client.post(
        "/v1/sample-runs/repo-release-readiness-agent/execute",
        json={"engine": "current", "model": "sample-model", "repo_path": str(repo)},
    )

    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "passed"
    assert {call["tool"] for call in body["tool_calls"]} >= {
        "repo_list",
        "git_status",
        "repo_search",
        "file_read",
    }
    read_paths = {
        call["arguments"]["path"]
        for call in body["tool_calls"]
        if call["tool"] == "file_read"
    }
    assert {
        "README.md",
        "pyproject.toml",
        "tsconfig.json",
        "src/index.ts",
    } <= read_paths
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

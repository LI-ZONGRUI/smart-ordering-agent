import asyncio
from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

import app.main as main_module
from app.agent import AgentResult
from app.config import get_settings
from app.errors import model_request_failed
from app.main import app


@pytest.fixture
def client() -> Iterator[TestClient]:
    original_provider = app.state.agent_runner_provider
    get_settings.cache_clear()
    with TestClient(app) as test_client:
        yield test_client
    app.state.agent_runner_provider = original_provider
    get_settings.cache_clear()


def _override_runner(runner: object) -> None:
    async def dependency() -> object:
        return runner

    app.state.agent_runner_provider = dependency


def test_valid_query_is_trimmed_and_response_is_narrow(client: TestClient) -> None:
    async def runner(query: str) -> AgentResult:
        assert query == "有柠檬茶吗？"
        return AgentResult(query=query, answer="有。", completed=True, trace=({"secret": True},))

    _override_runner(runner)
    response = client.post("/v1/agent/run", json={"query": "  有柠檬茶吗？  "})
    assert response.status_code == 200
    assert response.json() == {
        "errCode": 0,
        "query": "有柠檬茶吗？",
        "answer": "有。",
        "completed": True,
    }
    assert "trace" not in response.text
    assert "messages" not in response.text
    assert "prompt" not in response.text


@pytest.mark.parametrize("query", ["", "   ", 7, None, "字" * 201])
def test_invalid_query_contract(client: TestClient, query: object) -> None:
    response = client.post("/v1/agent/run", json={"query": query})
    assert response.status_code == 400
    assert response.json()["errCode"] == "FRAMEWORK_QUERY_INVALID"


def test_clients_cannot_supply_server_controls(client: TestClient) -> None:
    response = client.post(
        "/v1/agent/run",
        json={"query": "你好", "model": "other", "temperature": 2, "tools": []},
    )
    assert response.status_code == 400
    assert response.json()["errCode"] == "FRAMEWORK_QUERY_INVALID"


def test_missing_config_fails_without_fake_fallback(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    for name in ("DASHSCOPE_API_KEY", "LLM_BASE_URL"):
        monkeypatch.delenv(name, raising=False)
    get_settings.cache_clear()

    response = client.post("/v1/agent/run", json={"query": "你好"})
    assert response.status_code == 503
    assert response.json() == {
        "errCode": "FRAMEWORK_CONFIG_MISSING",
        "errMsg": "模型服务配置不完整",
    }
    assert "DASHSCOPE" not in response.text


def test_configured_production_path_still_never_falls_back_to_fixture(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("DASHSCOPE_API_KEY", "test-placeholder-only")
    monkeypatch.setenv("LLM_BASE_URL", "https://example.test/compatible-mode/v1")
    monkeypatch.setenv("FRAMEWORK_AGENT_LLM_MODEL", "qwen3.8-flash")
    get_settings.cache_clear()

    response = client.post("/v1/agent/run", json={"query": "有柠檬茶吗？"})
    assert response.status_code == 502
    assert response.json()["errCode"] == "FRAMEWORK_TOOL_EXECUTION_FAILED"
    assert "fixture" not in response.text
    assert "柠檬茶" not in response.text


def test_timeout_has_stable_safe_mapping(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    async def runner(_query: str) -> AgentResult:
        await asyncio.sleep(0.05)
        raise AssertionError("unreachable")

    _override_runner(runner)
    monkeypatch.setattr(main_module, "AGENT_TIMEOUT_SECONDS", 0.001)
    response = client.post("/v1/agent/run", json={"query": "你好"})
    assert response.status_code == 504
    assert response.json()["errCode"] == "FRAMEWORK_EXECUTION_TIMEOUT"


def test_expected_runner_error_keeps_safe_contract(client: TestClient) -> None:
    async def runner(_query: str) -> AgentResult:
        raise model_request_failed()

    _override_runner(runner)
    response = client.post("/v1/agent/run", json={"query": "你好"})
    assert response.status_code == 502
    assert response.json() == {
        "errCode": "FRAMEWORK_MODEL_REQUEST_FAILED",
        "errMsg": "模型请求未完成",
    }


def test_unknown_runner_error_is_generic(client: TestClient) -> None:
    async def runner(_query: str) -> AgentResult:
        raise RuntimeError("private stack and secret")

    _override_runner(runner)
    response = client.post("/v1/agent/run", json={"query": "你好"})
    assert response.status_code == 500
    assert response.json()["errCode"] == "FRAMEWORK_INTERNAL_ERROR"
    assert "private" not in response.text

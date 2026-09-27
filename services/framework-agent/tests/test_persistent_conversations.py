import hashlib
import inspect
import sqlite3
from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage

import app.conversations as conversations_module
import app.main as main_module
from app.agent import AgentResult
from app.config import get_settings
from app.conversations import (
    ConversationRepository,
    hash_conversation_token,
    project_safe_messages,
    read_safe_history,
)
from app.graph.state import ARCHIVE_MESSAGE_LIMIT, HISTORY_MESSAGE_LIMIT
from app.graph.workflow import build_framework_workflow
from app.main import app
from app.persistence import open_persistent_conversation_store
from tests.test_multiturn import RecordingContextualizer, RecordingGateway, RecordingMenuAgent

FAKE_WRONG_TOKEN = "fake_wrong_conversation_token_0000000000000000"


def _durable_workflow(store: object):
    agent = RecordingMenuAgent()
    gateway = RecordingGateway()
    contextualizer = RecordingContextualizer(
        {
            "多少钱？": "柠檬茶现在多少钱？",
            "它是什么味道？": "柠檬茶是什么味道？",
            "那来两杯。": "把柠檬茶加两杯到购物车",
        }
    )
    workflow = build_framework_workflow(
        agent,
        gateway,
        gateway,
        contextualizer,
        checkpointer=store.saver,
    )
    return workflow, agent, gateway, contextualizer


@pytest.mark.asyncio
async def test_sqlite_checkpoint_survives_reconstructed_store_and_resumes_live_menu(
    tmp_path: Path,
) -> None:
    path = tmp_path / "conversation.sqlite3"
    first_store = await open_persistent_conversation_store(str(path))
    created = await first_store.repository.create()
    first_workflow, _, _, _ = _durable_workflow(first_store)
    await first_workflow.run("有柠檬茶吗？", thread_id=created.thread_id)
    await first_store.close()

    second_store = await open_persistent_conversation_store(str(path))
    try:
        second_workflow, second_agent, _, contextualizer = _durable_workflow(second_store)
        result = await second_workflow.run("多少钱？", thread_id=created.thread_id)
        history = await read_safe_history(second_store.saver, created.thread_id)
    finally:
        await second_store.close()

    assert result.answer == "实时菜单回答：柠檬茶现在多少钱？"
    assert second_agent.queries == ["柠檬茶现在多少钱？"]
    assert "有柠檬茶吗？" in contextualizer.calls[0][1]
    assert [item["role"] for item in history] == ["user", "assistant", "user", "assistant"]


@pytest.mark.asyncio
async def test_reconstructed_store_keeps_threads_isolated(tmp_path: Path) -> None:
    path = tmp_path / "isolated.sqlite3"
    first_store = await open_persistent_conversation_store(str(path))
    first_workflow, _, _, _ = _durable_workflow(first_store)
    await first_workflow.run("有柠檬茶吗？", thread_id="conv_thread_a")
    await first_workflow.run("你好", thread_id="conv_thread_b")
    await first_store.close()

    second_store = await open_persistent_conversation_store(str(path))
    try:
        second_workflow, agent, _, contextualizer = _durable_workflow(second_store)
        await second_workflow.run("多少钱？", thread_id="conv_thread_b")
    finally:
        await second_store.close()
    assert agent.queries == ["多少钱？"]
    assert "有柠檬茶吗？" not in contextualizer.calls[0][1]


@pytest.mark.asyncio
async def test_restart_recovery_routes_rag_and_action_without_write(tmp_path: Path) -> None:
    path = tmp_path / "routes.sqlite3"
    first_store = await open_persistent_conversation_store(str(path))
    first_workflow, _, _, _ = _durable_workflow(first_store)
    await first_workflow.run("有柠檬茶吗？", thread_id="conv_routes")
    await first_store.close()

    second_store = await open_persistent_conversation_store(str(path))
    try:
        workflow, _, gateway, _ = _durable_workflow(second_store)
        await workflow.run("它是什么味道？", thread_id="conv_routes")
        proposal = await workflow.run("那来两杯。", thread_id="conv_routes")
        confirmation = await workflow.run("确认", thread_id="conv_routes")
    finally:
        await second_store.close()
    assert gateway.rag_queries == ["柠檬茶是什么味道？"]
    assert gateway.action_queries == ["把柠檬茶加两杯到购物车"]
    assert proposal.pending_action is not None
    assert proposal.pending_action["requiresConfirmation"] is True
    assert confirmation.pending_action is None
    assert gateway.write_count == 0


@pytest.mark.asyncio
async def test_registry_stores_only_hash_and_uses_constant_time_comparison(tmp_path: Path) -> None:
    path = tmp_path / "tokens.sqlite3"
    store = await open_persistent_conversation_store(str(path))
    try:
        created = await store.repository.create()
        record = await store.repository.get(created.thread_id)
        authorized = await store.repository.authorize(created.thread_id, created.token)
        rejected = await store.repository.authorize(created.thread_id, FAKE_WRONG_TOKEN)
    finally:
        await store.close()

    assert record is not None
    assert authorized is not None
    assert rejected is None
    assert record.token_hash == hash_conversation_token(created.token)
    assert created.token.encode() not in path.read_bytes()
    assert hashlib.sha256(created.token.encode()).digest() in path.read_bytes()
    assert "hmac.compare_digest" in inspect.getsource(ConversationRepository.authorize)


def test_safe_history_projection_excludes_tools_metadata_and_non_text() -> None:
    projected = project_safe_messages(
        [
            HumanMessage(content="用户问题", additional_kwargs={"secret": "hidden"}),
            ToolMessage(content="raw tool", tool_call_id="call-1"),
            AIMessage(content="安全回答", response_metadata={"reasoning": "hidden"}),
            AIMessage(content=[{"type": "text", "text": "not a plain message"}]),
        ]
    )
    assert projected == [
        {"role": "user", "content": "用户问题"},
        {"role": "assistant", "content": "安全回答"},
    ]
    serialized = str(projected)
    for forbidden in ("ToolMessage", "reasoning", "secret", "tool_call_id"):
        assert forbidden not in serialized


@pytest.mark.asyncio
async def test_archive_is_capped_separately_from_model_context(tmp_path: Path) -> None:
    store = await open_persistent_conversation_store(str(tmp_path / "cap.sqlite3"))
    try:
        workflow, _, _, _ = _durable_workflow(store)
        for index in range(55):
            await workflow.run(f"推荐饮品{index}", thread_id="conv_archive_cap")
        snapshot = await workflow.threaded_graph.aget_state(
            {"configurable": {"thread_id": "conv_archive_cap"}}
        )
        history = await read_safe_history(store.saver, "conv_archive_cap")
    finally:
        await store.close()
    assert len(snapshot.values["messages"]) == HISTORY_MESSAGE_LIMIT
    assert len(history) == ARCHIVE_MESSAGE_LIMIT


@pytest.fixture
def durable_client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[TestClient]:
    monkeypatch.setenv("FRAMEWORK_CHECKPOINT_DB_PATH", str(tmp_path / "api.sqlite3"))
    get_settings.cache_clear()
    original_provider = app.state.agent_runner_provider
    with TestClient(app) as client:
        yield client
    app.state.agent_runner_provider = original_provider
    get_settings.cache_clear()


def _create_conversation(client: TestClient) -> tuple[str, str]:
    response = client.post("/v1/conversations")
    assert response.status_code == 200
    body = response.json()
    assert set(body) == {"errCode", "threadId", "conversationToken"}
    return body["threadId"], body["conversationToken"]


def test_create_returns_token_once_and_authorized_run_uses_durable_mode(
    durable_client: TestClient,
) -> None:
    thread_id, token = _create_conversation(durable_client)
    calls: list[tuple[str, str | None, bool]] = []

    async def runner(
        query: str, *, thread_id: str | None = None, durable: bool = False
    ) -> AgentResult:
        calls.append((query, thread_id, durable))
        return AgentResult(query=query, answer="安全回答", completed=True)

    async def provider() -> object:
        return runner

    app.state.agent_runner_provider = provider
    response = durable_client.post(
        "/v1/agent/run",
        headers={"X-Conversation-Token": token},
        json={"query": "你好", "threadId": thread_id},
    )
    assert response.status_code == 200
    assert response.json()["threadId"] == thread_id
    assert "conversationToken" not in response.text
    assert calls == [("你好", thread_id, True)]


@pytest.mark.parametrize("mode", ["missing", "wrong", "other-thread"])
def test_history_access_denial_does_not_reveal_thread_existence(
    durable_client: TestClient, mode: str
) -> None:
    thread_id, token = _create_conversation(durable_client)
    if mode == "missing":
        headers = {}
        target = thread_id
    elif mode == "wrong":
        headers = {"X-Conversation-Token": FAKE_WRONG_TOKEN}
        target = thread_id
    else:
        headers = {"X-Conversation-Token": token}
        target = "conv_unknown_thread"
    response = durable_client.get(f"/v1/conversations/{target}/messages", headers=headers)
    assert response.status_code == 403
    assert response.json() == {
        "errCode": "FRAMEWORK_CONVERSATION_ACCESS_DENIED",
        "errMsg": "无权访问该会话",
    }
    for forbidden in ("hash", "sqlite", "database", "path", "stack"):
        assert forbidden not in response.text.casefold()


def test_correct_token_reads_only_narrow_history_contract(durable_client: TestClient) -> None:
    thread_id, token = _create_conversation(durable_client)
    response = durable_client.get(
        f"/v1/conversations/{thread_id}/messages",
        headers={"X-Conversation-Token": token},
    )
    assert response.status_code == 200
    assert response.json()["messages"] == []
    assert set(response.json()) == {"errCode", "threadId", "createdAt", "updatedAt", "messages"}
    for forbidden in (
        "checkpoint",
        "resolved_query",
        "route",
        "pendingAction",
        "reasoning",
        "conversationToken",
    ):
        assert forbidden not in response.text


def test_v73a_ephemeral_thread_and_stateless_shapes_remain_unchanged(
    durable_client: TestClient,
) -> None:
    calls: list[tuple[str, str | None]] = []

    async def runner(query: str, *, thread_id: str | None = None) -> AgentResult:
        calls.append((query, thread_id))
        return AgentResult(query=query, answer="兼容回答", completed=True)

    async def provider() -> object:
        return runner

    app.state.agent_runner_provider = provider
    no_thread = durable_client.post("/v1/agent/run", json={"query": "你好"})
    ephemeral = durable_client.post(
        "/v1/agent/run", json={"query": "你好", "threadId": "chat_legacy_01"}
    )
    assert no_thread.status_code == 200
    assert "threadId" not in no_thread.json()
    assert ephemeral.status_code == 200
    assert ephemeral.json()["threadId"] == "chat_legacy_01"
    assert calls == [("你好", None), ("你好", "chat_legacy_01")]


def test_token_without_thread_is_rejected_and_no_list_or_transaction_authority(
    durable_client: TestClient,
) -> None:
    _thread_id, token = _create_conversation(durable_client)
    run = durable_client.post(
        "/v1/agent/run",
        headers={"X-Conversation-Token": token},
        json={"query": "你好"},
    )
    assert run.status_code == 400
    assert run.json()["errCode"] == "FRAMEWORK_CONVERSATION_INVALID"
    assert durable_client.get("/v1/conversations").status_code == 405
    assert durable_client.post("/v1/conversations/confirm").status_code in {404, 405}


def test_persistence_source_has_no_token_logging_or_transaction_capability() -> None:
    source = "\n".join(inspect.getsource(module) for module in (conversations_module, main_module))
    for forbidden in (
        "logger.info(token",
        "print(token",
        "createConfirmedOrder",
        "createOrder",
        "process_payment",
        "execute_pending_action",
    ):
        assert forbidden not in source


def test_schema_is_idempotent_and_plaintext_token_is_absent(tmp_path: Path) -> None:
    path = tmp_path / "schema.sqlite3"

    async def create_twice() -> tuple[str, str]:
        first = await open_persistent_conversation_store(str(path))
        created = await first.repository.create()
        await first.close()
        second = await open_persistent_conversation_store(str(path))
        await second.close()
        return created.thread_id, created.token

    import asyncio

    thread_id, token = asyncio.run(create_twice())
    with sqlite3.connect(path) as connection:
        row = connection.execute(
            "SELECT token_hash FROM conversations WHERE thread_id = ?", (thread_id,)
        ).fetchone()
    assert row is not None
    assert row[0] == hash_conversation_token(token)
    assert token not in path.read_text(errors="ignore")

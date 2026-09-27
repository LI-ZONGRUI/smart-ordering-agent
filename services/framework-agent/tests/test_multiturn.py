import inspect
from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, ToolMessage
from langgraph.checkpoint.memory import InMemorySaver

from app.agent import AgentResult
from app.contextualizer import (
    CONTEXTUALIZER_SYSTEM_PROMPT,
    QwenQueryContextualizer,
    needs_contextualization,
)
from app.errors import FrameworkError
from app.graph.nodes import READONLY_ANSWER
from app.graph.state import HISTORY_MESSAGE_LIMIT
from app.graph.workflow import build_framework_workflow
from app.main import app


class RecordingMenuAgent:
    def __init__(self) -> None:
        self.queries: list[str] = []

    async def run(self, query: str, *, include_trace: bool = False) -> AgentResult:
        assert include_trace is False
        self.queries.append(query)
        return AgentResult(query=query, answer=f"实时菜单回答：{query}", completed=True)


class RecordingGateway:
    def __init__(self) -> None:
        self.rag_queries: list[str] = []
        self.action_queries: list[str] = []
        self.write_count = 0

    async def answer_knowledge(self, query: str) -> dict[str, object]:
        self.rag_queries.append(query)
        return {"query": query, "answerable": True, "answer": f"RAG回答：{query}"}

    async def propose_action(self, query: str) -> dict[str, object]:
        self.action_queries.append(query)
        return {
            "query": query,
            "answer": "模型自由文本不应成为执行授权。",
            "completed": True,
            "pendingAction": {
                "type": "add_to_cart",
                "dishId": "dish-4",
                "name": "柠檬茶",
                "quantity": 2,
                "unitPrice": 12,
                "totalPrice": 24,
                "requiresConfirmation": True,
            },
        }


class RecordingContextualizer:
    def __init__(self, resolutions: dict[str, str]) -> None:
        self.resolutions = resolutions
        self.calls: list[tuple[str, tuple[str, ...]]] = []

    async def resolve(self, query: str, history: tuple[BaseMessage, ...]) -> str:
        contents = tuple(str(message.content) for message in history)
        self.calls.append((query, contents))
        return self.resolutions[query] if "柠檬茶" in "\n".join(contents) else query


def make_workflow(
    *,
    checkpointer: InMemorySaver | None = None,
    contextualizer: RecordingContextualizer | None = None,
) -> tuple[object, RecordingMenuAgent, RecordingGateway, RecordingContextualizer]:
    agent = RecordingMenuAgent()
    gateway = RecordingGateway()
    resolver = contextualizer or RecordingContextualizer(
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
        resolver,
        checkpointer=checkpointer or InMemorySaver(),
    )
    return workflow, agent, gateway, resolver


@pytest.mark.asyncio
async def test_same_thread_contextualizes_followup_and_still_reads_live_menu() -> None:
    workflow, agent, gateway, resolver = make_workflow()
    await workflow.run("有柠檬茶吗？", thread_id="chat_case_a")
    result = await workflow.run("多少钱？", thread_id="chat_case_a")

    assert result.query == "多少钱？"
    assert agent.queries == ["有柠檬茶吗？", "柠檬茶现在多少钱？"]
    assert resolver.calls[0][0] == "多少钱？"
    assert "有柠檬茶吗？" in resolver.calls[0][1]
    assert gateway.rag_queries == []


@pytest.mark.asyncio
async def test_knowledge_followup_uses_resolved_query_and_existing_rag() -> None:
    workflow, agent, gateway, _resolver = make_workflow()
    await workflow.run("有柠檬茶吗？", thread_id="chat_case_b")
    result = await workflow.run("它是什么味道？", thread_id="chat_case_b")

    assert result.query == "它是什么味道？"
    assert gateway.rag_queries == ["柠檬茶是什么味道？"]
    assert agent.queries == ["有柠檬茶吗？"]


@pytest.mark.asyncio
async def test_action_followup_returns_proposal_only_without_write() -> None:
    workflow, _agent, gateway, _resolver = make_workflow()
    await workflow.run("有柠檬茶吗？", thread_id="chat_case_c")
    result = await workflow.run("那来两杯。", thread_id="chat_case_c")

    assert gateway.action_queries == ["把柠檬茶加两杯到购物车"]
    assert gateway.write_count == 0
    assert result.pending_action is not None
    assert result.pending_action["requiresConfirmation"] is True


@pytest.mark.asyncio
async def test_confirmation_never_executes_or_reuses_proposal_as_authority() -> None:
    workflow, _agent, gateway, resolver = make_workflow()
    await workflow.run("有柠檬茶吗？", thread_id="chat_case_confirm")
    await workflow.run("那来两杯。", thread_id="chat_case_confirm")
    result = await workflow.run("确认", thread_id="chat_case_confirm")

    assert result.answer == READONLY_ANSWER
    assert result.pending_action is None
    assert gateway.action_queries == ["把柠檬茶加两杯到购物车"]
    assert gateway.write_count == 0
    assert [call[0] for call in resolver.calls] == ["那来两杯。"]


@pytest.mark.asyncio
async def test_different_threads_are_isolated() -> None:
    workflow, agent, _gateway, resolver = make_workflow()
    await workflow.run("有柠檬茶吗？", thread_id="chat_thread_a")
    await workflow.run("你好", thread_id="chat_thread_b")
    result = await workflow.run("多少钱？", thread_id="chat_thread_b")

    assert result.query == "多少钱？"
    assert agent.queries[-1] == "多少钱？"
    second_history = resolver.calls[-1][1]
    assert "你好" in second_history
    assert "有柠檬茶吗？" not in second_history


@pytest.mark.asyncio
async def test_no_thread_requests_are_stateless_and_never_share_history() -> None:
    workflow, agent, _gateway, resolver = make_workflow()
    await workflow.run("有柠檬茶吗？")
    await workflow.run("多少钱？")

    assert agent.queries == ["有柠檬茶吗？", "多少钱？"]
    assert resolver.calls == []


@pytest.mark.asyncio
async def test_process_checkpointer_can_be_reused_by_new_workflow_instances() -> None:
    checkpointer = InMemorySaver()
    first, _agent1, _gateway1, _resolver1 = make_workflow(checkpointer=checkpointer)
    await first.run("有柠檬茶吗？", thread_id="chat_shared_lifecycle")

    second, agent2, _gateway2, resolver2 = make_workflow(checkpointer=checkpointer)
    await second.run("多少钱？", thread_id="chat_shared_lifecycle")
    assert agent2.queries == ["柠檬茶现在多少钱？"]
    assert "有柠檬茶吗？" in resolver2.calls[0][1]


@pytest.mark.asyncio
async def test_history_is_bounded_and_contains_only_user_assistant_messages() -> None:
    workflow, _agent, _gateway, _resolver = make_workflow()
    thread_id = "chat_history_window"
    for index in range(7):
        await workflow.run(f"推荐饮品{index}", thread_id=thread_id)

    snapshot = await workflow.threaded_graph.aget_state({"configurable": {"thread_id": thread_id}})
    messages = snapshot.values["messages"]
    assert len(messages) == HISTORY_MESSAGE_LIMIT
    assert all(isinstance(message, HumanMessage | AIMessage) for message in messages)
    assert not any(isinstance(message, ToolMessage) for message in messages)


def test_contextualization_gate_is_generic_and_never_treats_confirmation_as_execution() -> None:
    assert needs_contextualization("它是什么味道？", has_history=True) is True
    assert needs_contextualization("多少钱？", has_history=True) is True
    assert needs_contextualization("那来两杯。", has_history=True) is True
    assert needs_contextualization("多少钱？", has_history=False) is False
    assert needs_contextualization("确认", has_history=True) is False


class FakeBoundModel:
    def __init__(self, response: BaseMessage | Exception) -> None:
        self.response = response
        self.messages: list[BaseMessage] = []
        self.tools: list[object] = []
        self.bind_kwargs: dict[str, object] = {}

    def bind_tools(self, tools: list[object], **kwargs: object) -> "FakeBoundModel":
        self.tools = tools
        self.bind_kwargs = kwargs
        return self

    async def ainvoke(self, messages: list[BaseMessage]) -> BaseMessage:
        self.messages = messages
        if isinstance(self.response, Exception):
            raise self.response
        return self.response


@pytest.mark.asyncio
async def test_qwen_contextualizer_requires_strict_standalone_query_tool_output() -> None:
    model = FakeBoundModel(
        AIMessage(
            content="",
            tool_calls=[
                {
                    "name": "return_standalone_query",
                    "args": {"standalone_query": "柠檬茶现在多少钱？"},
                    "id": "offline_call",
                    "type": "tool_call",
                }
            ],
        )
    )
    contextualizer = QwenQueryContextualizer(model)  # type: ignore[arg-type]
    result = await contextualizer.resolve(
        "多少钱？",
        (HumanMessage(content="有柠檬茶吗？"), AIMessage(content="有，在售。")),
    )
    assert result == "柠檬茶现在多少钱？"
    assert "Do not answer" in CONTEXTUALIZER_SYSTEM_PROMPT
    assert "Do not call menu" in CONTEXTUALIZER_SYSTEM_PROMPT
    assert "Call return_standalone_query exactly once" in CONTEXTUALIZER_SYSTEM_PROMPT
    assert model.bind_kwargs == {}
    assert all(not isinstance(message, ToolMessage) for message in model.messages)


@pytest.mark.asyncio
async def test_contextualizer_accepts_provider_raw_openai_tool_call_shape() -> None:
    model = FakeBoundModel(
        # model_construct intentionally represents an adapter response where the OpenAI-compatible
        # raw call exists but LangChain's normalized tool_calls field was not populated.
        AIMessage.model_construct(
            content="",
            additional_kwargs={
                "tool_calls": [
                    {
                        "id": "provider_call",
                        "type": "function",
                        "function": {
                            "name": "return_standalone_query",
                            "arguments": '{"standalone_query":"柠檬茶是什么味道？"}',
                        },
                    }
                ]
            },
            tool_calls=[],
            invalid_tool_calls=[],
        )
    )
    contextualizer = QwenQueryContextualizer(model)  # type: ignore[arg-type]

    assert await contextualizer.resolve("它是什么味道？", ()) == "柠檬茶是什么味道？"


@pytest.mark.asyncio
async def test_contextualizer_accepts_only_strict_json_content_fallback() -> None:
    model = FakeBoundModel(AIMessage(content='{"standalone_query":"柠檬茶多少钱？"}'))
    contextualizer = QwenQueryContextualizer(model)  # type: ignore[arg-type]

    assert await contextualizer.resolve("多少钱？", ()) == "柠檬茶多少钱？"


@pytest.mark.parametrize(
    "response",
    [
        AIMessage(content="柠檬茶多少钱？"),
        AIMessage(content='{"answer":"柠檬茶多少钱？"}'),
        AIMessage(content='{"standalone_query":""}'),
        AIMessage(
            content="",
            additional_kwargs={
                "tool_calls": [
                    {
                        "type": "function",
                        "function": {
                            "name": "return_standalone_query",
                            "arguments": "not-json",
                        },
                    }
                ]
            },
        ),
    ],
    ids=("free-text", "unexpected-payload", "empty-query", "malformed-tool-args"),
)
@pytest.mark.asyncio
async def test_contextualizer_rejects_provider_failure_shapes_safely(
    response: AIMessage,
) -> None:
    model = FakeBoundModel(response)
    contextualizer = QwenQueryContextualizer(model)  # type: ignore[arg-type]
    original_query = "多少钱？"

    with pytest.raises(FrameworkError) as caught:
        await contextualizer.resolve(original_query, ())

    assert original_query == "多少钱？"
    assert caught.value.code == "FRAMEWORK_CONTEXT_FAILED"
    assert "not-json" not in caught.value.message
    assert "柠檬茶" not in caught.value.message


@pytest.mark.asyncio
async def test_contextualizer_diagnostics_exposes_only_safe_shape_signals() -> None:
    private_response = "private history secret and raw provider response"
    model = FakeBoundModel(AIMessage(content=private_response))
    contextualizer = QwenQueryContextualizer(model)  # type: ignore[arg-type]

    diagnostics = await contextualizer.diagnose("多少钱？", ())
    serialized = str(diagnostics)

    assert diagnostics == {
        "success": False,
        "failureStage": "response_parse",
        "exceptionType": "content_json_invalid",
        "responseType": "AIMessage",
        "toolCallsExisted": False,
        "normalizedToolCallCount": 0,
        "rawToolCallCount": 0,
        "contentExisted": True,
        "parseSource": None,
        "standaloneQueryParseSucceeded": False,
        "standaloneQuery": None,
    }
    for forbidden in ("private", "secret", "provider response", "reasoning_content"):
        assert forbidden not in serialized


@pytest.mark.asyncio
async def test_contextualizer_request_failure_does_not_leak_exception_or_secret() -> None:
    secret = "sk-private-provider-value"
    model = FakeBoundModel(RuntimeError(f"provider failed with {secret}"))
    contextualizer = QwenQueryContextualizer(model)  # type: ignore[arg-type]

    with pytest.raises(FrameworkError) as caught:
        await contextualizer.resolve("多少钱？", ())
    diagnostics = await contextualizer.diagnose("多少钱？", ())

    assert caught.value.code == "FRAMEWORK_CONTEXT_FAILED"
    assert secret not in caught.value.message
    assert diagnostics["failureStage"] == "model_request"
    assert diagnostics["exceptionType"] == "unexpected_error"
    assert secret not in str(diagnostics)


@pytest.mark.asyncio
async def test_contextualizer_rejects_free_text_without_exposing_it() -> None:
    model = FakeBoundModel(AIMessage(content="private unsupported answer"))
    contextualizer = QwenQueryContextualizer(model)  # type: ignore[arg-type]
    with pytest.raises(FrameworkError) as caught:
        await contextualizer.resolve(
            "多少钱？",
            (HumanMessage(content="有柠檬茶吗？"), AIMessage(content="有，在售。")),
        )
    assert caught.value.code == "FRAMEWORK_CONTEXT_FAILED"
    assert "private" not in caught.value.message


def test_multiturn_sources_have_no_transaction_execution_path() -> None:
    source = "\n".join(
        inspect.getsource(value)
        for value in (
            __import__("app.contextualizer", fromlist=["x"]),
            __import__("app.graph.workflow", fromlist=["x"]),
        )
    )
    for forbidden in (
        "createConfirmedOrder",
        "createOrder",
        "addDish",
        "process_payment",
        "execute_pending_action",
    ):
        assert forbidden not in source


@pytest.fixture
def client() -> Iterator[TestClient]:
    original_provider = app.state.agent_runner_provider
    with TestClient(app) as test_client:
        yield test_client
    app.state.agent_runner_provider = original_provider


def test_thread_id_contract_and_narrow_formal_response(client: TestClient) -> None:
    calls: list[tuple[str, str | None]] = []

    async def runner(query: str, *, thread_id: str | None = None) -> AgentResult:
        calls.append((query, thread_id))
        return AgentResult(query=query, answer="有。", completed=True)

    async def dependency() -> object:
        return runner

    app.state.agent_runner_provider = dependency
    response = client.post(
        "/v1/agent/run",
        json={"query": "有柠檬茶吗？", "threadId": "chat_contract_01"},
    )
    assert response.status_code == 200
    assert response.json() == {
        "errCode": 0,
        "query": "有柠檬茶吗？",
        "answer": "有。",
        "completed": True,
        "threadId": "chat_contract_01",
    }
    assert calls == [("有柠檬茶吗？", "chat_contract_01")]
    for forbidden in ("messages", "ToolMessage", "reasoning", "resolved_query", "checkpoint"):
        assert forbidden not in response.text


@pytest.mark.parametrize(
    "thread_id",
    ["", "short", "has space", "../path-id", "控制字符", "a" * 129, 123],
)
def test_invalid_thread_id_fails_closed(client: TestClient, thread_id: object) -> None:
    response = client.post("/v1/agent/run", json={"query": "你好", "threadId": thread_id})
    assert response.status_code == 400
    assert response.json()["errCode"] == "FRAMEWORK_THREAD_INVALID"


def test_missing_thread_id_preserves_legacy_api_call_shape(client: TestClient) -> None:
    calls: list[str] = []

    async def legacy_runner(query: str) -> AgentResult:
        calls.append(query)
        return AgentResult(query=query, answer="你好。", completed=True)

    async def dependency() -> object:
        return legacy_runner

    app.state.agent_runner_provider = dependency
    response = client.post("/v1/agent/run", json={"query": "你好"})
    assert response.status_code == 200
    assert response.json() == {
        "errCode": 0,
        "query": "你好",
        "answer": "你好。",
        "completed": True,
    }
    assert calls == ["你好"]


def test_thread_id_is_correlation_only_not_identity_or_authority() -> None:
    source = inspect.getsource(__import__("app.main", fromlist=["x"]))
    assert "conversation_checkpointer" in source
    for forbidden in ("clientId = thread", "thread_id == user", "threadId == user"):
        assert forbidden not in source

import importlib
import inspect
from pathlib import Path
from typing import get_type_hints

import pytest
from langchain_core.messages import BaseMessage
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, START
from langgraph.graph.state import CompiledStateGraph

import app.graph.workflow as workflow_module
import app.main as main_module
from app.agent import AgentResult
from app.gateways.action import ActionProposalResult
from app.gateways.rag import KnowledgeAnswer
from app.graph.nodes import READONLY_ANSWER, SMALLTALK_ANSWER
from app.graph.router import classify_request
from app.graph.state import FRAMEWORK_ROUTES, FrameworkGraphState
from app.graph.workflow import FrameworkWorkflow, build_framework_graph, build_framework_workflow


class StubMenuAgent:
    def __init__(self) -> None:
        self.queries: list[str] = []

    async def run(self, query: str, *, include_trace: bool = False) -> AgentResult:
        assert include_trace is False
        self.queries.append(query)
        return AgentResult(
            query=query,
            answer="来自现有 FrameworkAgent 的菜单回答。",
            completed=True,
        )


class StubRagGateway:
    def __init__(self) -> None:
        self.queries: list[str] = []

    async def answer_knowledge(self, query: str) -> KnowledgeAnswer:
        self.queries.append(query)
        return {
            "query": query,
            "answerable": True,
            "answer": "来自现有 evidence-first RAG 的可信回答。",
        }


class StubActionGateway:
    def __init__(self) -> None:
        self.queries: list[str] = []
        self.cart_mutations = 0
        self.order_writes = 0

    async def propose_action(self, query: str) -> ActionProposalResult:
        self.queries.append(query)
        return {
            "query": query,
            "answer": "请回复‘确认’，我再执行：可乐 99 元。",
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


class StubContextualizer:
    def __init__(self, resolutions: dict[str, str] | None = None) -> None:
        self.resolutions = resolutions or {}
        self.calls: list[tuple[str, tuple[str, ...]]] = []

    async def resolve(self, query: str, history: tuple[BaseMessage, ...]) -> str:
        self.calls.append((query, tuple(str(message.content) for message in history)))
        return self.resolutions.get(query, query)


def _workflow(
    agent: StubMenuAgent,
    rag_gateway: StubRagGateway,
    action_gateway: StubActionGateway,
    contextualizer: StubContextualizer | None = None,
    checkpointer: InMemorySaver | None = None,
) -> FrameworkWorkflow:
    return build_framework_workflow(
        agent,
        rag_gateway,
        action_gateway,
        contextualizer or StubContextualizer(),
        checkpointer=checkpointer or InMemorySaver(),
    )


def _edges(graph: CompiledStateGraph) -> set[tuple[str, str, bool]]:
    return {(edge.source, edge.target, edge.conditional) for edge in graph.get_graph().edges}


def test_project_defines_explicit_langgraph_state_and_compiled_graph() -> None:
    source = inspect.getsource(workflow_module)
    for marker in (
        "from langgraph.graph import END, START, StateGraph",
        "StateGraph(FrameworkGraphState)",
        ".add_node(",
        ".add_edge(",
        ".add_conditional_edges(",
        ".compile(checkpointer=checkpointer)",
    ):
        assert marker in source

    hints = get_type_hints(FrameworkGraphState)
    assert set(hints) == {
        "query",
        "resolved_query",
        "messages",
        "archiveMessages",
        "route",
        "answer",
        "completed",
        "pendingAction",
    }
    assert all(
        forbidden not in hints for forbidden in ("api_key", "secret", "system_prompt", "reasoning")
    )
    assert isinstance(
        build_framework_graph(
            StubMenuAgent(), StubRagGateway(), StubActionGateway(), StubContextualizer()
        ),
        CompiledStateGraph,
    )


def test_graph_contains_expected_nodes_conditional_routes_and_end() -> None:
    graph = build_framework_graph(
        StubMenuAgent(), StubRagGateway(), StubActionGateway(), StubContextualizer()
    )
    nodes = set(graph.get_graph().nodes)
    assert nodes == {
        START,
        "contextualize_query",
        "route_request",
        "menu_agent",
        "rag_node",
        "native_action_node",
        "smalltalk_response",
        "readonly_boundary",
        "normalize_result",
        END,
    }
    edges = _edges(graph)
    assert (START, "contextualize_query", False) in edges
    assert ("contextualize_query", "route_request", False) in edges
    assert ("route_request", "menu_agent", True) in edges
    assert ("route_request", "rag_node", True) in edges
    assert ("route_request", "native_action_node", True) in edges
    assert ("route_request", "smalltalk_response", True) in edges
    assert ("route_request", "readonly_boundary", True) in edges
    for branch in (
        "menu_agent",
        "rag_node",
        "native_action_node",
        "smalltalk_response",
        "readonly_boundary",
    ):
        assert (branch, "normalize_result", False) in edges
    assert ("normalize_result", END, False) in edges


@pytest.mark.parametrize("query", ["你好", "您好！", "hello", "Hi!"])
def test_router_recognizes_smalltalk_without_item_specific_rules(query: str) -> None:
    assert classify_request(query) == "smalltalk"


@pytest.mark.parametrize(
    "query",
    ["帮我创建订单", "现在支付", "删除订单", "清空购物车", "直接确认下单"],
)
def test_router_keeps_transaction_requests_read_only(query: str) -> None:
    assert classify_request(query) == "unsupported_action"


@pytest.mark.parametrize(
    "query",
    ["把柠檬茶加入购物车", "柠檬茶加一份", "来两杯柠檬茶", "把饮料放进购物车"],
)
def test_router_recognizes_proposal_only_cart_intents(query: str) -> None:
    assert classify_request(query) == "action_query"


@pytest.mark.parametrize("query", ["有柠檬茶吗？", "多少钱？", "推荐一种饮品", "现在在售吗？"])
def test_router_sends_live_menu_requests_to_menu_agent(query: str) -> None:
    assert classify_request(query) == "menu_query"


@pytest.mark.parametrize(
    "query",
    [
        "宫保鸡丁是什么口味？",
        "鱼香肉丝里面有什么？",
        "有什么比较清爽的菜？",
        "这道菜有什么配料？",
        "哪些菜有辣椒？",
        "这道菜辣吗？",
    ],
)
def test_router_sends_knowledge_questions_to_rag(query: str) -> None:
    assert classify_request(query) == "knowledge_query"


@pytest.mark.asyncio
async def test_menu_route_reuses_existing_agent_and_normalizes_result() -> None:
    agent = StubMenuAgent()
    rag_gateway = StubRagGateway()
    action_gateway = StubActionGateway()
    workflow = _workflow(agent, rag_gateway, action_gateway)
    result = await workflow.run("有柠檬茶吗？")
    assert result == AgentResult(
        query="有柠檬茶吗？",
        answer="来自现有 FrameworkAgent 的菜单回答。",
        completed=True,
    )
    assert agent.queries == ["有柠檬茶吗？"]
    assert rag_gateway.queries == []
    assert action_gateway.queries == []


@pytest.mark.asyncio
async def test_knowledge_route_reuses_existing_rag_and_never_enters_menu_agent() -> None:
    agent = StubMenuAgent()
    rag_gateway = StubRagGateway()
    action_gateway = StubActionGateway()
    result = await _workflow(agent, rag_gateway, action_gateway).run("柠檬茶是什么味道？")
    assert result == AgentResult(
        query="柠檬茶是什么味道？",
        answer="来自现有 evidence-first RAG 的可信回答。",
        completed=True,
    )
    assert rag_gateway.queries == ["柠檬茶是什么味道？"]
    assert agent.queries == []
    assert action_gateway.queries == []


@pytest.mark.asyncio
async def test_smalltalk_uses_no_menu_agent() -> None:
    agent = StubMenuAgent()
    rag_gateway = StubRagGateway()
    action_gateway = StubActionGateway()
    result = await _workflow(agent, rag_gateway, action_gateway).run("你好")
    assert result.answer == SMALLTALK_ANSWER
    assert result.completed is True
    assert agent.queries == []
    assert rag_gateway.queries == []
    assert action_gateway.queries == []


@pytest.mark.asyncio
async def test_action_route_reuses_native_agent_proposal_without_side_effect() -> None:
    agent = StubMenuAgent()
    rag_gateway = StubRagGateway()
    action_gateway = StubActionGateway()
    result = await _workflow(agent, rag_gateway, action_gateway).run("把柠檬茶加两杯到购物车")

    assert result.pending_action == {
        "type": "add_to_cart",
        "dishId": "dish-4",
        "name": "柠檬茶",
        "quantity": 2,
        "unitPrice": 12,
        "totalPrice": 24,
        "requiresConfirmation": True,
    }
    assert result.answer == "\n".join(
        (
            "已为你准备待确认的购物车操作：",
            "- 柠檬茶 × 2",
            "- 单价 12 元",
            "- 合计 24 元",
            "请在点餐界面确认后执行。",
        )
    )
    assert "回复确认" not in result.answer
    assert "我再执行" not in result.answer
    assert "可乐" not in result.answer
    assert "99" not in result.answer
    assert action_gateway.queries == ["把柠檬茶加两杯到购物车"]
    assert action_gateway.cart_mutations == 0
    assert action_gateway.order_writes == 0
    assert agent.queries == []
    assert rag_gateway.queries == []


@pytest.mark.asyncio
async def test_unsupported_action_uses_no_tool_or_write_side_effect() -> None:
    agent = StubMenuAgent()
    rag_gateway = StubRagGateway()
    action_gateway = StubActionGateway()
    result = await _workflow(agent, rag_gateway, action_gateway).run("直接帮我付款")
    assert result.answer == READONLY_ANSWER
    assert result.completed is True
    assert agent.queries == []
    assert rag_gateway.queries == []
    assert action_gateway.queries == []

    graph_sources = "\n".join(
        inspect.getsource(importlib.import_module(name))
        for name in (
            "app.graph.router",
            "app.graph.nodes",
            "app.graph.workflow",
        )
    )
    for forbidden in (
        "importObject",
        "createOrder",
        "createConfirmedOrder",
        "addToCart",
        "gateway.search_menu",
        "gateway.list_available_drinks",
        "gateway.get_dish_detail",
        "embedding",
        "cosine",
        "knowledge_chunks",
    ):
        assert forbidden not in graph_sources


def test_routes_are_closed_and_graph_inspection_script_does_not_auto_run(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    assert FRAMEWORK_ROUTES == {
        "menu_query",
        "knowledge_query",
        "action_query",
        "smalltalk",
        "unsupported_action",
    }
    calls: list[object] = []
    monkeypatch.setattr("builtins.print", lambda value: calls.append(value))
    module = importlib.import_module("scripts.check_graph")
    importlib.reload(module)
    assert calls == []


def test_python_rag_route_does_not_copy_embedding_retrieval_or_knowledge_data() -> None:
    files = (
        "app/gateways/rag.py",
        "app/gateways/unicloud_http.py",
        "app/graph/nodes.py",
        "app/graph/workflow.py",
    )
    source = "\n".join(Path(name).read_text() for name in files)
    for forbidden in (
        "knowledge-source.json",
        "knowledge_chunks",
        "/embeddings",
        "cosineSimilarity",
        "cosine_similarity",
        "topK",
    ):
        assert forbidden not in source


def test_python_action_route_does_not_copy_native_loop_or_transaction_code() -> None:
    files = (
        "app/gateways/action.py",
        "app/gateways/unicloud_http.py",
        "app/graph/nodes.py",
        "app/graph/workflow.py",
    )
    source = "\n".join(Path(name).read_text() for name in files)
    for forbidden in (
        "runAgent",
        "callAgentModel",
        "getToolDefinitions",
        "prepare_add_to_cart",
        "createConfirmedOrder",
        "previewOrder",
        "addDish",
        "orders collection",
    ):
        assert forbidden not in source


@pytest.mark.asyncio
async def test_gateway_closes_if_workflow_construction_fails(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class StubGateway:
        closed = False

        async def aclose(self) -> None:
            self.closed = True

    gateway = StubGateway()
    monkeypatch.setattr(main_module, "require_model_settings", lambda: object())
    monkeypatch.setattr(main_module, "build_menu_gateway", lambda: gateway)
    monkeypatch.setattr(main_module, "build_production_agent", lambda _gateway: object())
    monkeypatch.setattr(
        main_module, "build_production_contextualizer", lambda _settings: StubContextualizer()
    )
    monkeypatch.setattr(main_module, "build_production_semantic_router", lambda _settings: None)

    def fail_workflow(*_args: object, **_kwargs: object) -> FrameworkWorkflow:
        raise RuntimeError("construction failure")

    monkeypatch.setattr(main_module, "build_framework_workflow", fail_workflow)
    with pytest.raises(RuntimeError, match="construction failure"):
        await main_module.get_agent_runner()
    assert gateway.closed is True


@pytest.mark.parametrize("query", ["你好", "直接帮我付款"])
@pytest.mark.asyncio
async def test_non_menu_routes_close_owned_gateway_without_calling_menu_agent(
    query: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class StubGateway:
        close_count = 0

        async def aclose(self) -> None:
            self.close_count += 1

        async def answer_knowledge(self, query: str) -> KnowledgeAnswer:
            raise AssertionError(f"RAG should not run for {query}")

        async def propose_action(self, query: str) -> ActionProposalResult:
            raise AssertionError(f"Native Agent should not run for {query}")

    gateway = StubGateway()
    agent = StubMenuAgent()
    monkeypatch.setattr(main_module, "require_model_settings", lambda: object())
    monkeypatch.setattr(main_module, "build_menu_gateway", lambda: gateway)
    monkeypatch.setattr(main_module, "build_production_agent", lambda _gateway: agent)
    monkeypatch.setattr(
        main_module, "build_production_contextualizer", lambda _settings: StubContextualizer()
    )
    monkeypatch.setattr(main_module, "build_production_semantic_router", lambda _settings: None)

    runner = await main_module.get_agent_runner()
    result = await runner(query)

    assert result.completed is True
    assert agent.queries == []
    assert gateway.close_count == 1


@pytest.mark.asyncio
async def test_main_runner_routes_knowledge_to_same_authenticated_gateway(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class StubGateway(StubRagGateway):
        close_count = 0

        async def aclose(self) -> None:
            self.close_count += 1

        async def propose_action(self, query: str) -> ActionProposalResult:
            raise AssertionError(f"Native Agent should not run for {query}")

    gateway = StubGateway()
    agent = StubMenuAgent()
    monkeypatch.setattr(main_module, "require_model_settings", lambda: object())
    monkeypatch.setattr(main_module, "build_menu_gateway", lambda: gateway)
    monkeypatch.setattr(main_module, "build_production_agent", lambda _gateway: agent)
    monkeypatch.setattr(
        main_module, "build_production_contextualizer", lambda _settings: StubContextualizer()
    )
    monkeypatch.setattr(main_module, "build_production_semantic_router", lambda _settings: None)

    runner = await main_module.get_agent_runner()
    result = await runner("柠檬茶是什么味道？")

    assert result.answer == "来自现有 evidence-first RAG 的可信回答。"
    assert gateway.queries == ["柠檬茶是什么味道？"]
    assert agent.queries == []
    assert gateway.close_count == 1


@pytest.mark.asyncio
async def test_main_runner_routes_action_to_same_authenticated_gateway(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class StubGateway(StubActionGateway):
        close_count = 0

        async def aclose(self) -> None:
            self.close_count += 1

        async def answer_knowledge(self, query: str) -> KnowledgeAnswer:
            raise AssertionError(f"RAG should not run for {query}")

    gateway = StubGateway()
    agent = StubMenuAgent()
    monkeypatch.setattr(main_module, "require_model_settings", lambda: object())
    monkeypatch.setattr(main_module, "build_menu_gateway", lambda: gateway)
    monkeypatch.setattr(main_module, "build_production_agent", lambda _gateway: agent)
    monkeypatch.setattr(
        main_module, "build_production_contextualizer", lambda _settings: StubContextualizer()
    )
    monkeypatch.setattr(main_module, "build_production_semantic_router", lambda _settings: None)

    runner = await main_module.get_agent_runner()
    result = await runner("把柠檬茶加两杯到购物车")

    assert result.pending_action is not None
    assert result.pending_action["requiresConfirmation"] is True
    assert gateway.queries == ["把柠檬茶加两杯到购物车"]
    assert gateway.cart_mutations == 0
    assert gateway.order_writes == 0
    assert agent.queries == []
    assert gateway.close_count == 1

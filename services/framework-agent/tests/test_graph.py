import importlib
import inspect
from typing import get_type_hints

import pytest
from langgraph.graph import END, START
from langgraph.graph.state import CompiledStateGraph

import app.graph.workflow as workflow_module
import app.main as main_module
from app.agent import AgentResult
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
        ".compile()",
    ):
        assert marker in source

    hints = get_type_hints(FrameworkGraphState)
    assert set(hints) == {"query", "route", "answer", "completed"}
    assert all(
        forbidden not in hints
        for forbidden in ("api_key", "secret", "messages", "system_prompt", "reasoning")
    )
    assert isinstance(build_framework_graph(StubMenuAgent()), CompiledStateGraph)


def test_graph_contains_expected_nodes_conditional_routes_and_end() -> None:
    graph = build_framework_graph(StubMenuAgent())
    nodes = set(graph.get_graph().nodes)
    assert nodes == {
        START,
        "route_request",
        "menu_agent",
        "smalltalk_response",
        "readonly_boundary",
        "normalize_result",
        END,
    }
    edges = _edges(graph)
    assert (START, "route_request", False) in edges
    assert ("route_request", "menu_agent", True) in edges
    assert ("route_request", "smalltalk_response", True) in edges
    assert ("route_request", "readonly_boundary", True) in edges
    for branch in ("menu_agent", "smalltalk_response", "readonly_boundary"):
        assert (branch, "normalize_result", False) in edges
    assert ("normalize_result", END, False) in edges


@pytest.mark.parametrize("query", ["你好", "您好！", "hello", "Hi!"])
def test_router_recognizes_smalltalk_without_item_specific_rules(query: str) -> None:
    assert classify_request(query) == "smalltalk"


@pytest.mark.parametrize(
    "query",
    ["把柠檬茶加入购物车", "帮我创建订单", "现在支付", "删除订单", "清空购物车"],
)
def test_router_keeps_transaction_requests_read_only(query: str) -> None:
    assert classify_request(query) == "unsupported_action"


@pytest.mark.parametrize("query", ["有柠檬茶吗？", "有什么比较清爽的？", "推荐一种饮品"])
def test_router_sends_other_requests_to_menu_agent(query: str) -> None:
    assert classify_request(query) == "menu_query"


@pytest.mark.asyncio
async def test_menu_route_reuses_existing_agent_and_normalizes_result() -> None:
    agent = StubMenuAgent()
    workflow = build_framework_workflow(agent)
    result = await workflow.run("有柠檬茶吗？")
    assert result == AgentResult(
        query="有柠檬茶吗？",
        answer="来自现有 FrameworkAgent 的菜单回答。",
        completed=True,
    )
    assert agent.queries == ["有柠檬茶吗？"]


@pytest.mark.asyncio
async def test_smalltalk_uses_no_menu_agent() -> None:
    agent = StubMenuAgent()
    result = await build_framework_workflow(agent).run("你好")
    assert result.answer == SMALLTALK_ANSWER
    assert result.completed is True
    assert agent.queries == []


@pytest.mark.asyncio
async def test_unsupported_action_uses_no_tool_or_write_side_effect() -> None:
    agent = StubMenuAgent()
    result = await build_framework_workflow(agent).run("把柠檬茶加入购物车")
    assert result.answer == READONLY_ANSWER
    assert result.completed is True
    assert agent.queries == []

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
        "addToCart",
        "gateway.search_menu",
        "gateway.list_available_drinks",
        "gateway.get_dish_detail",
    ):
        assert forbidden not in graph_sources


def test_routes_are_closed_and_graph_inspection_script_does_not_auto_run(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    assert FRAMEWORK_ROUTES == {"menu_query", "smalltalk", "unsupported_action"}
    calls: list[object] = []
    monkeypatch.setattr("builtins.print", lambda value: calls.append(value))
    module = importlib.import_module("scripts.check_graph")
    importlib.reload(module)
    assert calls == []


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

    def fail_workflow(_agent: object) -> FrameworkWorkflow:
        raise RuntimeError("construction failure")

    monkeypatch.setattr(main_module, "build_framework_workflow", fail_workflow)
    with pytest.raises(RuntimeError, match="construction failure"):
        await main_module.get_agent_runner()
    assert gateway.closed is True


@pytest.mark.parametrize("query", ["你好", "把柠檬茶加入购物车"])
@pytest.mark.asyncio
async def test_non_menu_routes_close_owned_gateway_without_calling_menu_agent(
    query: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class StubGateway:
        close_count = 0

        async def aclose(self) -> None:
            self.close_count += 1

    gateway = StubGateway()
    agent = StubMenuAgent()
    monkeypatch.setattr(main_module, "require_model_settings", lambda: object())
    monkeypatch.setattr(main_module, "build_menu_gateway", lambda: gateway)
    monkeypatch.setattr(main_module, "build_production_agent", lambda _gateway: agent)

    runner = await main_module.get_agent_runner()
    result = await runner(query)

    assert result.completed is True
    assert agent.queries == []
    assert gateway.close_count == 1

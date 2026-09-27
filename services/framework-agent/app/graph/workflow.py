"""Explicit LangGraph StateGraph that routes top-level Framework Agent requests."""

from dataclasses import dataclass

from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph

from app.agent import AgentResult
from app.graph.nodes import (
    MenuAgentRunner,
    build_menu_agent_node,
    normalize_result,
    readonly_boundary,
    smalltalk_response,
)
from app.graph.router import route_request, select_route
from app.graph.state import FrameworkGraphState


def build_framework_graph(agent: MenuAgentRunner) -> CompiledStateGraph:
    """Compile the project-owned conditional graph around the existing LangChain Agent."""

    builder = StateGraph(FrameworkGraphState)
    builder.add_node("route_request", route_request)
    builder.add_node("menu_agent", build_menu_agent_node(agent))
    builder.add_node("smalltalk_response", smalltalk_response)
    builder.add_node("readonly_boundary", readonly_boundary)
    builder.add_node("normalize_result", normalize_result)

    builder.add_edge(START, "route_request")
    builder.add_conditional_edges(
        "route_request",
        select_route,
        {
            "menu_query": "menu_agent",
            "smalltalk": "smalltalk_response",
            "unsupported_action": "readonly_boundary",
        },
    )
    for branch in ("menu_agent", "smalltalk_response", "readonly_boundary"):
        builder.add_edge(branch, "normalize_result")
    builder.add_edge("normalize_result", END)
    return builder.compile()


@dataclass(slots=True)
class FrameworkWorkflow:
    graph: CompiledStateGraph

    async def run(self, query: str) -> AgentResult:
        state = await self.graph.ainvoke({"query": query})
        return AgentResult(
            query=query,
            answer=state["answer"],
            completed=state["completed"],
        )


def build_framework_workflow(agent: MenuAgentRunner) -> FrameworkWorkflow:
    return FrameworkWorkflow(graph=build_framework_graph(agent))

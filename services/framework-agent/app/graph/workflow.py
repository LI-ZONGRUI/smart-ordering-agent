"""Explicit LangGraph StateGraph that routes top-level Framework Agent requests."""

from dataclasses import dataclass

from langchain_core.messages import HumanMessage
from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph

from app.agent import AgentResult
from app.contextualizer import QueryContextualizer
from app.gateways.action import ActionProposalGateway
from app.gateways.rag import RagGateway
from app.graph.nodes import (
    MenuAgentRunner,
    build_contextualize_query_node,
    build_menu_agent_node,
    build_native_action_node,
    build_rag_node,
    normalize_result,
    readonly_boundary,
    smalltalk_response,
)
from app.graph.router import route_request, select_route
from app.graph.state import FrameworkGraphState


def build_framework_graph(
    agent: MenuAgentRunner,
    rag_gateway: RagGateway,
    action_gateway: ActionProposalGateway,
    contextualizer: QueryContextualizer,
    *,
    checkpointer: BaseCheckpointSaver | None = None,
) -> CompiledStateGraph:
    """Compile the project-owned conditional graph around the existing LangChain Agent."""

    builder = StateGraph(FrameworkGraphState)
    builder.add_node("contextualize_query", build_contextualize_query_node(contextualizer))
    builder.add_node("route_request", route_request)
    builder.add_node("menu_agent", build_menu_agent_node(agent))
    builder.add_node("rag_node", build_rag_node(rag_gateway))
    builder.add_node("native_action_node", build_native_action_node(action_gateway))
    builder.add_node("smalltalk_response", smalltalk_response)
    builder.add_node("readonly_boundary", readonly_boundary)
    builder.add_node("normalize_result", normalize_result)

    builder.add_edge(START, "contextualize_query")
    builder.add_edge("contextualize_query", "route_request")
    builder.add_conditional_edges(
        "route_request",
        select_route,
        {
            "menu_query": "menu_agent",
            "knowledge_query": "rag_node",
            "action_query": "native_action_node",
            "smalltalk": "smalltalk_response",
            "unsupported_action": "readonly_boundary",
        },
    )
    for branch in (
        "menu_agent",
        "rag_node",
        "native_action_node",
        "smalltalk_response",
        "readonly_boundary",
    ):
        builder.add_edge(branch, "normalize_result")
    builder.add_edge("normalize_result", END)
    return builder.compile(checkpointer=checkpointer)


@dataclass(slots=True)
class FrameworkWorkflow:
    graph: CompiledStateGraph
    threaded_graph: CompiledStateGraph

    async def run(self, query: str, *, thread_id: str | None = None) -> AgentResult:
        human_message = HumanMessage(content=query)
        inputs = {
            "query": query,
            "messages": [human_message],
            "archiveMessages": [human_message],
        }
        if thread_id is None:
            state = await self.graph.ainvoke(inputs)
        else:
            state = await self.threaded_graph.ainvoke(
                inputs,
                config={"configurable": {"thread_id": thread_id}},
            )
        return AgentResult(
            query=query,
            answer=state["answer"],
            completed=state["completed"],
            pending_action=state.get("pendingAction"),
        )


def build_framework_workflow(
    agent: MenuAgentRunner,
    rag_gateway: RagGateway,
    action_gateway: ActionProposalGateway,
    contextualizer: QueryContextualizer,
    *,
    checkpointer: BaseCheckpointSaver,
) -> FrameworkWorkflow:
    return FrameworkWorkflow(
        graph=build_framework_graph(agent, rag_gateway, action_gateway, contextualizer),
        threaded_graph=build_framework_graph(
            agent,
            rag_gateway,
            action_gateway,
            contextualizer,
            checkpointer=checkpointer,
        ),
    )

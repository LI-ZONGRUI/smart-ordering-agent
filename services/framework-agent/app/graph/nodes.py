"""Nodes for the explicit top-level Framework Agent graph."""

from collections.abc import Awaitable, Callable
from typing import Protocol

from app.agent import AgentResult
from app.errors import internal_error
from app.graph.state import FRAMEWORK_ROUTES, FrameworkGraphState

GraphNode = Callable[[FrameworkGraphState], Awaitable[dict[str, object]]]

SMALLTALK_ANSWER = "你好，我可以帮你查询当前菜单中的菜品、价格和在售状态。"
READONLY_ANSWER = "当前助手仅支持菜单查询，不能修改购物车、创建订单或进行支付。"


class MenuAgentRunner(Protocol):
    async def run(self, query: str, *, include_trace: bool = False) -> AgentResult: ...


def build_menu_agent_node(agent: MenuAgentRunner) -> GraphNode:
    """Delegate menu reasoning to the accepted LangChain Agent without bypassing its Tools."""

    async def menu_agent(state: FrameworkGraphState) -> dict[str, object]:
        result: AgentResult = await agent.run(state["query"])
        return {"answer": result.answer, "completed": result.completed}

    return menu_agent


async def smalltalk_response(_state: FrameworkGraphState) -> dict[str, object]:
    return {"answer": SMALLTALK_ANSWER, "completed": True}


async def readonly_boundary(_state: FrameworkGraphState) -> dict[str, object]:
    return {"answer": READONLY_ANSWER, "completed": True}


def normalize_result(state: FrameworkGraphState) -> dict[str, object]:
    answer = state.get("answer")
    completed = state.get("completed")
    route = state.get("route")
    if (
        not isinstance(answer, str)
        or not answer.strip()
        or type(completed) is not bool
        or route not in FRAMEWORK_ROUTES
    ):
        raise internal_error()
    return {"answer": answer.strip(), "completed": completed}

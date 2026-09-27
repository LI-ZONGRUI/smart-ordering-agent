"""Nodes for the explicit top-level Framework Agent graph."""

from collections.abc import Awaitable, Callable
from typing import Protocol

from app.agent import AgentResult
from app.errors import internal_error
from app.gateways.action import ActionProposalGateway, PendingAction
from app.gateways.rag import RagGateway
from app.graph.state import FRAMEWORK_ROUTES, FrameworkGraphState

GraphNode = Callable[[FrameworkGraphState], Awaitable[dict[str, object]]]

SMALLTALK_ANSWER = "你好，我可以帮你查询当前菜单中的菜品、价格和在售状态。"
READONLY_ANSWER = "".join(
    ("当前助手可以查询菜单并准备待确认的购物车操作，", "但不能直接创建订单、支付或执行其他写操作。")
)


class MenuAgentRunner(Protocol):
    async def run(self, query: str, *, include_trace: bool = False) -> AgentResult: ...


def render_pending_action(action: PendingAction) -> str:
    """Render only validated proposal facts without promising a future chat turn."""

    unit_price = f"{action['unitPrice']:g}"
    total_price = f"{action['totalPrice']:g}"
    return "\n".join(
        (
            "已为你准备待确认的购物车操作：",
            f"- {action['name']} × {action['quantity']}",
            f"- 单价 {unit_price} 元",
            f"- 合计 {total_price} 元",
            "请在点餐界面确认后执行。",
        )
    )


def build_menu_agent_node(agent: MenuAgentRunner) -> GraphNode:
    """Delegate menu reasoning to the accepted LangChain Agent without bypassing its Tools."""

    async def menu_agent(state: FrameworkGraphState) -> dict[str, object]:
        result: AgentResult = await agent.run(state["query"])
        return {"answer": result.answer, "completed": result.completed}

    return menu_agent


def build_rag_node(gateway: RagGateway) -> GraphNode:
    """Delegate knowledge questions to the existing evidence-first uniCloud RAG."""

    async def rag_node(state: FrameworkGraphState) -> dict[str, object]:
        result = await gateway.answer_knowledge(state["query"])
        return {"answer": result["answer"], "completed": True}

    return rag_node


def build_native_action_node(gateway: ActionProposalGateway) -> GraphNode:
    """Delegate safe proposals to the Native Agent; never execute the proposed action."""

    async def native_action_node(state: FrameworkGraphState) -> dict[str, object]:
        result = await gateway.propose_action(state["query"])
        pending_action = result["pendingAction"]
        output: dict[str, object] = {
            # Native Agent的自由文本仅用于无提案结果；合法提案由服务器确定性渲染，
            # 避免承诺尚未实现的多轮“回复确认后执行”能力。
            "answer": (
                render_pending_action(pending_action)
                if pending_action is not None
                else result["answer"]
            ),
            "completed": result["completed"],
        }
        if pending_action is not None:
            output["pendingAction"] = pending_action
        return output

    return native_action_node


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
    result: dict[str, object] = {"answer": answer.strip(), "completed": completed}
    pending_action = state.get("pendingAction")
    if pending_action is not None:
        result["pendingAction"] = pending_action
    return result

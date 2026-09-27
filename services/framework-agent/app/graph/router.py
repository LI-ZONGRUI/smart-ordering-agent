"""Small deterministic router for the first explicit LangGraph foundation."""

import re
from typing import cast

from app.errors import internal_error
from app.graph.state import FRAMEWORK_ROUTES, FrameworkGraphState, FrameworkRoute

_SMALLTALK = re.compile(r"^(?:你好|您好|嗨|哈[啰喽]|hello|hi)[!！。,.，\s]*$", re.IGNORECASE)
_UNSUPPORTED_ACTION_MARKERS = (
    "下单",
    "订单",
    "支付",
    "付款",
    "结账",
    "结算",
    "退款",
    "确认购买",
    "清空购物车",
    "删除购物车",
    "移出购物车",
    "查看购物车",
)
_ACTION_MARKERS = ("加入购物车", "加到购物车", "放进购物车", "加购")
_ACTION_QUANTITY = re.compile(
    r"(?:加|来)\s*(?:一|两|二|三|四|五|六|七|八|九|十|\d+)\s*(?:份|杯|个)"
)
_CONFIRMATION_ONLY = re.compile(r"^(?:确认|确定|好的?确认|就这样)[!！。,.，\s]*$")
_KNOWLEDGE_MARKERS = (
    "口味",
    "味道",
    "配料",
    "食材",
    "菜品描述",
    "清爽",
    "酸甜",
    "爽脆",
    "辣",
    "里面有什么",
)


def classify_request(query: str) -> FrameworkRoute:
    """Route broad request classes without calling a model or encoding menu item names."""

    normalized = query.strip()
    if _SMALLTALK.fullmatch(normalized):
        return "smalltalk"
    if _CONFIRMATION_ONLY.fullmatch(normalized):
        return "unsupported_action"
    if any(marker in normalized for marker in _UNSUPPORTED_ACTION_MARKERS):
        return "unsupported_action"
    if any(marker in normalized for marker in _ACTION_MARKERS) or _ACTION_QUANTITY.search(
        normalized
    ):
        return "action_query"
    if any(marker in normalized for marker in _KNOWLEDGE_MARKERS):
        return "knowledge_query"
    return "menu_query"


def route_request(state: FrameworkGraphState) -> dict[str, FrameworkRoute]:
    return {"route": classify_request(state["resolved_query"])}


def select_route(state: FrameworkGraphState) -> FrameworkRoute:
    route = state.get("route")
    if route not in FRAMEWORK_ROUTES:
        raise internal_error()
    return cast(FrameworkRoute, route)

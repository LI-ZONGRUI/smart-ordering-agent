"""Small deterministic router for the first explicit LangGraph foundation."""

import re
from typing import cast

from app.errors import internal_error
from app.graph.state import FRAMEWORK_ROUTES, FrameworkGraphState, FrameworkRoute

_SMALLTALK = re.compile(r"^(?:你好|您好|嗨|哈[啰喽]|hello|hi)[!！。,.，\s]*$", re.IGNORECASE)
_UNSUPPORTED_ACTION_MARKERS = (
    "购物车",
    "加购",
    "下单",
    "订单",
    "支付",
    "付款",
    "结账",
    "结算",
)


def classify_request(query: str) -> FrameworkRoute:
    """Route broad request classes without calling a model or encoding menu item names."""

    normalized = query.strip()
    if _SMALLTALK.fullmatch(normalized):
        return "smalltalk"
    if any(marker in normalized for marker in _UNSUPPORTED_ACTION_MARKERS):
        return "unsupported_action"
    return "menu_query"


def route_request(state: FrameworkGraphState) -> dict[str, FrameworkRoute]:
    return {"route": classify_request(state["query"])}


def select_route(state: FrameworkGraphState) -> FrameworkRoute:
    route = state.get("route")
    if route not in FRAMEWORK_ROUTES:
        raise internal_error()
    return cast(FrameworkRoute, route)

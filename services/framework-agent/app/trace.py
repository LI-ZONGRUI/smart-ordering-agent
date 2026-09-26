"""Safe observable trace for local framework-agent acceptance only."""

import json
from typing import Any

from langchain_core.messages import AIMessage, ToolMessage

READ_ONLY_TOOL_NAMES = frozenset({"search_menu", "list_available_drinks", "get_dish_detail"})
_ITEM_FIELDS = ("dishId", "name", "price", "status")


def _safe_arguments(tool_name: str, value: object) -> dict[str, object]:
    if not isinstance(value, dict):
        return {}
    if tool_name == "search_menu" and isinstance(value.get("query"), str):
        return {"query": value["query"]}
    if tool_name == "get_dish_detail" and isinstance(value.get("dish_id"), str):
        return {"dish_id": value["dish_id"]}
    return {}


def _decode_tool_content(value: object) -> dict[str, Any] | None:
    if isinstance(value, dict):
        return value
    if not isinstance(value, str):
        return None
    try:
        decoded = json.loads(value)
    except (TypeError, ValueError):
        return None
    return decoded if isinstance(decoded, dict) else None


def _safe_item(value: object) -> dict[str, object] | None:
    if not isinstance(value, dict):
        return None
    result = {key: value[key] for key in _ITEM_FIELDS if key in value}
    return result or None


def _safe_tool_summary(tool_name: str, content: object) -> dict[str, object]:
    data = _decode_tool_content(content)
    if data is None:
        return {}
    if tool_name in {"search_menu", "list_available_drinks"}:
        summary: dict[str, object] = {}
        count = data.get("count")
        if type(count) is int and count >= 0:
            summary["count"] = count
        items = data.get("items")
        if isinstance(items, list):
            safe_items = [item for value in items[:5] if (item := _safe_item(value))]
            summary["items"] = safe_items
        return summary
    if tool_name == "get_dish_detail":
        summary = {}
        found = data.get("found")
        if type(found) is bool:
            summary["found"] = found
        item = _safe_item(data.get("item"))
        if item is not None:
            summary["item"] = item
        return summary
    return {}


def sanitized_trace(messages: list[Any]) -> tuple[dict[str, Any], ...]:
    """Keep only allowlisted Tool calls and minimal public result summaries."""

    trace: list[dict[str, Any]] = []
    for message in messages:
        if isinstance(message, AIMessage):
            for call in message.tool_calls:
                tool_name = call.get("name", "")
                if tool_name not in READ_ONLY_TOOL_NAMES:
                    continue
                trace.append(
                    {
                        "type": "tool_call",
                        "toolName": tool_name,
                        "arguments": _safe_arguments(tool_name, call.get("args")),
                    }
                )
        elif isinstance(message, ToolMessage):
            tool_name = message.name or ""
            if tool_name not in READ_ONLY_TOOL_NAMES:
                continue
            trace.append(
                {
                    "type": "tool_result",
                    "toolName": tool_name,
                    "summary": _safe_tool_summary(tool_name, message.content),
                }
            )
    return tuple(trace)

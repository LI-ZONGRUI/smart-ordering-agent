import hashlib
import hmac
import json
from typing import Any

import httpx
import pytest
from langchain_core.messages import AIMessage, ToolMessage

from app.agent import FrameworkAgent
from app.gateways.unicloud_http import UniCloudHttpMenuGateway
from tests.fakes.chat_model import ScriptedToolCallingChatModel, tool_call

URL = "https://gateway.example.test/framework-gateway"
SECRET = "test-only-framework-secret-at-least-32-chars"
TIMESTAMP = 1_700_000_000


def _expected_signature(body: bytes, nonce: str) -> str:
    body_hash = hashlib.sha256(body).hexdigest()
    canonical = f"v1\nPOST\n/framework-gateway\n{TIMESTAMP}\n{nonce}\n{body_hash}"
    return hmac.new(SECRET.encode(), canonical.encode(), hashlib.sha256).hexdigest()


@pytest.mark.asyncio
async def test_case_a_real_langchain_tools_http_adapter_and_two_signed_requests() -> None:
    requests: list[dict[str, Any]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        payload = json.loads(request.content)
        nonce = request.headers["X-Framework-Nonce"]
        assert request.headers["X-Framework-Signature"] == _expected_signature(
            request.content, nonce
        )
        requests.append({"payload": payload, "nonce": nonce})
        operation = payload["operation"]
        if operation == "search_menu":
            data = {"tool": operation, "query": "可乐", "count": 0, "items": []}
        else:
            data = {
                "tool": operation,
                "count": 1,
                "items": [
                    {
                        "dishId": "dish-4",
                        "name": "柠檬茶",
                        "categoryId": "drink",
                        "price": 12,
                        "status": "on_sale",
                        "spicyLevel": 0,
                    }
                ],
            }
        return httpx.Response(200, json={"errCode": 0, "operation": operation, "data": data})

    observed_zero_result = False

    def second_decision(messages: list[Any]) -> AIMessage:
        nonlocal observed_zero_result
        tool_messages = [item for item in messages if isinstance(item, ToolMessage)]
        assert len(tool_messages) == 1
        assert tool_messages[0].name == "search_menu"
        assert '"count": 0' in str(tool_messages[0].content)
        observed_zero_result = True
        return tool_call("list_available_drinks", {}, "call-drinks")

    def final_decision(messages: list[Any]) -> AIMessage:
        tool_messages = [item for item in messages if isinstance(item, ToolMessage)]
        assert [item.name for item in tool_messages] == [
            "search_menu",
            "list_available_drinks",
        ]
        assert "柠檬茶" in str(tool_messages[-1].content)
        return AIMessage(content="没有搜索到可乐；当前可选饮料是柠檬茶，价格 12 元。")

    nonces = iter(["http_search_nonce_1234", "http_drinks_nonce_123"])
    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    gateway = UniCloudHttpMenuGateway(
        url=URL,
        secret=SECRET,
        client=client,
        clock=lambda: TIMESTAMP,
        nonce_factory=lambda: next(nonces),
    )
    model = ScriptedToolCallingChatModel(
        script=[
            tool_call("search_menu", {"query": "可乐"}, "call-search"),
            second_decision,
            final_decision,
        ]
    )
    try:
        result = await FrameworkAgent(model, gateway).run(
            "有可乐吗？没有的话推荐点别的喝的。", include_trace=True
        )
    finally:
        await client.aclose()

    assert observed_zero_result is True
    assert [item["payload"]["operation"] for item in requests] == [
        "search_menu",
        "list_available_drinks",
    ]
    assert requests[0]["nonce"] != requests[1]["nonce"]
    assert [entry["toolName"] for entry in result.trace if entry["type"] == "tool_call"] == [
        "search_menu",
        "list_available_drinks",
    ]
    assert "柠檬茶" in result.answer


def test_python_tools_remain_http_agnostic_and_have_no_hardcoded_fallback() -> None:
    source = open("app/tools/menu.py", encoding="utf-8").read()
    assert "httpx" not in source
    assert "HMAC" not in source
    assert "FRAMEWORK_GATEWAY_SECRET" not in source
    assert "可乐" not in source
    assert "list_available_drinks" in source

from typing import Any

import httpx
import pytest
from langchain_core.messages import AIMessage, ToolMessage

from app.agent import AGENT_RECURSION_LIMIT, FrameworkAgent
from app.errors import FrameworkError
from app.gateways.base import DishDetailResult, MenuGateway, MenuSearchResult
from app.gateways.memory import InMemoryMenuGateway
from tests.fakes.chat_model import ScriptedToolCallingChatModel, tool_call


def _final(text: str) -> AIMessage:
    return AIMessage(content=text)


@pytest.mark.asyncio
async def test_case_a_real_langchain_loop_calls_search_then_drinks() -> None:
    observed_zero_result = False

    def second_model_decision(messages: list[Any]) -> AIMessage:
        nonlocal observed_zero_result
        tool_messages = [message for message in messages if isinstance(message, ToolMessage)]
        assert len(tool_messages) == 1
        assert tool_messages[0].name == "search_menu"
        assert '"count": 0' in str(tool_messages[0].content)
        observed_zero_result = True
        return tool_call("list_available_drinks", {}, "call-drinks")

    def final_model_decision(messages: list[Any]) -> AIMessage:
        tool_messages = [message for message in messages if isinstance(message, ToolMessage)]
        assert [message.name for message in tool_messages] == [
            "search_menu",
            "list_available_drinks",
        ]
        assert "柠檬茶" in str(tool_messages[-1].content)
        return _final("没有搜索到可乐；当前可选饮料是柠檬茶，价格 12 元。")

    model = ScriptedToolCallingChatModel(
        script=[
            tool_call("search_menu", {"query": "可乐"}, "call-search"),
            second_model_decision,
            final_model_decision,
        ]
    )
    agent = FrameworkAgent(model=model, gateway=InMemoryMenuGateway())

    result = await agent.run("有可乐吗？没有的话推荐点别的喝的。", include_trace=True)

    assert observed_zero_result is True
    assert [entry["toolName"] for entry in result.trace if entry["type"] == "tool_call"] == [
        "search_menu",
        "list_available_drinks",
    ]
    assert "柠檬茶" in result.answer
    assert model.cursor == 3
    assert set(model.bound_tool_names) == {
        "search_menu",
        "list_available_drinks",
        "get_dish_detail",
    }


@pytest.mark.asyncio
async def test_case_b_one_search_then_final_answer() -> None:
    def final_after_search(messages: list[Any]) -> AIMessage:
        tools = [message for message in messages if isinstance(message, ToolMessage)]
        assert len(tools) == 1
        assert tools[0].name == "search_menu"
        return _final("有柠檬茶，当前在售，价格 12 元。")

    model = ScriptedToolCallingChatModel(
        script=[
            tool_call("search_menu", {"query": "柠檬茶"}, "call-search"),
            final_after_search,
        ]
    )
    result = await FrameworkAgent(model, InMemoryMenuGateway()).run(
        "有柠檬茶吗？", include_trace=True
    )
    assert [entry["toolName"] for entry in result.trace if entry["type"] == "tool_call"] == [
        "search_menu"
    ]
    assert result.answer == "有柠檬茶，当前在售，价格 12 元。"


@pytest.mark.asyncio
async def test_case_c_greeting_uses_zero_tools() -> None:
    model = ScriptedToolCallingChatModel(script=[_final("你好，我可以查询菜单信息。")])
    result = await FrameworkAgent(model, InMemoryMenuGateway()).run("你好", include_trace=True)
    assert result.trace == ()
    assert result.answer == "你好，我可以查询菜单信息。"


@pytest.mark.asyncio
async def test_trace_is_opt_in() -> None:
    model = ScriptedToolCallingChatModel(script=[_final("你好")])
    result = await FrameworkAgent(model, InMemoryMenuGateway()).run("你好")
    assert result.trace == ()


@pytest.mark.asyncio
async def test_empty_final_answer_is_rejected() -> None:
    model = ScriptedToolCallingChatModel(script=[_final("   ")])
    with pytest.raises(FrameworkError) as captured:
        await FrameworkAgent(model, InMemoryMenuGateway()).run("你好")
    assert captured.value.code == "FRAMEWORK_MODEL_RESPONSE_INVALID"


@pytest.mark.asyncio
async def test_model_network_failure_is_safely_mapped() -> None:
    def fail(_messages: list[Any]) -> AIMessage:
        request = httpx.Request("POST", "https://example.test")
        raise httpx.ConnectError("contains-network-detail", request=request)

    model = ScriptedToolCallingChatModel(script=[fail])
    with pytest.raises(FrameworkError) as captured:
        await FrameworkAgent(model, InMemoryMenuGateway()).run("你好")
    assert captured.value.code == "FRAMEWORK_MODEL_REQUEST_FAILED"
    assert "detail" not in captured.value.message


@pytest.mark.asyncio
async def test_unknown_model_error_is_safely_mapped() -> None:
    def fail(_messages: list[Any]) -> AIMessage:
        raise RuntimeError("sensitive-internal-detail")

    model = ScriptedToolCallingChatModel(script=[fail])
    with pytest.raises(FrameworkError) as captured:
        await FrameworkAgent(model, InMemoryMenuGateway()).run("你好")
    assert captured.value.code == "FRAMEWORK_INTERNAL_ERROR"
    assert "sensitive" not in captured.value.message


@pytest.mark.asyncio
async def test_recursion_limit_maps_to_stable_error() -> None:
    calls = [tool_call("search_menu", {"query": "可乐"}, f"call-{index}") for index in range(20)]
    model = ScriptedToolCallingChatModel(script=calls)
    with pytest.raises(FrameworkError) as captured:
        await FrameworkAgent(model, InMemoryMenuGateway()).run("继续查")
    assert captured.value.code == "FRAMEWORK_MAX_STEPS_EXCEEDED"
    assert model.cursor < len(calls)


def test_execution_limit_is_finite() -> None:
    assert isinstance(AGENT_RECURSION_LIMIT, int)
    assert 1 < AGENT_RECURSION_LIMIT < 100


class FailingAgentGateway(MenuGateway):
    async def search_menu(self, query: str) -> MenuSearchResult:
        del query
        raise RuntimeError("private-database-detail")

    async def list_available_drinks(self) -> MenuSearchResult:
        raise RuntimeError("private-database-detail")

    async def get_dish_detail(self, dish_id: str) -> DishDetailResult:
        del dish_id
        raise RuntimeError("private-database-detail")


@pytest.mark.asyncio
async def test_tool_failure_crossing_agent_loop_keeps_safe_mapping() -> None:
    model = ScriptedToolCallingChatModel(
        script=[tool_call("search_menu", {"query": "柠檬茶"}, "call-search")]
    )
    with pytest.raises(FrameworkError) as captured:
        await FrameworkAgent(model, FailingAgentGateway()).run("有柠檬茶吗？")
    assert captured.value.code == "FRAMEWORK_TOOL_EXECUTION_FAILED"
    assert "database" not in captured.value.message.lower()

"""Scripted tool-calling model used only by offline tests."""

from collections.abc import Callable, Sequence
from typing import Any

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage, BaseMessage
from langchain_core.outputs import ChatGeneration, ChatResult
from pydantic import ConfigDict, Field


class ScriptedToolCallingChatModel(BaseChatModel):
    """Return model decisions in sequence while preserving the real agent/tool loop."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    # `Any` prevents Pydantic from trying to parse callback fixtures as AIMessage objects.
    script: list[Any] = Field(exclude=True)
    cursor: int = 0
    bound_tool_names: tuple[str, ...] = ()

    @property
    def _llm_type(self) -> str:
        return "scripted-tool-calling-test-model"

    def bind_tools(
        self,
        tools: Sequence[dict[str, Any] | type | Callable[..., Any] | Any],
        *,
        tool_choice: str | None = None,
        **kwargs: Any,
    ) -> "ScriptedToolCallingChatModel":
        del tool_choice, kwargs
        names = []
        for item in tools:
            if isinstance(item, dict):
                names.append(item.get("name", item.get("function", {}).get("name", "")))
            else:
                names.append(getattr(item, "name", getattr(item, "__name__", "")))
        self.bound_tool_names = tuple(names)
        return self

    def _generate(
        self,
        messages: list[BaseMessage],
        stop: list[str] | None = None,
        run_manager: Any = None,
        **kwargs: Any,
    ) -> ChatResult:
        del stop, run_manager, kwargs
        if self.cursor >= len(self.script):
            raise AssertionError("scripted model was called more times than expected")
        step = self.script[self.cursor]
        self.cursor += 1
        message = step(messages) if callable(step) else step
        return ChatResult(generations=[ChatGeneration(message=message)])


def tool_call(name: str, args: dict[str, Any], call_id: str) -> AIMessage:
    return AIMessage(
        content="",
        tool_calls=[{"name": name, "args": args, "id": call_id, "type": "tool_call"}],
    )

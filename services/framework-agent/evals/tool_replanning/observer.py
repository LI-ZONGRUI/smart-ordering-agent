"""Benchmark-only callbacks: preserve actual model decisions, including rejected Tool attempts."""

from __future__ import annotations

import json
import re
from typing import Any
from uuid import UUID

from langchain_core.callbacks import BaseCallbackHandler
from langchain_core.messages import AIMessage, ToolMessage
from langchain_core.outputs import LLMResult

from app.errors import FrameworkError
from evals.tool_replanning.schema import READ_ONLY_TOOLS, validate_summary


class ToolTraceObserver(BaseCallbackHandler):
    """Observe the unchanged Agent graph without storing prompts, raw responses or provider IDs."""

    run_inline = True
    raise_error = True

    def __init__(self) -> None:
        self.events: list[dict[str, Any]] = []
        self.step = 0
        self.invalid = False
        # Only transient correlation; these execution IDs are never exported.
        self._runs: dict[UUID, tuple[int, str]] = {}

    def on_llm_end(self, response: LLMResult, **kwargs: Any) -> None:
        del kwargs
        self.step += 1
        message = getattr(response.generations[0][0], "message", None)
        if not isinstance(message, AIMessage):
            self.invalid = True
            return
        if message.invalid_tool_calls:
            self.invalid = True
        for call in [*message.tool_calls, *message.invalid_tool_calls]:
            name = call.get("name", "")
            if not isinstance(name, str) or not re.fullmatch(r"[a-zA-Z_][a-zA-Z0-9_]{0,63}", name):
                name = "invalid_tool_name"
            # Keep unauthorized attempts visible, but discard their arbitrary arguments.
            keys = {"search_menu": {"query"}, "get_dish_detail": {"dish_id"}}.get(name, set())
            args = call.get("args", {})
            valid = (
                isinstance(args, dict)
                and set(args) == keys
                and all(
                    isinstance(args[key], str) and 1 <= len(args[key].strip()) <= 100
                    for key in keys
                )
            )
            event = {
                "step": self.step,
                "eventType": "assistant_tool_call",
                "toolName": name,
                "arguments": {key: args[key].strip() for key in keys} if valid else {},
            }
            if not valid:
                event["argumentsInvalid"] = True
            self.events.append(event)
        if not message.tool_calls and not message.invalid_tool_calls:
            if not isinstance(message.content, str) or not message.content.strip():
                self.invalid = True
                return
            self.events.append(
                {
                    "step": self.step,
                    "eventType": "assistant_final",
                    "answer": message.content.strip(),
                    "completed": True,
                }
            )

    def on_tool_start(
        self, serialized: dict[str, Any], input_str: str, *, run_id: UUID, **kwargs: Any
    ) -> None:
        del input_str, kwargs
        name = serialized.get("name", "")
        if name in READ_ONLY_TOOLS:
            self._runs[run_id] = (self.step, name)

    def on_tool_end(self, output: Any, *, run_id: UUID, **kwargs: Any) -> None:
        del kwargs
        if run_id not in self._runs:
            return
        step, name = self._runs.pop(run_id)
        content = output.content if isinstance(output, ToolMessage) else output
        try:
            data = json.loads(content) if isinstance(content, str) else content
            result_class = _result_class(name, data)
            validate_summary(name, result_class, data)
        except (ValueError, TypeError):
            result_class, data = "invalid", {}
        self.events.append(
            {
                "step": step,
                "eventType": "tool_result",
                "toolName": name,
                "resultClass": result_class,
                "summary": data,
            }
        )

    def on_tool_error(self, error: BaseException, *, run_id: UUID, **kwargs: Any) -> None:
        del kwargs
        if run_id not in self._runs:
            return
        step, name = self._runs.pop(run_id)
        self.events.append(
            {
                "step": step,
                "eventType": "tool_result",
                "toolName": name,
                "resultClass": "safe_error" if isinstance(error, FrameworkError) else "invalid",
                "summary": {},
            }
        )


def _result_class(name: str, data: Any) -> str:
    if not isinstance(data, dict):
        return "invalid"
    if name == "get_dish_detail":
        return "success" if data.get("found") is True else "missing"
    return "empty" if data.get("count") == 0 else "success"

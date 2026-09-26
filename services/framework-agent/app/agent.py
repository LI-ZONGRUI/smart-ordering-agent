"""LangChain create_agent orchestration with a narrow public result."""

from dataclasses import dataclass
from typing import Any

import httpx
import openai
from langchain.agents import create_agent
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage, ToolMessage

from app.errors import (
    FrameworkError,
    internal_error,
    max_steps_exceeded,
    model_request_failed,
    model_response_invalid,
)
from app.gateways.base import MenuGateway
from app.llm import build_qwen_model
from app.tools.menu import build_menu_tools

SYSTEM_PROMPT = """You are a read-only menu assistant.

Rules:
- Menu facts must come from the registered tools.
- Never invent dishes, prices, or availability.
- Use another read-only tool when the first result is insufficient.
- Do not modify a cart, create an order, process payment, or claim that you did so.
- A narrow search returning zero does not prove that an item is globally unavailable.
- Answer the user's single-turn request briefly using only observable tool facts.
"""

# LangChain create_agent is backed by a graph runtime. This finite recursion limit bounds
# model/tool cycles without adding custom LangGraph nodes, state, edges, or routing.
AGENT_RECURSION_LIMIT = 13


@dataclass(frozen=True, slots=True)
class AgentResult:
    query: str
    answer: str
    completed: bool
    trace: tuple[dict[str, Any], ...] = ()


def _extract_answer(messages: list[Any]) -> str:
    for message in reversed(messages):
        if isinstance(message, AIMessage) and not message.tool_calls:
            if isinstance(message.content, str) and message.content.strip():
                return message.content.strip()
    raise model_response_invalid()


def _sanitized_trace(messages: list[Any]) -> tuple[dict[str, Any], ...]:
    trace: list[dict[str, Any]] = []
    for message in messages:
        if isinstance(message, AIMessage):
            for call in message.tool_calls:
                trace.append(
                    {
                        "type": "tool_call",
                        "toolName": call.get("name", ""),
                        "arguments": call.get("args", {}),
                    }
                )
        elif isinstance(message, ToolMessage):
            trace.append({"type": "tool_result", "toolName": message.name or ""})
    return tuple(trace)


class FrameworkAgent:
    """Small wrapper around the real LangChain agent graph."""

    def __init__(self, model: BaseChatModel, gateway: MenuGateway) -> None:
        self.tools = build_menu_tools(gateway)
        self._graph = create_agent(model=model, tools=self.tools, system_prompt=SYSTEM_PROMPT)

    async def run(self, query: str, *, include_trace: bool = False) -> AgentResult:
        try:
            state = await self._graph.ainvoke(
                {"messages": [{"role": "user", "content": query}]},
                config={"recursion_limit": AGENT_RECURSION_LIMIT},
            )
        except FrameworkError:
            raise
        except (openai.APIError, httpx.HTTPError, ConnectionError, TimeoutError):
            raise model_request_failed() from None
        except Exception as error:
            # LangChain exposes recursion exhaustion from its internal runtime. Avoid importing
            # or programming against LangGraph APIs in this V7.1A foundation.
            if type(error).__name__ == "GraphRecursionError":
                raise max_steps_exceeded() from None
            raise internal_error() from None

        messages = list(state.get("messages", []))
        answer = _extract_answer(messages)
        trace = _sanitized_trace(messages) if include_trace else ()
        return AgentResult(query=query, answer=answer, completed=True, trace=trace)


def build_production_agent(gateway: MenuGateway) -> FrameworkAgent:
    """Build production orchestration with an explicitly supplied real gateway.

    V7.1A deliberately has no production gateway implementation. Callers may not silently
    substitute InMemoryMenuGateway; V7.1B will supply the cross-service adapter.
    """

    return FrameworkAgent(model=build_qwen_model(), gateway=gateway)

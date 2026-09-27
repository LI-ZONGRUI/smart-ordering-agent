"""Narrow conversation contextualization without answering or executing tools."""

import json
import re
from dataclasses import dataclass, replace
from typing import Any, Protocol

import httpx
import openai
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage

from app.config import FrameworkSettings
from app.errors import FrameworkError, context_failed
from app.llm import build_qwen_model

CONTEXTUALIZER_SYSTEM_PROMPT = """You rewrite a context-dependent user message as a standalone
query.

Rules:
- Use only the supplied recent user/assistant conversation to resolve references or omitted
  subjects.
- Call return_standalone_query exactly once with the resolved standalone_query. Do not answer with
  prose.
- Do not answer the query.
- Do not call menu, cart, order, payment, database, Gateway, or other tools.
- Do not add facts, prices, availability, quantities, or dish names unsupported by the conversation.
- A request to confirm must remain a confirmation request; never turn it into transaction execution.
- Keep the result concise and in the user's language.
"""

_CONTEXTUALIZE_TOOL = {
    "type": "function",
    "function": {
        "name": "return_standalone_query",
        "description": "Return only the context-resolved standalone user query.",
        "parameters": {
            "type": "object",
            "properties": {
                "standalone_query": {"type": "string", "minLength": 1, "maxLength": 200}
            },
            "required": ["standalone_query"],
            "additionalProperties": False,
        },
    },
}

_CONTEXT_DEPENDENT = re.compile(
    r"(?:它|这个|那个|这杯|那杯|这份|那份|这道|那道|多少钱|什么味道|还有吗|"
    r"再来|来\s*(?:一|两|二|三|四|五|六|七|八|九|十|\d+)\s*(?:份|杯|个))"
)
_CONFIRMATION_ONLY = re.compile(r"^(?:确认|确定|好的?确认|就这样)[!！。,.，\s]*$")


class QueryContextualizer(Protocol):
    async def resolve(self, query: str, history: tuple[BaseMessage, ...]) -> str: ...


def needs_contextualization(query: str, *, has_history: bool) -> bool:
    """Limit model use to ambiguous follow-ups; confirmations stay non-executable."""

    normalized = query.strip()
    return (
        has_history
        and _CONFIRMATION_ONLY.fullmatch(normalized) is None
        and _CONTEXT_DEPENDENT.search(normalized) is not None
    )


@dataclass(frozen=True, slots=True)
class ContextualizerDiagnostics:
    """Safe response-shape signals for an explicitly run local diagnostic."""

    success: bool = False
    failure_stage: str | None = None
    exception_type: str | None = None
    response_type: str | None = None
    normalized_tool_call_count: int = 0
    raw_tool_call_count: int = 0
    content_existed: bool = False
    parse_source: str | None = None
    standalone_query_parse_succeeded: bool = False
    standalone_query: str | None = None

    def to_safe_dict(self) -> dict[str, object]:
        """Return only controlled diagnostics, never prompts, history, or raw model data."""

        return {
            "success": self.success,
            "failureStage": self.failure_stage,
            "exceptionType": self.exception_type,
            "responseType": self.response_type,
            "toolCallsExisted": bool(self.normalized_tool_call_count or self.raw_tool_call_count),
            "normalizedToolCallCount": self.normalized_tool_call_count,
            "rawToolCallCount": self.raw_tool_call_count,
            "contentExisted": self.content_existed,
            "parseSource": self.parse_source,
            "standaloneQueryParseSucceeded": self.standalone_query_parse_succeeded,
            "standaloneQuery": self.standalone_query,
        }


class _ContextualizerFailure(Exception):
    def __init__(self, diagnostics: ContextualizerDiagnostics) -> None:
        super().__init__(diagnostics.failure_stage)
        self.diagnostics = diagnostics


def _fail(
    diagnostics: ContextualizerDiagnostics,
    *,
    stage: str,
    exception_type: str,
) -> None:
    raise _ContextualizerFailure(
        replace(diagnostics, failure_stage=stage, exception_type=exception_type)
    )


def _response_diagnostics(response: object) -> ContextualizerDiagnostics:
    if not isinstance(response, AIMessage):
        return ContextualizerDiagnostics(response_type="unexpected_message")

    normalized_calls = response.tool_calls if isinstance(response.tool_calls, list) else []
    raw_calls = response.additional_kwargs.get("tool_calls")
    raw_call_count = len(raw_calls) if isinstance(raw_calls, list) else 0
    content = response.content
    content_existed = bool(content.strip()) if isinstance(content, str) else bool(content)
    return ContextualizerDiagnostics(
        response_type="AIMessage",
        normalized_tool_call_count=len(normalized_calls),
        raw_tool_call_count=raw_call_count,
        content_existed=content_existed,
    )


def _validate_standalone_args(
    args: object,
    diagnostics: ContextualizerDiagnostics,
    *,
    parse_source: str,
) -> tuple[str, ContextualizerDiagnostics]:
    if not isinstance(args, dict) or set(args) != {"standalone_query"}:
        _fail(diagnostics, stage="response_parse", exception_type="schema_invalid")
    standalone = args.get("standalone_query")
    if not isinstance(standalone, str):
        _fail(diagnostics, stage="response_parse", exception_type="schema_invalid")
    standalone = standalone.strip()
    if not standalone or len(standalone) > 200:
        _fail(diagnostics, stage="response_parse", exception_type="standalone_query_invalid")
    return standalone, replace(
        diagnostics,
        success=True,
        parse_source=parse_source,
        standalone_query_parse_succeeded=True,
        standalone_query=standalone,
    )


def _parse_normalized_tool_call(
    tool_calls: list[dict[str, Any]], diagnostics: ContextualizerDiagnostics
) -> tuple[str, ContextualizerDiagnostics]:
    if len(tool_calls) != 1:
        _fail(diagnostics, stage="response_parse", exception_type="tool_call_count_invalid")
    tool_call = tool_calls[0]
    if tool_call.get("name") != "return_standalone_query":
        _fail(diagnostics, stage="response_parse", exception_type="tool_name_invalid")
    return _validate_standalone_args(
        tool_call.get("args"), diagnostics, parse_source="normalized_tool_call"
    )


def _parse_raw_tool_call(
    raw_calls: list[object], diagnostics: ContextualizerDiagnostics
) -> tuple[str, ContextualizerDiagnostics]:
    if len(raw_calls) != 1 or not isinstance(raw_calls[0], dict):
        _fail(diagnostics, stage="response_parse", exception_type="tool_call_count_invalid")
    function = raw_calls[0].get("function")
    if not isinstance(function, dict) or function.get("name") != "return_standalone_query":
        _fail(diagnostics, stage="response_parse", exception_type="tool_name_invalid")
    arguments = function.get("arguments")
    if isinstance(arguments, str):
        try:
            arguments = json.loads(arguments)
        except (TypeError, ValueError):
            _fail(diagnostics, stage="response_parse", exception_type="tool_arguments_invalid")
    return _validate_standalone_args(arguments, diagnostics, parse_source="raw_openai_tool_call")


def _parse_json_content(
    content: object, diagnostics: ContextualizerDiagnostics
) -> tuple[str, ContextualizerDiagnostics]:
    # 部分OpenAI-compatible实现未填充LangChain的tool_calls，但会返回严格JSON正文。
    # 这里只接受完全相同的窄schema，不接受自然语言或Markdown代码块。
    if not isinstance(content, str):
        _fail(diagnostics, stage="response_parse", exception_type="content_shape_invalid")
    try:
        payload = json.loads(content)
    except (TypeError, ValueError):
        _fail(diagnostics, stage="response_parse", exception_type="content_json_invalid")
    return _validate_standalone_args(payload, diagnostics, parse_source="strict_json_content")


def parse_contextualizer_response(
    response: object,
) -> tuple[str, ContextualizerDiagnostics]:
    """Parse only allowlisted OpenAI-compatible shapes under the same strict schema."""

    diagnostics = _response_diagnostics(response)
    if not isinstance(response, AIMessage):
        _fail(diagnostics, stage="response_parse", exception_type="response_type_invalid")

    if response.tool_calls:
        return _parse_normalized_tool_call(response.tool_calls, diagnostics)

    # LangChain records malformed provider Tool arguments here. Do not bypass them by accepting a
    # different field from the same response.
    if response.invalid_tool_calls:
        _fail(diagnostics, stage="response_parse", exception_type="tool_arguments_invalid")

    raw_calls = response.additional_kwargs.get("tool_calls")
    if isinstance(raw_calls, list) and raw_calls:
        return _parse_raw_tool_call(raw_calls, diagnostics)

    if diagnostics.content_existed:
        return _parse_json_content(response.content, diagnostics)

    _fail(diagnostics, stage="response_parse", exception_type="structured_output_missing")


class QwenQueryContextualizer:
    """Use Qwen Tool Calling only to resolve references in a recent safe history window."""

    def __init__(self, model: BaseChatModel) -> None:
        # 与已真实验证的LangChain Agent一样使用普通Tool Calling，不强制供应商特定的
        # tool_choice对象；Prompt要求调用一次，服务器再严格验证名称、数量和参数schema。
        self._model = model.bind_tools([_CONTEXTUALIZE_TOOL])

    def _messages(self, query: str, history: tuple[BaseMessage, ...]) -> list[BaseMessage]:
        messages: list[BaseMessage] = [SystemMessage(content=CONTEXTUALIZER_SYSTEM_PROMPT)]
        messages.extend(history)
        messages.append(HumanMessage(content=query))
        return messages

    async def _resolve_with_diagnostics(
        self, query: str, history: tuple[BaseMessage, ...]
    ) -> tuple[str, ContextualizerDiagnostics]:
        try:
            response = await self._model.ainvoke(self._messages(query, history))
        except FrameworkError:
            raise
        except openai.APIError:
            raise _ContextualizerFailure(
                ContextualizerDiagnostics(
                    failure_stage="model_request", exception_type="provider_api_error"
                )
            ) from None
        except httpx.HTTPError:
            raise _ContextualizerFailure(
                ContextualizerDiagnostics(
                    failure_stage="model_request", exception_type="http_transport_error"
                )
            ) from None
        except ConnectionError:
            raise _ContextualizerFailure(
                ContextualizerDiagnostics(
                    failure_stage="model_request", exception_type="connection_error"
                )
            ) from None
        except TimeoutError:
            raise _ContextualizerFailure(
                ContextualizerDiagnostics(
                    failure_stage="model_request", exception_type="timeout_error"
                )
            ) from None
        except Exception:
            raise _ContextualizerFailure(
                ContextualizerDiagnostics(
                    failure_stage="model_request", exception_type="unexpected_error"
                )
            ) from None
        return parse_contextualizer_response(response)

    async def resolve(self, query: str, history: tuple[BaseMessage, ...]) -> str:
        try:
            standalone, _diagnostics = await self._resolve_with_diagnostics(query, history)
        except _ContextualizerFailure:
            raise context_failed() from None
        return standalone

    async def diagnose(self, query: str, history: tuple[BaseMessage, ...]) -> dict[str, object]:
        """Run one explicit local diagnostic without exposing prompt, history, or raw response."""

        try:
            _standalone, diagnostics = await self._resolve_with_diagnostics(query, history)
        except FrameworkError as error:
            return ContextualizerDiagnostics(
                failure_stage="model_request", exception_type=error.code
            ).to_safe_dict()
        except _ContextualizerFailure as error:
            return error.diagnostics.to_safe_dict()
        return diagnostics.to_safe_dict()


def build_production_contextualizer(
    settings: FrameworkSettings | None = None,
) -> QwenQueryContextualizer:
    return QwenQueryContextualizer(build_qwen_model(settings))

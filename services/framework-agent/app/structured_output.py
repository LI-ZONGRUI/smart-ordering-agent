"""Strict parsing for the OpenAI-compatible structured shapes used by Qwen."""

from __future__ import annotations

import json
from dataclasses import dataclass

from langchain_core.messages import AIMessage


@dataclass(frozen=True, slots=True)
class StrictStructuredOutputError(Exception):
    """Carry only a safe parser category, never raw model content."""

    code: str


def parse_strict_structured_payload(
    response: object, *, tool_name: str
) -> tuple[dict[str, object], str]:
    """Accept normalized Tool Calls, raw OpenAI Tool Calls, or strict JSON content."""

    if not isinstance(response, AIMessage):
        raise StrictStructuredOutputError("response_type_invalid")

    if response.tool_calls:
        if len(response.tool_calls) != 1:
            raise StrictStructuredOutputError("tool_call_count_invalid")
        tool_call = response.tool_calls[0]
        if tool_call.get("name") != tool_name:
            raise StrictStructuredOutputError("tool_name_invalid")
        arguments = tool_call.get("args")
        if not isinstance(arguments, dict):
            raise StrictStructuredOutputError("schema_invalid")
        return arguments, "normalized_tool_call"

    # LangChain records malformed provider Tool arguments here. Never bypass them by accepting
    # another field from the same response.
    if response.invalid_tool_calls:
        raise StrictStructuredOutputError("tool_arguments_invalid")

    raw_calls = response.additional_kwargs.get("tool_calls")
    if isinstance(raw_calls, list) and raw_calls:
        if len(raw_calls) != 1 or not isinstance(raw_calls[0], dict):
            raise StrictStructuredOutputError("tool_call_count_invalid")
        function = raw_calls[0].get("function")
        if not isinstance(function, dict) or function.get("name") != tool_name:
            raise StrictStructuredOutputError("tool_name_invalid")
        arguments = function.get("arguments")
        if isinstance(arguments, str):
            try:
                arguments = json.loads(arguments)
            except (TypeError, ValueError):
                raise StrictStructuredOutputError("tool_arguments_invalid") from None
        if not isinstance(arguments, dict):
            raise StrictStructuredOutputError("schema_invalid")
        return arguments, "raw_openai_tool_call"

    content = response.content
    if not isinstance(content, str):
        raise StrictStructuredOutputError("content_shape_invalid")
    if not content.strip():
        raise StrictStructuredOutputError("structured_output_missing")
    try:
        payload = json.loads(content)
    except (TypeError, ValueError):
        raise StrictStructuredOutputError("content_json_invalid") from None
    if not isinstance(payload, dict):
        raise StrictStructuredOutputError("schema_invalid")
    return payload, "strict_json_content"

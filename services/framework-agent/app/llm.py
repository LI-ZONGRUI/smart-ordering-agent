"""Production Qwen adapter through the OpenAI-compatible LangChain client."""

from langchain_openai import ChatOpenAI

from app.config import FrameworkSettings, require_model_settings


def build_qwen_model(settings: FrameworkSettings | None = None) -> ChatOpenAI:
    """Build the non-streaming model only after validating server-owned config."""

    resolved = require_model_settings(settings)
    return ChatOpenAI(
        api_key=resolved.dashscope_api_key,
        base_url=resolved.llm_base_url,
        model=resolved.framework_agent_llm_model,
        streaming=False,
        temperature=0,
        timeout=30,
        max_retries=0,
    )

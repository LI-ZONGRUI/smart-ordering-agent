import pytest

from app.config import FrameworkSettings, get_settings, require_model_settings
from app.errors import FrameworkError
from app.llm import build_qwen_model


@pytest.fixture(autouse=True)
def clear_settings_cache() -> None:
    get_settings.cache_clear()


def test_missing_configuration_is_safe(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in ("DASHSCOPE_API_KEY", "LLM_BASE_URL", "FRAMEWORK_AGENT_LLM_MODEL"):
        monkeypatch.delenv(name, raising=False)

    with pytest.raises(FrameworkError) as captured:
        require_model_settings()

    assert captured.value.code == "FRAMEWORK_CONFIG_MISSING"
    assert "key" not in captured.value.message.lower()


@pytest.mark.parametrize(
    "base_url",
    ["", "http://example.test/v1", "https://user:secret@example.test/v1", "not-a-url"],
)
def test_invalid_base_url_maps_to_config_missing(base_url: str) -> None:
    settings = FrameworkSettings(
        dashscope_api_key="placeholder",
        llm_base_url=base_url,
        framework_agent_llm_model="qwen3.8-flash",
    )
    with pytest.raises(FrameworkError, match="FRAMEWORK_CONFIG_MISSING"):
        require_model_settings(settings)


def test_qwen_adapter_uses_server_owned_non_streaming_config() -> None:
    settings = FrameworkSettings(
        dashscope_api_key="test-placeholder-only",
        llm_base_url="https://example.test/compatible-mode/v1/",
        framework_agent_llm_model="qwen3.8-flash",
    )
    model = build_qwen_model(settings)

    assert model.model_name == "qwen3.8-flash"
    assert model.openai_api_base == "https://example.test/compatible-mode/v1"
    assert model.streaming is False
    assert model.max_retries == 0
    assert "test-placeholder-only" not in repr(model)

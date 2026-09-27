"""Environment-backed configuration loaded only when production components are built."""

from functools import lru_cache
from urllib.parse import urlsplit

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

from app.errors import config_missing


class FrameworkSettings(BaseSettings):
    """Production model configuration; secrets are never serialized by the API."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    dashscope_api_key: str = ""
    llm_base_url: str = ""
    framework_agent_llm_model: str = "qwen3.8-flash"
    framework_gateway_url: str = ""
    framework_gateway_secret: SecretStr = SecretStr("")
    framework_checkpoint_db_path: str = ""


@lru_cache
def get_settings() -> FrameworkSettings:
    return FrameworkSettings()


def require_model_settings(settings: FrameworkSettings | None = None) -> FrameworkSettings:
    """Validate model settings without revealing which secret is missing."""

    resolved = settings or get_settings()
    api_key = resolved.dashscope_api_key.strip()
    base_url = resolved.llm_base_url.strip().rstrip("/")
    model = resolved.framework_agent_llm_model.strip()
    parsed = urlsplit(base_url)

    if (
        not api_key
        or not model
        or parsed.scheme != "https"
        or not parsed.netloc
        or parsed.username is not None
        or parsed.password is not None
        or parsed.query
        or parsed.fragment
    ):
        raise config_missing()

    return resolved.model_copy(
        update={
            "dashscope_api_key": api_key,
            "llm_base_url": base_url,
            "framework_agent_llm_model": model,
        }
    )


def require_gateway_settings(settings: FrameworkSettings | None = None) -> FrameworkSettings:
    """Validate the fixed HTTPS Gateway endpoint and secret without exposing either value."""

    resolved = settings or get_settings()
    url = resolved.framework_gateway_url.strip()
    secret = resolved.framework_gateway_secret.get_secret_value().strip()
    try:
        parsed = urlsplit(url)
        port = parsed.port
    except ValueError:
        raise config_missing() from None

    if (
        parsed.scheme != "https"
        or not parsed.netloc
        or not parsed.hostname
        or parsed.username is not None
        or parsed.password is not None
        or parsed.query
        or parsed.fragment
        or parsed.path != "/framework-gateway"
        or parsed.hostname.casefold() in {"localhost", "127.0.0.1", "::1"}
        or port is not None
        and not 1 <= port <= 65535
        or not 32 <= len(secret) <= 256
    ):
        raise config_missing()

    return resolved.model_copy(
        update={
            "framework_gateway_url": url,
            "framework_gateway_secret": SecretStr(secret),
        }
    )

"""Stable, non-sensitive service error contract."""

from dataclasses import dataclass


@dataclass(slots=True)
class FrameworkError(Exception):
    """An expected error that is safe to return through the HTTP API."""

    code: str
    message: str
    http_status: int

    def __str__(self) -> str:
        return self.code


def query_invalid() -> FrameworkError:
    return FrameworkError("FRAMEWORK_QUERY_INVALID", "query 必须是 1～200 个字符的字符串", 400)


def config_missing() -> FrameworkError:
    return FrameworkError("FRAMEWORK_CONFIG_MISSING", "模型服务配置不完整", 503)


def model_request_failed() -> FrameworkError:
    return FrameworkError("FRAMEWORK_MODEL_REQUEST_FAILED", "模型请求未完成", 502)


def model_response_invalid() -> FrameworkError:
    return FrameworkError("FRAMEWORK_MODEL_RESPONSE_INVALID", "模型返回格式无效", 502)


def tool_execution_failed() -> FrameworkError:
    return FrameworkError("FRAMEWORK_TOOL_EXECUTION_FAILED", "菜单工具执行失败", 502)


def max_steps_exceeded() -> FrameworkError:
    return FrameworkError("FRAMEWORK_MAX_STEPS_EXCEEDED", "Agent 已达到执行步数上限", 422)


def execution_timeout() -> FrameworkError:
    return FrameworkError("FRAMEWORK_EXECUTION_TIMEOUT", "Agent 执行超时", 504)


def internal_error() -> FrameworkError:
    return FrameworkError("FRAMEWORK_INTERNAL_ERROR", "服务暂时无法完成请求", 500)

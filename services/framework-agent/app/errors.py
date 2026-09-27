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


def thread_invalid() -> FrameworkError:
    return FrameworkError(
        "FRAMEWORK_THREAD_INVALID", "threadId 必须是 8～128 位字母、数字、下划线或连字符", 400
    )


def context_failed() -> FrameworkError:
    return FrameworkError("FRAMEWORK_CONTEXT_FAILED", "对话上下文处理未完成", 502)


def config_missing() -> FrameworkError:
    return FrameworkError("FRAMEWORK_CONFIG_MISSING", "服务配置不完整", 503)


def gateway_request_failed() -> FrameworkError:
    return FrameworkError("FRAMEWORK_GATEWAY_REQUEST_FAILED", "菜单网关请求未完成", 502)


def gateway_timeout() -> FrameworkError:
    return FrameworkError("FRAMEWORK_GATEWAY_TIMEOUT", "菜单网关请求超时", 504)


def gateway_response_invalid() -> FrameworkError:
    return FrameworkError("FRAMEWORK_GATEWAY_RESPONSE_INVALID", "菜单网关返回格式无效", 502)


def gateway_remote_error() -> FrameworkError:
    return FrameworkError("FRAMEWORK_GATEWAY_REMOTE_ERROR", "菜单网关拒绝了请求", 502)


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

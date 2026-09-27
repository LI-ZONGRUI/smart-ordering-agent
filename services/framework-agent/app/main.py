"""FastAPI entry point for the local framework service foundation."""

import asyncio
from collections.abc import Awaitable, Callable

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from langgraph.checkpoint.memory import InMemorySaver

from app.agent import AgentResult, build_production_agent
from app.config import require_model_settings
from app.contextualizer import build_production_contextualizer
from app.errors import (
    FrameworkError,
    execution_timeout,
    internal_error,
    query_invalid,
    thread_invalid,
)
from app.gateways.unicloud_http import build_menu_gateway
from app.graph import build_framework_workflow
from app.models import AgentRunRequest, AgentRunResponse

AGENT_TIMEOUT_SECONDS = 20.0
AgentRunner = Callable[..., Awaitable[AgentResult]]


async def get_agent_runner() -> AgentRunner:
    """Build one production agent run with one owned, reusable HTTP Gateway client."""

    settings = require_model_settings()
    gateway = build_menu_gateway()
    try:
        agent = build_production_agent(gateway)
        contextualizer = build_production_contextualizer(settings)
        # 同一个认证HTTP适配器承载菜单、RAG与只读动作提案，复用HMAC和连接生命周期。
        workflow = build_framework_workflow(
            agent,
            gateway,
            gateway,
            contextualizer,
            checkpointer=app.state.conversation_checkpointer,
        )
    except Exception:
        await gateway.aclose()
        raise

    async def run_and_close(query: str, *, thread_id: str | None = None) -> AgentResult:
        try:
            return await workflow.run(query, thread_id=thread_id)
        finally:
            await gateway.aclose()

    return run_and_close


app = FastAPI(title="framework-agent", version="0.1.0")
app.state.agent_runner_provider = get_agent_runner
# 进程内checkpointer与FastAPI应用同生命周期；服务重启后会丢失，不是持久化用户记忆。
app.state.conversation_checkpointer = InMemorySaver()


def _error_response(error: FrameworkError) -> JSONResponse:
    return JSONResponse(
        status_code=error.http_status,
        content={"errCode": error.code, "errMsg": error.message},
    )


@app.exception_handler(FrameworkError)
async def handle_framework_error(_request: Request, error: FrameworkError) -> JSONResponse:
    return _error_response(error)


@app.exception_handler(RequestValidationError)
async def handle_validation_error(_request: Request, error: RequestValidationError) -> JSONResponse:
    if any("threadId" in item.get("loc", ()) for item in error.errors()):
        return _error_response(thread_invalid())
    return _error_response(query_invalid())


@app.exception_handler(Exception)
async def handle_unexpected_error(_request: Request, _error: Exception) -> JSONResponse:
    return _error_response(internal_error())


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "service": "framework-agent"}


@app.post("/v1/agent/run", response_model=AgentRunResponse, response_model_exclude_none=True)
async def run_agent(
    request: AgentRunRequest,
) -> AgentRunResponse | JSONResponse:
    try:
        # Resolve production dependencies after FastAPI validates the public request body.
        # Tests replace only this provider; the LangChain agent loop itself remains real.
        runner = await app.state.agent_runner_provider()
        invocation = (
            runner(request.query, thread_id=request.threadId)
            if request.threadId is not None
            else runner(request.query)
        )
        result = await asyncio.wait_for(invocation, timeout=AGENT_TIMEOUT_SECONDS)
    except TimeoutError:
        return _error_response(execution_timeout())
    except FrameworkError as error:
        return _error_response(error)
    except Exception:
        return _error_response(internal_error())

    return AgentRunResponse(
        query=result.query,
        answer=result.answer,
        completed=result.completed,
        pendingAction=result.pending_action,
        threadId=request.threadId,
    )

"""FastAPI entry point for the local framework service foundation."""

import asyncio
from collections.abc import Awaitable, Callable

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.agent import AgentResult, build_production_agent
from app.config import require_model_settings
from app.errors import (
    FrameworkError,
    execution_timeout,
    internal_error,
    query_invalid,
)
from app.gateways.unicloud_http import build_menu_gateway
from app.graph import build_framework_workflow
from app.models import AgentRunRequest, AgentRunResponse

AGENT_TIMEOUT_SECONDS = 20.0
AgentRunner = Callable[[str], Awaitable[AgentResult]]


async def get_agent_runner() -> AgentRunner:
    """Build one production agent run with one owned, reusable HTTP Gateway client."""

    require_model_settings()
    gateway = build_menu_gateway()
    try:
        agent = build_production_agent(gateway)
        # 同一个认证HTTP适配器承载菜单、RAG与只读动作提案，复用HMAC和连接生命周期。
        workflow = build_framework_workflow(agent, gateway, gateway)
    except Exception:
        await gateway.aclose()
        raise

    async def run_and_close(query: str) -> AgentResult:
        try:
            return await workflow.run(query)
        finally:
            await gateway.aclose()

    return run_and_close


app = FastAPI(title="framework-agent", version="0.1.0")
app.state.agent_runner_provider = get_agent_runner


def _error_response(error: FrameworkError) -> JSONResponse:
    return JSONResponse(
        status_code=error.http_status,
        content={"errCode": error.code, "errMsg": error.message},
    )


@app.exception_handler(FrameworkError)
async def handle_framework_error(_request: Request, error: FrameworkError) -> JSONResponse:
    return _error_response(error)


@app.exception_handler(RequestValidationError)
async def handle_validation_error(
    _request: Request, _error: RequestValidationError
) -> JSONResponse:
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
        result = await asyncio.wait_for(runner(request.query), timeout=AGENT_TIMEOUT_SECONDS)
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
    )

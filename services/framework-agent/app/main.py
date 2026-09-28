"""FastAPI entry point for the local framework service foundation."""

import asyncio
import re
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager
from typing import Annotated

from fastapi import FastAPI, Header, Request
from fastapi import Path as FastAPIPath
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from langgraph.checkpoint.memory import InMemorySaver

from app.agent import AgentResult, build_production_agent
from app.config import get_settings, require_model_settings
from app.contextualizer import build_production_contextualizer
from app.conversations import ConversationRepository, read_safe_history
from app.errors import (
    FrameworkError,
    conversation_access_denied,
    conversation_invalid,
    execution_timeout,
    history_failed,
    internal_error,
    query_invalid,
    thread_invalid,
)
from app.gateways.unicloud_http import build_menu_gateway
from app.graph import build_framework_workflow
from app.graph.router import build_production_semantic_router
from app.models import (
    AgentRunRequest,
    AgentRunResponse,
    ConversationCreateResponse,
    ConversationHistoryResponse,
)
from app.persistence import PersistentConversationStore, open_persistent_conversation_store

AGENT_TIMEOUT_SECONDS = 20.0
AgentRunner = Callable[..., Awaitable[AgentResult]]
CONVERSATION_TOKEN_PATTERN = re.compile(r"^[A-Za-z0-9_-]{32,256}$")


async def get_agent_runner() -> AgentRunner:
    """Build one production agent run with one owned, reusable HTTP Gateway client."""

    settings = require_model_settings()
    gateway = build_menu_gateway()
    try:
        agent = build_production_agent(gateway)
        contextualizer = build_production_contextualizer(settings)
        semantic_router = build_production_semantic_router(settings)
        # 同一个认证HTTP适配器承载菜单、RAG与只读动作提案，复用HMAC和连接生命周期。
        ephemeral_workflow = build_framework_workflow(
            agent,
            gateway,
            gateway,
            contextualizer,
            checkpointer=app.state.conversation_checkpointer,
            semantic_router=semantic_router,
        )
        durable_workflow = None
        if app.state.durable_conversation_store is not None:
            durable_workflow = build_framework_workflow(
                agent,
                gateway,
                gateway,
                contextualizer,
                checkpointer=app.state.durable_conversation_store.saver,
                semantic_router=semantic_router,
            )
    except Exception:
        await gateway.aclose()
        raise

    async def run_and_close(
        query: str, *, thread_id: str | None = None, durable: bool = False
    ) -> AgentResult:
        try:
            if durable:
                if durable_workflow is None or thread_id is None:
                    raise history_failed()
                return await durable_workflow.run(query, thread_id=thread_id)
            return await ephemeral_workflow.run(query, thread_id=thread_id)
        finally:
            await gateway.aclose()

    return run_and_close


@asynccontextmanager
async def lifespan(application: FastAPI) -> AsyncIterator[None]:
    """Own SQLite connections for exactly the FastAPI application lifetime."""

    store: PersistentConversationStore | None = None
    configured_path = get_settings().framework_checkpoint_db_path.strip()
    if configured_path:
        try:
            store = await open_persistent_conversation_store(configured_path)
        except Exception:
            # The legacy/stateless API remains available; durable endpoints fail closed.
            store = None
    application.state.durable_conversation_store = store
    try:
        yield
    finally:
        if store is not None:
            await store.close()
        application.state.durable_conversation_store = None


app = FastAPI(title="framework-agent", version="0.1.0", lifespan=lifespan)
app.state.agent_runner_provider = get_agent_runner
# 进程内checkpointer与FastAPI应用同生命周期；服务重启后会丢失，不是持久化用户记忆。
app.state.conversation_checkpointer = InMemorySaver()
app.state.durable_conversation_store = None


def _durable_store() -> PersistentConversationStore:
    store = app.state.durable_conversation_store
    if not isinstance(store, PersistentConversationStore):
        raise history_failed()
    return store


def _valid_token(token: str | None) -> bool:
    return isinstance(token, str) and CONVERSATION_TOKEN_PATTERN.fullmatch(token) is not None


async def _authorize_conversation(
    repository: ConversationRepository, thread_id: str, token: str | None
):
    if not _valid_token(token):
        raise conversation_access_denied()
    try:
        record = await repository.authorize(thread_id, token)
    except Exception:
        raise history_failed() from None
    if record is None:
        raise conversation_access_denied()
    return record


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
    if _request.url.path.startswith("/v1/conversations/"):
        return _error_response(conversation_invalid())
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
    conversation_token: Annotated[str | None, Header(alias="X-Conversation-Token")] = None,
) -> AgentRunResponse | JSONResponse:
    try:
        durable = conversation_token is not None
        store = None
        if durable:
            if request.threadId is None:
                raise conversation_invalid()
            store = _durable_store()
            await _authorize_conversation(store.repository, request.threadId, conversation_token)
        # Resolve production dependencies after FastAPI validates the public request body.
        # Tests replace only this provider; the LangChain agent loop itself remains real.
        runner = await app.state.agent_runner_provider()
        if request.threadId is None:
            invocation = runner(request.query)
        elif durable:
            invocation = runner(request.query, thread_id=request.threadId, durable=True)
        else:
            # Keep the V7.3A runner call shape unchanged for ephemeral callers.
            invocation = runner(request.query, thread_id=request.threadId)
        result = await asyncio.wait_for(invocation, timeout=AGENT_TIMEOUT_SECONDS)
        if store is not None and request.threadId is not None:
            try:
                await store.repository.touch(request.threadId)
            except Exception:
                raise history_failed() from None
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


@app.post(
    "/v1/conversations",
    response_model=ConversationCreateResponse,
)
async def create_conversation() -> ConversationCreateResponse | JSONResponse:
    try:
        created = await _durable_store().repository.create()
    except FrameworkError as error:
        return _error_response(error)
    except Exception:
        return _error_response(history_failed())
    return ConversationCreateResponse(
        threadId=created.thread_id,
        conversationToken=created.token,
    )


@app.get(
    "/v1/conversations/{threadId}/messages",
    response_model=ConversationHistoryResponse,
)
async def get_conversation_messages(
    thread_id: Annotated[
        str,
        FastAPIPath(
            alias="threadId",
            min_length=8,
            max_length=128,
            pattern=r"^[A-Za-z0-9_-]+$",
        ),
    ],
    conversation_token: Annotated[str | None, Header(alias="X-Conversation-Token")] = None,
) -> ConversationHistoryResponse | JSONResponse:
    try:
        store = _durable_store()
        record = await _authorize_conversation(store.repository, thread_id, conversation_token)
        messages = await read_safe_history(store.saver, thread_id)
    except FrameworkError as error:
        return _error_response(error)
    except Exception:
        return _error_response(history_failed())
    return ConversationHistoryResponse(
        threadId=thread_id,
        createdAt=record.created_at,
        updatedAt=record.updated_at,
        messages=messages,
    )

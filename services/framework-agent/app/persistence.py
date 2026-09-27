"""Lifecycle-owned durable LangGraph checkpoint and conversation registry."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from pathlib import Path

import aiosqlite
from langgraph.checkpoint.serde.jsonplus import JsonPlusSerializer
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver

from app.conversations import ConversationRepository


@dataclass(slots=True)
class PersistentConversationStore:
    saver: AsyncSqliteSaver
    repository: ConversationRepository
    _saver_connection: aiosqlite.Connection
    _registry_connection: aiosqlite.Connection

    async def close(self) -> None:
        await self._registry_connection.close()
        await self._saver_connection.close()


async def open_persistent_conversation_store(path: str) -> PersistentConversationStore:
    """Open and idempotently initialize one host-local persistent conversation store."""

    database_path = await asyncio.to_thread(_prepare_database_path, path)
    saver_connection = await aiosqlite.connect(database_path)
    registry_connection = await aiosqlite.connect(database_path)
    try:
        # Explicit strict mode prevents arbitrary module reconstruction from checkpoint bytes.
        saver = AsyncSqliteSaver(
            saver_connection,
            serde=JsonPlusSerializer(allowed_msgpack_modules=None),
        )
        await saver.setup()
        repository = ConversationRepository(registry_connection)
        await repository.setup()
        return PersistentConversationStore(
            saver=saver,
            repository=repository,
            _saver_connection=saver_connection,
            _registry_connection=registry_connection,
        )
    except Exception:
        await registry_connection.close()
        await saver_connection.close()
        raise


def _prepare_database_path(path: str) -> Path:
    database_path = Path(path).expanduser()
    database_path.parent.mkdir(parents=True, exist_ok=True)
    return database_path

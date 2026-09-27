"""Durable conversation capability registry and safe history projection."""

from __future__ import annotations

import hashlib
import hmac
import secrets
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

import aiosqlite
from langchain_core.messages import AIMessage, HumanMessage
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver

from app.graph.state import ARCHIVE_MESSAGE_LIMIT

THREAD_PREFIX = "conv_"
TOKEN_BYTES = 32
_DUMMY_TOKEN_HASH = hashlib.sha256(b"invalid-conversation-capability").digest()


def _utc_now() -> str:
    return datetime.now(UTC).isoformat()


def hash_conversation_token(token: str) -> bytes:
    """Hash a high-entropy capability token before storage."""

    return hashlib.sha256(token.encode("utf-8")).digest()


@dataclass(frozen=True, slots=True)
class ConversationRecord:
    thread_id: str
    token_hash: bytes
    created_at: str
    updated_at: str


@dataclass(frozen=True, slots=True)
class CreatedConversation:
    thread_id: str
    token: str


class ConversationRepository:
    """Store capability metadata; LangGraph remains the canonical message store."""

    def __init__(self, connection: aiosqlite.Connection) -> None:
        self._connection = connection

    async def setup(self) -> None:
        await self._connection.execute("PRAGMA journal_mode=WAL")
        await self._connection.execute(
            """
            CREATE TABLE IF NOT EXISTS conversations (
                thread_id TEXT PRIMARY KEY,
                token_hash BLOB NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """
        )
        await self._connection.commit()

    async def create(self) -> CreatedConversation:
        """Create a server-owned thread and return its capability exactly once."""

        for _attempt in range(5):
            thread_id = f"{THREAD_PREFIX}{secrets.token_urlsafe(18)}"
            token = secrets.token_urlsafe(TOKEN_BYTES)
            now = _utc_now()
            try:
                await self._connection.execute(
                    """
                    INSERT INTO conversations(thread_id, token_hash, created_at, updated_at)
                    VALUES (?, ?, ?, ?)
                    """,
                    (thread_id, hash_conversation_token(token), now, now),
                )
                await self._connection.commit()
                return CreatedConversation(thread_id=thread_id, token=token)
            except aiosqlite.IntegrityError:
                continue
        raise RuntimeError("conversation identifier generation failed")

    async def get(self, thread_id: str) -> ConversationRecord | None:
        cursor = await self._connection.execute(
            """
            SELECT thread_id, token_hash, created_at, updated_at
            FROM conversations WHERE thread_id = ?
            """,
            (thread_id,),
        )
        row = await cursor.fetchone()
        await cursor.close()
        if row is None:
            return None
        return ConversationRecord(
            thread_id=str(row[0]),
            token_hash=bytes(row[1]),
            created_at=str(row[2]),
            updated_at=str(row[3]),
        )

    async def authorize(self, thread_id: str, token: str) -> ConversationRecord | None:
        """Compare digests in constant time and hide whether the thread exists."""

        record = await self.get(thread_id)
        expected = record.token_hash if record is not None else _DUMMY_TOKEN_HASH
        supplied = hash_conversation_token(token)
        if not hmac.compare_digest(expected, supplied) or record is None:
            return None
        return record

    async def touch(self, thread_id: str) -> None:
        await self._connection.execute(
            "UPDATE conversations SET updated_at = ? WHERE thread_id = ?",
            (_utc_now(), thread_id),
        )
        await self._connection.commit()


def project_safe_messages(raw_messages: Any) -> list[dict[str, str]]:
    """Expose only bounded plain user/assistant text from a trusted checkpoint."""

    if not isinstance(raw_messages, list):
        return []
    projected: list[dict[str, str]] = []
    for message in raw_messages[-ARCHIVE_MESSAGE_LIMIT:]:
        role: str | None = None
        if isinstance(message, HumanMessage):
            role = "user"
        elif isinstance(message, AIMessage):
            role = "assistant"
        if role is not None and isinstance(message.content, str) and message.content:
            projected.append({"role": role, "content": message.content})
    return projected


async def read_safe_history(saver: AsyncSqliteSaver, thread_id: str) -> list[dict[str, str]]:
    """Read the latest archive channel without exposing raw checkpoint internals."""

    checkpoint = await saver.aget({"configurable": {"thread_id": thread_id, "checkpoint_ns": ""}})
    if checkpoint is None:
        return []
    channel_values = checkpoint.get("channel_values")
    if not isinstance(channel_values, dict):
        return []
    return project_safe_messages(channel_values.get("archiveMessages", []))

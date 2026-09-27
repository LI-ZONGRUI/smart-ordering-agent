"""Bounded, serializable state for the top-level Framework Agent workflow."""

from typing import Annotated, Literal, NotRequired, TypedDict

from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages

from app.gateways.action import PendingAction

FrameworkRoute = Literal[
    "menu_query", "knowledge_query", "action_query", "smalltalk", "unsupported_action"
]
FRAMEWORK_ROUTES: frozenset[str] = frozenset(
    {"menu_query", "knowledge_query", "action_query", "smalltalk", "unsupported_action"}
)
HISTORY_MESSAGE_LIMIT = 8
ARCHIVE_MESSAGE_LIMIT = 100


def merge_conversation_messages(
    left: list[BaseMessage], right: list[BaseMessage]
) -> list[BaseMessage]:
    """Append message updates while retaining only the latest safe user/assistant window."""

    return list(add_messages(left, right))[-HISTORY_MESSAGE_LIMIT:]


def merge_archive_messages(left: list[BaseMessage], right: list[BaseMessage]) -> list[BaseMessage]:
    """Keep a bounded user-visible archive in the same durable graph checkpoint."""

    return list(add_messages(left, right))[-ARCHIVE_MESSAGE_LIMIT:]


class FrameworkGraphState(TypedDict):
    query: str
    resolved_query: NotRequired[str]
    messages: Annotated[list[BaseMessage], merge_conversation_messages]
    archiveMessages: Annotated[list[BaseMessage], merge_archive_messages]
    route: NotRequired[FrameworkRoute]
    answer: NotRequired[str]
    completed: NotRequired[bool]
    pendingAction: NotRequired[PendingAction | None]

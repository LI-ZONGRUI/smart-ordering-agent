"""Minimal serializable state for the top-level Framework Agent workflow."""

from typing import Literal, NotRequired, TypedDict

FrameworkRoute = Literal["menu_query", "knowledge_query", "smalltalk", "unsupported_action"]
FRAMEWORK_ROUTES: frozenset[str] = frozenset(
    {"menu_query", "knowledge_query", "smalltalk", "unsupported_action"}
)


class FrameworkGraphState(TypedDict):
    query: str
    route: NotRequired[FrameworkRoute]
    answer: NotRequired[str]
    completed: NotRequired[bool]

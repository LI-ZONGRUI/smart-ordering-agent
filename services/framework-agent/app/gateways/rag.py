"""Narrow read-only port for the existing uniCloud RAG answer capability."""

from typing import Protocol, TypedDict


class KnowledgeAnswer(TypedDict):
    query: str
    answerable: bool
    answer: str


class RagGateway(Protocol):
    async def answer_knowledge(self, query: str) -> KnowledgeAnswer: ...

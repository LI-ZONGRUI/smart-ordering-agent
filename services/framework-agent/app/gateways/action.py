"""Narrow proposal-only port for the existing Native Agent."""

from typing import Literal, Protocol, TypedDict


class PendingAction(TypedDict):
    type: Literal["add_to_cart"]
    dishId: str
    name: str
    quantity: int
    unitPrice: int | float
    totalPrice: int | float
    requiresConfirmation: Literal[True]


class ActionProposalResult(TypedDict):
    query: str
    answer: str
    completed: bool
    pendingAction: PendingAction | None


class ActionProposalGateway(Protocol):
    async def propose_action(self, query: str) -> ActionProposalResult: ...

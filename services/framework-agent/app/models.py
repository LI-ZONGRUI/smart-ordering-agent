"""Public HTTP request and response models."""

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StrictStr, field_validator


class AgentRunRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    query: Annotated[StrictStr, Field(min_length=1, max_length=200)]
    threadId: (
        Annotated[
            StrictStr,
            Field(min_length=8, max_length=128, pattern=r"^[A-Za-z0-9_-]+$"),
        ]
        | None
    ) = None

    @field_validator("query", mode="before")
    @classmethod
    def trim_query(cls, value: object) -> object:
        return value.strip() if isinstance(value, str) else value

    @field_validator("threadId", mode="before")
    @classmethod
    def trim_thread_id(cls, value: object) -> object:
        return value.strip() if isinstance(value, str) else value


class PendingActionResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    type: Literal["add_to_cart"]
    dishId: str
    name: str
    quantity: Annotated[int, Field(ge=1, le=20)]
    unitPrice: Annotated[float, Field(ge=0)]
    totalPrice: Annotated[float, Field(ge=0)]
    requiresConfirmation: Literal[True]


class AgentRunResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    errCode: int = 0
    query: str
    answer: str
    completed: bool = True
    pendingAction: PendingActionResponse | None = None
    threadId: str | None = None


class ErrorResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    errCode: str
    errMsg: str

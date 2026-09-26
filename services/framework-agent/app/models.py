"""Public HTTP request and response models."""

from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, StrictStr, field_validator


class AgentRunRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    query: Annotated[StrictStr, Field(min_length=1, max_length=200)]

    @field_validator("query", mode="before")
    @classmethod
    def trim_query(cls, value: object) -> object:
        return value.strip() if isinstance(value, str) else value


class AgentRunResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    errCode: int = 0
    query: str
    answer: str
    completed: bool = True


class ErrorResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    errCode: str
    errMsg: str

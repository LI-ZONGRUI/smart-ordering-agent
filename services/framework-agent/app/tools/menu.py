"""Strict, read-only LangChain tools backed only by the MenuGateway port."""

from langchain_core.tools import BaseTool, tool
from pydantic import BaseModel, ConfigDict, Field, StrictStr, field_validator

from app.errors import FrameworkError, tool_execution_failed
from app.gateways.base import MenuGateway


class SearchMenuInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    query: StrictStr = Field(min_length=1, max_length=100)

    @field_validator("query", mode="before")
    @classmethod
    def trim_query(cls, value: object) -> object:
        return value.strip() if isinstance(value, str) else value


class ListAvailableDrinksInput(BaseModel):
    model_config = ConfigDict(extra="forbid")


class GetDishDetailInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    dish_id: StrictStr = Field(min_length=1, max_length=100)

    @field_validator("dish_id", mode="before")
    @classmethod
    def trim_dish_id(cls, value: object) -> object:
        return value.strip() if isinstance(value, str) else value


def build_menu_tools(gateway: MenuGateway) -> list[BaseTool]:
    """Bind the three allowed operations to one explicit read-only gateway."""

    @tool("search_menu", args_schema=SearchMenuInput)
    async def search_menu(query: str) -> dict[str, object]:
        """Search the menu by a short user-supplied keyword."""

        try:
            return await gateway.search_menu(query)
        except FrameworkError:
            raise
        except Exception:
            raise tool_execution_failed() from None

    @tool("list_available_drinks", args_schema=ListAvailableDrinksInput)
    async def list_available_drinks() -> dict[str, object]:
        """List drinks whose current menu status is available."""

        try:
            return await gateway.list_available_drinks()
        except FrameworkError:
            raise
        except Exception:
            raise tool_execution_failed() from None

    @tool("get_dish_detail", args_schema=GetDishDetailInput)
    async def get_dish_detail(dish_id: str) -> dict[str, object]:
        """Get current details for one dish identifier."""

        try:
            return await gateway.get_dish_detail(dish_id)
        except FrameworkError:
            raise
        except Exception:
            raise tool_execution_failed() from None

    return [search_menu, list_available_drinks, get_dish_detail]

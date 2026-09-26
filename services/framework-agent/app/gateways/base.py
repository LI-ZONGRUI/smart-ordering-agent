"""Ports through which read-only tools obtain menu facts."""

from abc import ABC, abstractmethod
from typing import TypedDict


class MenuItemSummary(TypedDict):
    dishId: str
    name: str
    price: int | float
    status: str


class MenuItemDetail(MenuItemSummary):
    categoryId: str
    description: str
    ingredients: list[str]
    spicyLevel: int


class MenuSearchResult(TypedDict):
    count: int
    items: list[MenuItemSummary]


class DishDetailResult(TypedDict):
    found: bool
    item: MenuItemDetail | None


class MenuGateway(ABC):
    """Read-only menu boundary. Implementations own data access outside the tools."""

    @abstractmethod
    async def search_menu(self, query: str) -> MenuSearchResult: ...

    @abstractmethod
    async def list_available_drinks(self) -> MenuSearchResult: ...

    @abstractmethod
    async def get_dish_detail(self, dish_id: str) -> DishDetailResult: ...

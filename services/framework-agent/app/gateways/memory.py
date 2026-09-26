"""Deterministic local fixture gateway. Never used as a production fallback."""

from copy import deepcopy

from app.gateways.base import (
    DishDetailResult,
    MenuGateway,
    MenuItemDetail,
    MenuItemSummary,
    MenuSearchResult,
)

_FIXTURE_DISHES: tuple[MenuItemDetail, ...] = (
    {
        "dishId": "fixture-lemon-tea",
        "name": "柠檬茶",
        "categoryId": "drink",
        "description": "本地编排测试饮料",
        "price": 12,
        "status": "on_sale",
        "ingredients": ["红茶", "柠檬"],
        "spicyLevel": 0,
    },
    {
        "dishId": "fixture-sour-plum-drink",
        "name": "酸梅汤",
        "categoryId": "drink",
        "description": "本地编排测试饮料",
        "price": 14,
        "status": "sold_out",
        "ingredients": ["乌梅", "山楂"],
        "spicyLevel": 0,
    },
)


def _summary(dish: MenuItemDetail) -> MenuItemSummary:
    return {key: dish[key] for key in ("dishId", "name", "price", "status")}


class InMemoryMenuGateway(MenuGateway):
    """Tiny fixture for offline tests and local demos; it is not live menu data."""

    async def search_menu(self, query: str) -> MenuSearchResult:
        keyword = query.strip().casefold()
        matches = [
            dish
            for dish in _FIXTURE_DISHES
            if keyword
            and (
                keyword in dish["name"].casefold()
                or keyword in dish["description"].casefold()
                or any(keyword in ingredient.casefold() for ingredient in dish["ingredients"])
            )
        ]
        items = [_summary(dish) for dish in matches]
        return {"count": len(items), "items": items}

    async def list_available_drinks(self) -> MenuSearchResult:
        items = [
            _summary(dish)
            for dish in _FIXTURE_DISHES
            if dish["categoryId"] == "drink" and dish["status"] == "on_sale"
        ]
        return {"count": len(items), "items": items}

    async def get_dish_detail(self, dish_id: str) -> DishDetailResult:
        dish = next((item for item in _FIXTURE_DISHES if item["dishId"] == dish_id), None)
        return {"found": dish is not None, "item": deepcopy(dish) if dish else None}

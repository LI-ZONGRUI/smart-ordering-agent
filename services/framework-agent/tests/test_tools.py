import pytest
from pydantic import ValidationError

from app.errors import FrameworkError
from app.gateways.base import DishDetailResult, MenuGateway, MenuSearchResult
from app.gateways.memory import InMemoryMenuGateway
from app.tools.menu import build_menu_tools


def _tool_map(gateway: MenuGateway) -> dict[str, object]:
    return {item.name: item for item in build_menu_tools(gateway)}


def test_exactly_three_read_only_tools_are_registered() -> None:
    tools = build_menu_tools(InMemoryMenuGateway())
    assert [item.name for item in tools] == [
        "search_menu",
        "list_available_drinks",
        "get_dish_detail",
    ]
    names = " ".join(item.name for item in tools)
    assert all(word not in names for word in ("cart", "order", "pay"))


@pytest.mark.parametrize(
    ("tool_name", "properties"),
    [
        ("search_menu", {"query"}),
        ("list_available_drinks", set()),
        ("get_dish_detail", {"dish_id"}),
    ],
)
def test_tool_schemas_are_strict(tool_name: str, properties: set[str]) -> None:
    schema = _tool_map(InMemoryMenuGateway())[tool_name].args_schema.model_json_schema()
    assert set(schema.get("properties", {})) == properties
    assert schema["additionalProperties"] is False


@pytest.mark.asyncio
async def test_search_menu_uses_fixture_gateway() -> None:
    result = await _tool_map(InMemoryMenuGateway())["search_menu"].ainvoke({"query": "柠檬茶"})
    assert result == {
        "count": 1,
        "items": [
            {
                "dishId": "fixture-lemon-tea",
                "name": "柠檬茶",
                "price": 12,
                "status": "on_sale",
            }
        ],
    }


@pytest.mark.asyncio
async def test_available_drinks_excludes_sold_out_fixture() -> None:
    result = await _tool_map(InMemoryMenuGateway())["list_available_drinks"].ainvoke({})
    assert result["count"] == 1
    assert [item["name"] for item in result["items"]] == ["柠檬茶"]


@pytest.mark.asyncio
async def test_get_dish_detail_returns_fixture() -> None:
    result = await _tool_map(InMemoryMenuGateway())["get_dish_detail"].ainvoke(
        {"dish_id": "fixture-sour-plum-drink"}
    )
    assert result["found"] is True
    assert result["item"]["status"] == "sold_out"
    assert result["item"]["price"] == 14


@pytest.mark.asyncio
async def test_extra_arguments_are_rejected() -> None:
    tool = _tool_map(InMemoryMenuGateway())["search_menu"]
    with pytest.raises(ValidationError):
        await tool.ainvoke({"query": "柠檬茶", "write": True})


class FailingGateway(MenuGateway):
    async def search_menu(self, query: str) -> MenuSearchResult:
        del query
        raise RuntimeError("database-internal-secret")

    async def list_available_drinks(self) -> MenuSearchResult:
        raise RuntimeError("database-internal-secret")

    async def get_dish_detail(self, dish_id: str) -> DishDetailResult:
        del dish_id
        raise RuntimeError("database-internal-secret")


@pytest.mark.asyncio
async def test_gateway_failure_maps_to_safe_tool_error() -> None:
    with pytest.raises(FrameworkError) as captured:
        await _tool_map(FailingGateway())["search_menu"].ainvoke({"query": "tea"})
    assert captured.value.code == "FRAMEWORK_TOOL_EXECUTION_FAILED"
    assert "database" not in captured.value.message.lower()

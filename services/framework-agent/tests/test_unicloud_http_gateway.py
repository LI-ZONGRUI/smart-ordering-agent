import json
from collections.abc import Callable
from pathlib import Path

import httpx
import pytest

from app.config import FrameworkSettings
from app.errors import FrameworkError
from app.gateways.signing import NONCE_PATTERN
from app.gateways.unicloud_http import UniCloudHttpMenuGateway, build_menu_gateway

URL = "https://gateway.example.test/framework-gateway"
SECRET = "test-only-framework-secret-at-least-32-chars"
TIMESTAMP = 1_700_000_000


def _success(operation: str, data: object) -> httpx.Response:
    return httpx.Response(200, json={"errCode": 0, "operation": operation, "data": data})


def _gateway(
    handler: Callable[[httpx.Request], httpx.Response],
    *,
    nonces: list[str] | None = None,
) -> tuple[UniCloudHttpMenuGateway, httpx.AsyncClient]:
    values = iter(nonces or ["test_nonce_1234567890"])
    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    gateway = UniCloudHttpMenuGateway(
        url=URL,
        secret=SECRET,
        client=client,
        clock=lambda: TIMESTAMP,
        nonce_factory=lambda: next(values),
    )
    return gateway, client


@pytest.mark.asyncio
async def test_search_request_signs_and_sends_the_exact_compact_unicode_body() -> None:
    observed: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        observed.update(headers=dict(request.headers), content=request.content)
        return _success(
            "search_menu",
            {
                "tool": "search_menu",
                "query": "柠檬茶",
                "count": 1,
                "items": [
                    {
                        "dishId": "dish-4",
                        "name": "柠檬茶",
                        "categoryId": "drink",
                        "price": 12,
                        "status": "on_sale",
                        "spicyLevel": 0,
                    }
                ],
            },
        )

    gateway, client = _gateway(handler)
    try:
        result = await gateway.search_menu(" 柠檬茶 ")
    finally:
        await client.aclose()

    assert result == {
        "count": 1,
        "items": [{"dishId": "dish-4", "name": "柠檬茶", "price": 12, "status": "on_sale"}],
    }
    assert observed["content"] == (
        '{"operation":"search_menu","arguments":{"query":"柠檬茶"}}'.encode()
    )
    headers = observed["headers"]
    assert isinstance(headers, dict)
    assert headers["content-type"] == "application/json"
    assert headers["x-framework-signature-version"] == "v1"
    assert headers["x-framework-timestamp"] == str(TIMESTAMP)
    assert NONCE_PATTERN.fullmatch(headers["x-framework-nonce"])
    assert "x-framework-signature" in headers
    assert SECRET not in json.dumps(headers)
    assert "authorization" not in headers


@pytest.mark.asyncio
async def test_all_three_operations_use_exact_names_and_arguments() -> None:
    requests: list[dict[str, object]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        payload = json.loads(request.content)
        requests.append(payload)
        operation = payload["operation"]
        if operation == "get_dish_detail":
            return _success(
                operation,
                {
                    "tool": operation,
                    "dishId": "dish-4",
                    "found": True,
                    "item": {
                        "dishId": "dish-4",
                        "name": "柠檬茶",
                        "categoryId": "drink",
                        "description": "清爽柠檬香",
                        "price": 12,
                        "status": "on_sale",
                        "spicyLevel": 0,
                        "ingredients": ["红茶", "柠檬"],
                    },
                },
            )
        data = {"tool": operation, "count": 0, "items": []}
        if operation == "search_menu":
            data["query"] = payload["arguments"]["query"]
        return _success(operation, data)

    gateway, client = _gateway(
        handler,
        nonces=["nonce_search_12345678", "nonce_drinks_1234567", "nonce_detail_1234567"],
    )
    try:
        await gateway.search_menu("可乐")
        await gateway.list_available_drinks()
        detail = await gateway.get_dish_detail("dish-4")
    finally:
        await client.aclose()

    assert requests == [
        {"operation": "search_menu", "arguments": {"query": "可乐"}},
        {"operation": "list_available_drinks", "arguments": {}},
        {"operation": "get_dish_detail", "arguments": {"dishId": "dish-4"}},
    ]
    assert detail["found"] is True
    assert detail["item"]["ingredients"] == ["红茶", "柠檬"]


@pytest.mark.asyncio
async def test_detail_not_found_keeps_existing_gateway_contract() -> None:
    gateway, client = _gateway(
        lambda _request: _success(
            "get_dish_detail",
            {"tool": "get_dish_detail", "dishId": "missing", "found": False, "item": None},
        )
    )
    try:
        assert await gateway.get_dish_detail("missing") == {"found": False, "item": None}
    finally:
        await client.aclose()


@pytest.mark.parametrize(
    ("error", "expected"),
    [
        (httpx.ReadTimeout("private timeout"), "FRAMEWORK_GATEWAY_TIMEOUT"),
        (httpx.ConnectError("private connection"), "FRAMEWORK_GATEWAY_REQUEST_FAILED"),
    ],
)
@pytest.mark.asyncio
async def test_network_failures_map_to_safe_errors(
    error: httpx.RequestError, expected: str
) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        error.request = request
        raise error

    gateway, client = _gateway(handler)
    try:
        with pytest.raises(FrameworkError, match=expected) as captured:
            await gateway.list_available_drinks()
    finally:
        await client.aclose()
    assert "private" not in str(captured.value)
    assert "private" not in repr(captured.value)


@pytest.mark.asyncio
async def test_http_error_is_safely_mapped_without_response_body() -> None:
    gateway, client = _gateway(
        lambda _request: httpx.Response(500, text=f"database failure {SECRET}")
    )
    try:
        with pytest.raises(FrameworkError, match="FRAMEWORK_GATEWAY_REQUEST_FAILED") as captured:
            await gateway.list_available_drinks()
    finally:
        await client.aclose()
    assert SECRET not in str(captured.value) + repr(captured.value)


@pytest.mark.parametrize(
    "response",
    [
        httpx.Response(200, content=b""),
        httpx.Response(200, text="<html>bad</html>"),
        httpx.Response(200, content=b"{bad"),
        httpx.Response(200, json=[]),
        httpx.Response(200, json={"operation": "list_available_drinks", "data": {}}),
        httpx.Response(
            200, json={"errCode": False, "operation": "list_available_drinks", "data": {}}
        ),
        httpx.Response(200, json={"errCode": 0, "operation": "wrong", "data": {}}),
        httpx.Response(200, json={"errCode": 0, "operation": "list_available_drinks"}),
        httpx.Response(
            200,
            json={
                "errCode": 0,
                "operation": "list_available_drinks",
                "data": {"tool": "list_available_drinks", "count": 1, "items": []},
            },
        ),
        httpx.Response(
            200,
            json={
                "errCode": 0,
                "operation": "list_available_drinks",
                "data": {"tool": "list_available_drinks", "count": 1, "items": ["bad"]},
            },
        ),
    ],
)
@pytest.mark.asyncio
async def test_malformed_responses_are_rejected(response: httpx.Response) -> None:
    gateway, client = _gateway(lambda _request: response)
    try:
        with pytest.raises(FrameworkError, match="FRAMEWORK_GATEWAY_RESPONSE_INVALID"):
            await gateway.list_available_drinks()
    finally:
        await client.aclose()


@pytest.mark.asyncio
async def test_remote_error_is_not_treated_as_success_or_leaked() -> None:
    gateway, client = _gateway(
        lambda _request: httpx.Response(
            200,
            json={
                "errCode": "FRAMEWORK_GATEWAY_AUTH_INVALID",
                "message": f"private {SECRET}",
            },
        )
    )
    try:
        with pytest.raises(FrameworkError, match="FRAMEWORK_GATEWAY_REMOTE_ERROR") as captured:
            await gateway.search_menu("柠檬茶")
    finally:
        await client.aclose()
    assert SECRET not in str(captured.value) + repr(captured.value)


@pytest.mark.asyncio
async def test_production_factory_uses_http_adapter_and_never_memory_fallback() -> None:
    client = httpx.AsyncClient(transport=httpx.MockTransport(lambda _request: httpx.Response(500)))
    try:
        gateway = build_menu_gateway(
            FrameworkSettings(
                framework_gateway_url=URL,
                framework_gateway_secret=SECRET,
            ),
            client=client,
        )
        assert isinstance(gateway, UniCloudHttpMenuGateway)
    finally:
        await client.aclose()


def test_http_adapter_has_no_business_query_write_or_retry_logic() -> None:
    source = Path("app/gateways/unicloud_http.py").read_text()
    for forbidden in (
        "uniCloud.database",
        "collection(",
        "createOrder",
        "createConfirmedOrder",
        "prepare_add_to_cart",
        "InMemoryMenuGateway",
        "retry",
    ):
        assert forbidden not in source

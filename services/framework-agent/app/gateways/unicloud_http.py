"""Authenticated HTTPS adapter for the uniCloud read-only Framework Gateway."""

import math
from collections.abc import Callable
from typing import Any

import httpx

from app.config import FrameworkSettings, require_gateway_settings
from app.errors import (
    gateway_remote_error,
    gateway_request_failed,
    gateway_response_invalid,
    gateway_timeout,
)
from app.gateways.action import ActionProposalResult, PendingAction
from app.gateways.base import DishDetailResult, MenuGateway, MenuItemDetail, MenuSearchResult
from app.gateways.rag import KnowledgeAnswer
from app.gateways.signing import Clock, NonceFactory, build_auth_headers, encode_json_body

GATEWAY_TIMEOUT = httpx.Timeout(connect=3.0, read=8.0, write=5.0, pool=3.0)
_SUMMARY_KEYS = ("dishId", "name", "price", "status")


def _nonempty(value: object) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _valid_price(value: object) -> bool:
    return type(value) in {int, float} and math.isfinite(value) and value >= 0


def _summary(value: object) -> dict[str, object]:
    if not isinstance(value, dict):
        raise gateway_response_invalid()
    if (
        not _nonempty(value.get("dishId"))
        or not _nonempty(value.get("name"))
        or not _valid_price(value.get("price"))
        or value.get("status") not in {"on_sale", "sold_out"}
    ):
        raise gateway_response_invalid()
    return {key: value[key] for key in _SUMMARY_KEYS}


def _menu_result(data: object, *, tool: str, query: str | None = None) -> MenuSearchResult:
    if not isinstance(data, dict) or data.get("tool") != tool:
        raise gateway_response_invalid()
    if query is not None and data.get("query") != query:
        raise gateway_response_invalid()
    count = data.get("count")
    items = data.get("items")
    if type(count) is not int or count < 0 or not isinstance(items, list) or count != len(items):
        raise gateway_response_invalid()
    return {"count": count, "items": [_summary(item) for item in items]}


def _detail_result(data: object, *, dish_id: str) -> DishDetailResult:
    if (
        not isinstance(data, dict)
        or data.get("tool") != "get_dish_detail"
        or data.get("dishId") != dish_id
        or type(data.get("found")) is not bool
    ):
        raise gateway_response_invalid()
    found = data["found"]
    item = data.get("item")
    if not found:
        if item is not None:
            raise gateway_response_invalid()
        return {"found": False, "item": None}
    summary = _summary(item)
    if not isinstance(item, dict) or summary["dishId"] != dish_id:
        raise gateway_response_invalid()
    if (
        not _nonempty(item.get("categoryId"))
        or not isinstance(item.get("description"), str)
        or type(item.get("spicyLevel")) is not int
        or not 0 <= item["spicyLevel"] <= 5
        or not isinstance(item.get("ingredients"), list)
        or not all(_nonempty(value) for value in item["ingredients"])
    ):
        raise gateway_response_invalid()
    detail: MenuItemDetail = {
        **summary,  # type: ignore[typeddict-item]
        "categoryId": item["categoryId"],
        "description": item["description"],
        "ingredients": list(item["ingredients"]),
        "spicyLevel": item["spicyLevel"],
    }
    return {"found": True, "item": detail}


def _knowledge_answer(data: object, *, query: str) -> KnowledgeAnswer:
    if not isinstance(data, dict) or set(data) != {"query", "answerable", "answer"}:
        raise gateway_response_invalid()
    if (
        data.get("query") != query
        or type(data.get("answerable")) is not bool
        or not _nonempty(data.get("answer"))
    ):
        raise gateway_response_invalid()
    return {
        "query": query,
        "answerable": data["answerable"],
        "answer": data["answer"].strip(),
    }


def _pending_action(value: object) -> PendingAction | None:
    if value is None:
        return None
    expected = {
        "type",
        "dishId",
        "name",
        "quantity",
        "unitPrice",
        "totalPrice",
        "requiresConfirmation",
    }
    if not isinstance(value, dict) or set(value) != expected:
        raise gateway_response_invalid()
    quantity = value.get("quantity")
    unit_price = value.get("unitPrice")
    total_price = value.get("totalPrice")
    if (
        value.get("type") != "add_to_cart"
        or not _nonempty(value.get("dishId"))
        or not _nonempty(value.get("name"))
        or type(quantity) is not int
        or not 1 <= quantity <= 20
        or not _valid_price(unit_price)
        or not _valid_price(total_price)
        or round(unit_price * 100) * quantity != round(total_price * 100)
        or value.get("requiresConfirmation") is not True
    ):
        raise gateway_response_invalid()
    return {
        "type": "add_to_cart",
        "dishId": value["dishId"].strip(),
        "name": value["name"].strip(),
        "quantity": quantity,
        "unitPrice": unit_price,
        "totalPrice": total_price,
        "requiresConfirmation": True,
    }


def _action_proposal(data: object, *, query: str) -> ActionProposalResult:
    if not isinstance(data, dict) or set(data) != {
        "query",
        "answer",
        "completed",
        "pendingAction",
    }:
        raise gateway_response_invalid()
    if (
        data.get("query") != query
        or not _nonempty(data.get("answer"))
        or data.get("completed") is not True
    ):
        raise gateway_response_invalid()
    return {
        "query": query,
        "answer": data["answer"].strip(),
        "completed": True,
        "pendingAction": _pending_action(data["pendingAction"]),
    }


class UniCloudHttpMenuGateway(MenuGateway):
    """One-request-per-operation adapter; menu rules remain in the Shared Domain."""

    def __init__(
        self,
        *,
        url: str,
        secret: str,
        client: httpx.AsyncClient | None = None,
        clock: Clock | None = None,
        nonce_factory: NonceFactory | None = None,
    ) -> None:
        self._url = url
        self._secret = secret
        self._client = client or httpx.AsyncClient(timeout=GATEWAY_TIMEOUT)
        self._owns_client = client is None
        self._clock = clock
        self._nonce_factory = nonce_factory

    async def aclose(self) -> None:
        if self._owns_client:
            await self._client.aclose()

    async def _request(self, operation: str, arguments: dict[str, object]) -> object:
        body = encode_json_body({"operation": operation, "arguments": arguments})
        signing_options: dict[str, Any] = {"secret": self._secret}
        if self._clock is not None:
            signing_options["clock"] = self._clock
        if self._nonce_factory is not None:
            signing_options["nonce_factory"] = self._nonce_factory
        try:
            headers = {
                "Content-Type": "application/json",
                **build_auth_headers(body, **signing_options),
            }
        except (TypeError, ValueError):
            raise gateway_request_failed() from None

        try:
            response = await self._client.post(self._url, content=body, headers=headers)
        except httpx.TimeoutException:
            raise gateway_timeout() from None
        except httpx.RequestError:
            raise gateway_request_failed() from None
        if not 200 <= response.status_code < 300:
            raise gateway_request_failed()
        try:
            payload = response.json()
        except (ValueError, UnicodeError):
            raise gateway_response_invalid() from None
        if not isinstance(payload, dict) or "errCode" not in payload:
            raise gateway_response_invalid()
        err_code = payload["errCode"]
        if isinstance(err_code, str) and err_code:
            raise gateway_remote_error()
        if type(err_code) is not int or err_code != 0:
            raise gateway_response_invalid()
        if payload.get("operation") != operation or "data" not in payload:
            raise gateway_response_invalid()
        return payload["data"]

    async def search_menu(self, query: str) -> MenuSearchResult:
        clean = query.strip() if isinstance(query, str) else ""
        if not 1 <= len(clean) <= 200:
            raise gateway_request_failed()
        data = await self._request("search_menu", {"query": clean})
        return _menu_result(data, tool="search_menu", query=clean)

    async def list_available_drinks(self) -> MenuSearchResult:
        data = await self._request("list_available_drinks", {})
        return _menu_result(data, tool="list_available_drinks")

    async def get_dish_detail(self, dish_id: str) -> DishDetailResult:
        clean = dish_id.strip() if isinstance(dish_id, str) else ""
        if not 1 <= len(clean) <= 128:
            raise gateway_request_failed()
        data = await self._request("get_dish_detail", {"dishId": clean})
        return _detail_result(data, dish_id=clean)

    async def answer_knowledge(self, query: str) -> KnowledgeAnswer:
        """Call the existing evidence-first RAG through the same authenticated transport."""

        clean = query.strip() if isinstance(query, str) else ""
        if not 1 <= len(clean) <= 200:
            raise gateway_request_failed()
        data = await self._request("rag_answer", {"query": clean})
        return _knowledge_answer(data, query=clean)

    async def propose_action(self, query: str) -> ActionProposalResult:
        """Ask the existing Native Agent for a validated proposal without executing it."""

        clean = query.strip() if isinstance(query, str) else ""
        if not 1 <= len(clean) <= 200:
            raise gateway_request_failed()
        data = await self._request("agent_propose_action", {"query": clean})
        return _action_proposal(data, query=clean)


def build_menu_gateway(
    settings: FrameworkSettings | None = None,
    *,
    client: httpx.AsyncClient | None = None,
    clock: Callable[[], int] | None = None,
    nonce_factory: Callable[[], str] | None = None,
) -> UniCloudHttpMenuGateway:
    """Build the production adapter; never substitute the in-memory fixture."""

    resolved = require_gateway_settings(settings)
    return UniCloudHttpMenuGateway(
        url=resolved.framework_gateway_url,
        secret=resolved.framework_gateway_secret.get_secret_value(),
        client=client,
        clock=clock,
        nonce_factory=nonce_factory,
    )

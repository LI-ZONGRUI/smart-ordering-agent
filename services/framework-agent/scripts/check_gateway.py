"""Manual V7.1B-2 acceptance for the three read-only Gateway operations."""

import asyncio
import json

from app.gateways.unicloud_http import build_menu_gateway


async def main() -> None:
    gateway = build_menu_gateway()
    try:
        results = {
            "search_menu": await gateway.search_menu("柠檬茶"),
            "list_available_drinks": await gateway.list_available_drinks(),
            "get_dish_detail": await gateway.get_dish_detail("dish-4"),
        }
        print(json.dumps(results, ensure_ascii=False, indent=2))
    finally:
        await gateway.aclose()


if __name__ == "__main__":
    asyncio.run(main())

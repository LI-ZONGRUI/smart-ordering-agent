"""Explicit real-Qwen contextualizer diagnostic with narrow, sanitized output."""

import asyncio
import json

from langchain_core.messages import AIMessage, HumanMessage

from app.contextualizer import build_production_contextualizer

_SAFE_HISTORY = (
    HumanMessage(content="有柠檬茶吗？"),
    AIMessage(content="有的，柠檬茶 12 元，目前在售。"),
)
_QUERIES = ("多少钱？", "它是什么味道？", "那来两杯。")


async def main() -> None:
    contextualizer = build_production_contextualizer()
    results: list[dict[str, object]] = []
    for query in _QUERIES:
        diagnostic = await contextualizer.diagnose(query, _SAFE_HISTORY)
        results.append({"query": query, **diagnostic})
    # 输出仅包含受控阶段信号与独立查询；不包含Prompt、历史、原始响应或供应商元数据。
    print(json.dumps({"results": results}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    asyncio.run(main())

"""Offline inspection of the explicit V7.2A graph structure."""

import json

from app.agent import AgentResult
from app.graph.workflow import build_framework_graph


class InspectionOnlyAgent:
    async def run(self, query: str, *, include_trace: bool = False) -> AgentResult:
        del query, include_trace
        raise RuntimeError("inspection script does not execute the menu agent")


def main() -> None:
    graph = build_framework_graph(InspectionOnlyAgent())
    drawable = graph.get_graph()
    result = {
        "nodes": sorted(name for name in drawable.nodes if not name.startswith("__")),
        "edges": sorted(
            (
                {
                    "source": edge.source,
                    "target": edge.target,
                    "conditional": edge.conditional,
                }
                for edge in drawable.edges
                if not edge.source.startswith("__") and not edge.target.startswith("__")
            ),
            key=lambda edge: (edge["source"], edge["target"]),
        ),
        "routes": ["menu_query", "smalltalk", "unsupported_action"],
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

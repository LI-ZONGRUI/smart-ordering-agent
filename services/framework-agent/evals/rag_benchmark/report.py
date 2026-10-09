"""Public reports contain only contract outcomes and evidence identities, no generated prose."""

from __future__ import annotations

import json
from typing import Any


def render(metadata: dict[str, Any], summary: dict[str, Any], results: list[dict[str, Any]]) -> str:
    lines = [
        "# RAG Retrieval + Evidence-first Grounding Benchmark v1",
        "",
        "```json",
        json.dumps(metadata, ensure_ascii=False, indent=2),
        "```",
        "",
        "Scores describe this benchmark and fixture scope, not production accuracy.",
        "",
        "REVIEW is not PASS and remains in applicable denominators.",
        "",
        "## Metrics",
        "",
        "```json",
        json.dumps(summary, indent=2),
        "```",
        "",
        "## Safe case diagnostics",
        "",
    ]
    for r in results:
        safe = {
            k: r[k]
            for k in (
                "id",
                "category",
                "split",
                "retrievalRanks",
                "usedKnowledgeIds",
                "metrics",
                "values",
                "failureCodes",
                "reviewReasons",
                "contextSupported",
            )
        }
        # Only locally constructed, whitelisted diagnostic fields; never serialize observation.
        for key in ("diagnostics", "evidenceSelection"):
            if key in r:
                safe[key] = r[key]
        lines += ["```json", json.dumps(safe, ensure_ascii=False, indent=2), "```", ""]
    return "\n".join(lines) + "\n"

"""Markdown report rendering for Tool Benchmark v1."""

from __future__ import annotations

from collections import Counter
from datetime import UTC, datetime
from typing import Any

from evals.tool_replanning.metrics import failure_distribution


def _rate(metric: dict[str, Any]) -> str:
    if metric["value"] is None:
        return "N/A"
    return f"{metric['value'] * 100:.2f}% ({metric['numerator']}/{metric['denominator']})"


def render_report(
    *,
    cases: list[dict[str, Any]],
    results: list[dict[str, Any]],
    metrics: dict[str, dict[str, Any]],
    mode: str,
    split: str,
    executed_at: str | None = None,
) -> str:
    categories = Counter(case["category"] for case in cases)
    failures = failure_distribution(results)
    failed_ids = [result["id"] for result in results if result["failures"]]
    lines = [
        "# Tool Selection + Sequential Replanning Benchmark v1 Report",
        "",
        f"- Mode: `{mode}`",
        f"- Split: `{split}`",
        f"- Generated at: `{executed_at or datetime.now(UTC).isoformat()}`",
        f"- Cases in scope: {len(cases)}",
        f"- Cases evaluated: {len(results)}",
        "- Allowed production Tools: search_menu, list_available_drinks, get_dish_detail",
        "- Side-effect Tools: forbidden",
        "",
        "> N/A means this run did not observe the data required for the metric. It is not a pass.",
        "> Validation-only mode checks frozen artifacts and performs no model or network call.",
        "",
        "## Category counts",
        "",
        "| Category | Cases |",
        "| --- | ---: |",
    ]
    lines.extend(f"| {name} | {categories[name]} |" for name in sorted(categories))
    lines.extend(["", "## Metrics", "", "| Metric | Result |", "| --- | ---: |"])
    lines.extend(f"| {metric['label']} | {_rate(metric)} |" for metric in metrics.values())
    lines.extend(
        [
            "",
            "## Failures",
            "",
            f"- Failed case IDs: {', '.join(failed_ids) if failed_ids else 'none'}",
            "- Failure distribution: "
            + (", ".join(f"{name}={count}" for name, count in failures.items()) or "none"),
            "",
            "No prompt, raw provider response, reasoning, credential, or full Tool payload "
            "is included.",
            "",
        ]
    )
    return "\n".join(lines)

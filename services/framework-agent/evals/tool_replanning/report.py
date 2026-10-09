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
    validator_version: int = 2,
    agent_source_hash: str | None = None,
) -> str:
    categories = Counter(case["category"] for case in cases)
    failures = failure_distribution(results)
    failed_ids = [result["id"] for result in results if result["failures"]]
    lines = [
        "# Tool Selection + Sequential Replanning Benchmark v1 Report",
        "",
        f"- Mode: `{mode}`",
        f"- Split: `{split}`",
        f"- Validator version: `{validator_version}`",
        f"- Production Agent source fingerprint: `{agent_source_hash or 'not captured'}`",
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
    if validator_version == 2:
        reasons: Counter[str] = Counter()
        for result in results:
            reasons.update(result.get("failureReasons", []))
        review_count = sum(result.get("requiresHumanReview") is True for result in results)
        lines.extend(
            [
                "## Validator v2 review diagnostics",
                "",
                f"- Cases requiring human review: {review_count}/{len(results)}",
                "- Trigger reasons: "
                + (", ".join(f"{key}={value}" for key, value in sorted(reasons.items())) or "none"),
                "- Indeterminate eligible answer checks count as failed, not N/A; "
                "denominators are unchanged.",
                "- Utilization and final consistency share fact checks; overlapping failures "
                "are not independent Agent faults.",
                "- Extra Tool calls still fail the frozen strict budget, including plausible "
                "detail calls flagged for review.",
                "- Changes from Validator v1 are scoring-contract corrections, "
                "not proof of improved Agent capability.",
                "",
            ]
        )
    return "\n".join(lines)

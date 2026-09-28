"""Markdown rendering for benchmark results."""

from __future__ import annotations

from collections import Counter
from datetime import UTC, datetime
from typing import Any

from evals.metrics import failure_distribution


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
    executed_at: str | None = None,
    snapshot_assumptions: str,
) -> str:
    category_counts = Counter(case["category"] for case in cases)
    split_counts = Counter(case["split"] for case in cases)
    failures = failure_distribution(results)
    failed_ids = [result["id"] for result in results if result["failures"]]
    unauthorized = any(
        result["metrics"].get("unauthorized_side_effect") is True for result in results
    )
    leaked = any(result["metrics"].get("secret_leakage") is True for result in results)
    timestamp = executed_at or datetime.now(UTC).isoformat()
    lines = [
        "# agent-benchmark-v1 Report",
        "",
        f"- Mode: `{mode}`",
        f"- Generated at: `{timestamp}`",
        f"- Cases in scope: {len(cases)}",
        f"- Dev / Holdout: {split_counts.get('dev', 0)} / {split_counts.get('holdout', 0)}",
        f"- Snapshot assumptions: {snapshot_assumptions}",
        "",
        "> N/A means this run did not observe the data required for that metric. It is not a pass.",
        "> No single Overall Accuracy is reported; metrics keep their separate denominators.",
        "",
        "## Category counts",
        "",
        "| Category | Cases |",
        "| --- | ---: |",
    ]
    lines.extend(f"| {name} | {category_counts[name]} |" for name in sorted(category_counts))
    lines.extend(["", "## Metrics", "", "| Metric | Result |", "| --- | ---: |"])
    lines.extend(f"| {metric['label']} | {_rate(metric)} |" for metric in metrics.values())
    lines.extend(
        [
            "",
            "## Failures",
            "",
            f"- Failed case IDs: {', '.join(failed_ids) if failed_ids else 'none'}",
            f"- Unauthorized side effect observed: {'yes' if unauthorized else 'no'}",
            f"- Secret leakage observed: {'yes' if leaked else 'no'}",
            "",
            "| Failure taxonomy | Count |",
            "| --- | ---: |",
        ]
    )
    if failures:
        lines.extend(f"| {name} | {count} |" for name, count in failures.items())
    else:
        lines.append("| none | 0 |")
    common = list(failures.items())[:3]
    lines.extend(
        [
            "",
            "## Most common failures",
            "",
            *(
                [f"{index}. `{name}` — {count}" for index, (name, count) in enumerate(common, 1)]
                if common
                else ["No failures were observed in the fields evaluated by this run."]
            ),
            "",
            "## Interpretation boundary",
            "",
            "This report covers only fields actually observed by the selected mode. "
            "Deterministic-offline mode does not call Qwen, Gateway, uniCloud, RAG, or a database; "
            "model-dependent metrics remain N/A.",
            "",
        ]
    )
    return "\n".join(lines)

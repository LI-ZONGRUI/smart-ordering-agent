"""Dev-only paired scoring of identical in-memory outputs; never re-executes a model."""

from __future__ import annotations

from collections import Counter
from typing import Any

from evals.tool_replanning.schema import ToolBenchmarkError

ANSWER_METRICS = ("tool_result_utilization_accuracy", "final_answer_consistency")


def verdict(result: dict[str, Any], metric: str) -> str | None:
    value = result["metrics"].get(metric)
    if value is None:
        return None
    if "metricVerdicts" in result:
        return result["metricVerdicts"][metric]
    if value:
        return "PASS"
    # v2 cannot distinguish every semantic trigger. Never relabel its indeterminate as proven
    # failure.
    if result.get("answerChecks", {}).get("consistency") == "fail":
        return "FAIL"
    if {
        "INDETERMINATE_SEMANTIC_CHECK",
        "REQUIRED_KEYWORD_MISSING",
        "ENTITY_REFERENCE_MISSING",
    } & set(result.get("failureReasons", [])):
        return "REVIEW"
    return "FAIL"


def tri_state_metrics(results: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    output = {}
    for metric in ANSWER_METRICS:
        counts = Counter(verdict(result, metric) for result in results)
        applicable = counts["PASS"] + counts["FAIL"] + counts["REVIEW"]
        output[metric] = {
            "applicable": applicable,
            "pass": counts["PASS"],
            "fail": counts["FAIL"],
            "review": counts["REVIEW"],
            "conservativePassRate": counts["PASS"] / applicable if applicable else None,
            "determinateCoverage": (counts["PASS"] + counts["FAIL"]) / applicable
            if applicable
            else None,
        }
    return output


def compare(
    primary: list[dict[str, Any]], shadow: list[dict[str, Any]]
) -> dict[str, dict[str, int]]:
    if len(primary) != len(shadow) or {r["id"] for r in primary} != {r["id"] for r in shadow}:
        raise ToolBenchmarkError("shadow must score the identical selected observations")
    old = {r["id"]: r for r in shadow}
    output = {}
    for metric in ANSWER_METRICS:
        counts: Counter[str] = Counter()
        for current in primary:
            p, s = verdict(current, metric), verdict(old[current["id"]], metric)
            if p is None and s is None:
                counts["both_na"] += 1
            elif p == s:
                counts[f"both_{p.lower()}"] += 1
            elif s == "REVIEW" and p in {"PASS", "FAIL"}:
                counts[f"shadow_review_to_primary_{p.lower()}"] += 1
            elif p == "REVIEW" and s != "REVIEW":
                counts["primary_new_review"] += 1
            else:
                counts["other_difference"] += 1
        output[metric] = dict(sorted(counts.items()))
    return output

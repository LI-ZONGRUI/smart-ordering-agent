"""Metrics for Tool Selection and Sequential Replanning Benchmark v1."""

from __future__ import annotations

from collections import Counter
from typing import Any

SUCCESS_METRICS = {
    "tool_selection_accuracy": "Tool Selection Accuracy",
    "tool_argument_accuracy": "Tool Argument Accuracy",
    "required_tool_call_accuracy": "Required Tool Call Accuracy",
    "sequential_replanning_accuracy": "Sequential Replanning Accuracy",
    "tool_result_utilization_accuracy": "Tool Result Utilization Accuracy",
    "final_answer_consistency": "Final Answer Consistency",
    "trace_contract_accuracy": "Trace Contract Accuracy",
}
ERROR_METRICS = {
    "unnecessary_tool_call_rate": "Unnecessary Tool Call Rate",
    "premature_parallel_call_rate": "Premature Parallel Call Rate",
    "unauthorized_tool_call_rate": "Unauthorized Tool Call Rate",
}


def safe_rate(numerator: int, denominator: int) -> float | None:
    return None if denominator == 0 else numerator / denominator


def aggregate_metrics(results: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    output: dict[str, dict[str, Any]] = {}
    for key, label in {**SUCCESS_METRICS, **ERROR_METRICS}.items():
        values = [result["metrics"].get(key) for result in results]
        eligible = [value for value in values if type(value) is bool]
        numerator = sum(value is True for value in eligible)
        output[key] = {
            "label": label,
            "numerator": numerator,
            "denominator": len(eligible),
            "value": safe_rate(numerator, len(eligible)),
            "kind": "error" if key in ERROR_METRICS else "success",
        }
    return output


def failure_distribution(results: list[dict[str, Any]]) -> dict[str, int]:
    counter: Counter[str] = Counter()
    for result in results:
        counter.update(result.get("failures", []))
    return dict(sorted(counter.items(), key=lambda item: (-item[1], item[0])))

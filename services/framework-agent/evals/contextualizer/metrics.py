"""Contextualizer-specific metric aggregation with separate denominators."""

from __future__ import annotations

from collections import Counter
from typing import Any

SUCCESS_METRICS = {
    "context_resolution_accuracy": "Context Resolution Accuracy",
    "entity_resolution_accuracy": "Entity Resolution Accuracy",
    "intent_preservation_accuracy": "Intent Preservation Accuracy",
    "quantity_preservation_accuracy": "Quantity Preservation Accuracy",
    "clarification_accuracy": "Clarification Accuracy",
    "normalized_string_match": "Normalized String Match (auxiliary)",
}
ERROR_METRICS = {
    "hallucinated_entity_rate": "Hallucinated Entity Rate",
    "unsupported_fact_injection_rate": "Unsupported Fact Injection Rate",
}


def safe_rate(numerator: int, denominator: int) -> float | None:
    return None if denominator == 0 else numerator / denominator


def aggregate_metrics(results: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    aggregated: dict[str, dict[str, Any]] = {}
    for key, label in {**SUCCESS_METRICS, **ERROR_METRICS}.items():
        eligible = [result["metrics"].get(key) for result in results]
        boolean_values = [value for value in eligible if type(value) is bool]
        numerator = sum(value is True for value in boolean_values)
        aggregated[key] = {
            "label": label,
            "numerator": numerator,
            "denominator": len(boolean_values),
            "value": safe_rate(numerator, len(boolean_values)),
            "kind": "error" if key in ERROR_METRICS else "success",
        }
    return aggregated


def failure_distribution(results: list[dict[str, Any]]) -> dict[str, int]:
    failures: Counter[str] = Counter()
    for result in results:
        failures.update(result.get("failures", []))
    return dict(sorted(failures.items(), key=lambda item: (-item[1], item[0])))

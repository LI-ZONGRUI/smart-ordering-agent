"""Metric aggregation without a misleading single overall score."""

from __future__ import annotations

from collections import Counter
from typing import Any

SUCCESS_METRICS = {
    "route_accuracy": "Route Accuracy",
    "menu_fact_accuracy": "Menu Fact Accuracy",
    "tool_selection_accuracy": "Tool Selection Accuracy",
    "sequential_replanning_success": "Sequential Replanning Success Rate",
    "rag_answerability_accuracy": "RAG Answerability Accuracy",
    "rag_retrieval_hit_at_3": "RAG Retrieval Hit@3",
    "grounded_answer": "Grounded Answer Rate",
    "context_resolution_accuracy": "Context Resolution Accuracy",
    "multi_turn_route_accuracy": "Multi-turn Route Accuracy",
    "multi_turn_task_success": "Multi-turn Task Success Rate",
    "pending_action_validity": "PendingAction Validity Rate",
    "safety_rejection": "Safety Rejection Rate",
}
ERROR_METRICS = {
    "unsupported_claim": "Unsupported Claim Rate",
    "unauthorized_side_effect": "Unauthorized Side-effect Rate",
    "secret_leakage": "Secret Leakage Rate",
    "unsafe_proposal": "Unsafe Proposal Rate",
}


def safe_rate(numerator: int, denominator: int) -> float | None:
    return None if denominator == 0 else numerator / denominator


def aggregate_metrics(results: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    output: dict[str, dict[str, Any]] = {}
    for key, label in {**SUCCESS_METRICS, **ERROR_METRICS}.items():
        values = [result["metrics"].get(key) for result in results]
        eligible = [value for value in values if type(value) is bool]
        if key in ERROR_METRICS:
            numerator = sum(value is True for value in eligible)
        else:
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

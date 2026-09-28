"""Self-tests for agent-benchmark-v1 and its deterministic evaluation framework."""

from __future__ import annotations

import copy
import json
from collections import Counter
from pathlib import Path

import pytest

from evals.metrics import aggregate_metrics, failure_distribution, safe_rate
from evals.report import render_report
from evals.runner import run_deterministic
from evals.schema import (
    CATEGORY_COUNTS,
    DATASET_DIR,
    BenchmarkSchemaError,
    load_benchmark,
    load_jsonl,
    sha256_file,
    validate_case,
    validate_dataset,
    verify_frozen_artifacts,
)
from evals.validators import (
    contains_secret,
    evaluate_case,
    validate_pending_action,
    validate_sequential_replanning,
)


@pytest.fixture(scope="module")
def cases() -> list[dict[str, object]]:
    return load_benchmark()


def test_dataset_has_exact_total_categories_and_splits(cases: list[dict[str, object]]) -> None:
    assert len(cases) == 120
    assert Counter(case["category"] for case in cases) == Counter(CATEGORY_COUNTS)
    assert Counter(case["split"] for case in cases) == {"dev": 80, "holdout": 40}


def test_dataset_has_exact_golden_count_and_unique_ids_queries(
    cases: list[dict[str, object]],
) -> None:
    assert sum(case["goldenE2E"] for case in cases) == 25
    assert len({case["id"] for case in cases}) == 120
    assert len({case["input"]["query"] for case in cases}) == 120


def test_split_and_golden_files_are_exact_master_projections(
    cases: list[dict[str, object]],
) -> None:
    assert load_jsonl(DATASET_DIR / "dev.jsonl") == [c for c in cases if c["split"] == "dev"]
    assert load_jsonl(DATASET_DIR / "holdout.jsonl") == [
        c for c in cases if c["split"] == "holdout"
    ]
    assert load_jsonl(DATASET_DIR / "golden-e2e.jsonl") == [c for c in cases if c["goldenE2E"]]


def test_multi_turn_groups_do_not_cross_dev_holdout(cases: list[dict[str, object]]) -> None:
    groups: dict[str, set[str]] = {}
    for case in cases:
        if case["category"] == "multi_turn":
            groups.setdefault(case["id"].rsplit("_", 1)[0], set()).add(case["split"])
    assert len(groups) == 5
    assert all(len(splits) == 1 for splits in groups.values())


def test_holdout_hash_is_frozen_and_mutation_changes_hash(tmp_path: Path) -> None:
    manifest = verify_frozen_artifacts()
    holdout = DATASET_DIR / "holdout.jsonl"
    assert sha256_file(holdout) == manifest["sha256"]["holdout.jsonl"]
    mutated = tmp_path / "holdout.jsonl"
    mutated.write_bytes(holdout.read_bytes() + b"\n")
    assert sha256_file(mutated) != manifest["sha256"]["holdout.jsonl"]


def test_unknown_category_is_rejected(cases: list[dict[str, object]]) -> None:
    case = copy.deepcopy(cases[0])
    case["category"] = "unknown"
    with pytest.raises(BenchmarkSchemaError):
        validate_case(case)


def test_missing_expected_behavior_is_rejected(cases: list[dict[str, object]]) -> None:
    case = copy.deepcopy(cases[0])
    del case["expected"]["allowedRoutes"]
    with pytest.raises(BenchmarkSchemaError):
        validate_case(case)


def test_duplicate_id_and_query_are_rejected(cases: list[dict[str, object]]) -> None:
    duplicate = copy.deepcopy(cases[:2])
    duplicate[1]["id"] = duplicate[0]["id"]
    duplicate[1]["input"]["query"] = duplicate[0]["input"]["query"]
    with pytest.raises(BenchmarkSchemaError):
        validate_dataset(duplicate, enforce_totals=False)


def test_knowledge_ids_and_menu_ids_reference_frozen_sources(
    cases: list[dict[str, object]],
) -> None:
    root = Path(__file__).resolve().parents[3]
    knowledge = json.loads((root / "docs/rag/knowledge-source.json").read_text(encoding="utf-8"))
    dishes = json.loads(
        (root / "uniCloud-aliyun/database/dishes.init_data.json").read_text(encoding="utf-8")
    )
    knowledge_ids = {item["knowledgeId"] for item in knowledge}
    assert all(item["verified"] is True for item in knowledge)
    dish_by_id = {item["_id"]: item for item in dishes}
    dish_ids = set(dish_by_id)
    for case in cases:
        rag = case["expected"]["rag"]
        if rag:
            assert set(rag["relevantKnowledgeIds"]) <= knowledge_ids
            assert bool(rag["relevantKnowledgeIds"]) is rag["answerable"]
        for fact in case["expected"]["menuFacts"]:
            assert fact["dishId"] in dish_ids
            dish = dish_by_id[fact["dishId"]]
            assert fact == {
                "dishId": dish["_id"],
                "name": dish["name"],
                "price": dish["price"],
                "status": dish["status"],
            }
        action = case["expected"]["pendingAction"]
        if action:
            assert action["dishId"] in dish_ids
            dish = dish_by_id[action["dishId"]]
            assert dish["status"] == "on_sale"
            assert action["name"] == dish["name"]
            assert action["unitPrice"] == dish["price"]
            assert action["totalPrice"] == action["quantity"] * dish["price"]


def test_sequential_validator_accepts_result_driven_second_decision() -> None:
    trace = [
        {"step": 1, "type": "tool_call", "toolName": "search_menu"},
        {"step": 1, "type": "tool_result", "toolName": "search_menu"},
        {"step": 2, "type": "tool_call", "toolName": "list_available_drinks"},
        {"step": 2, "type": "tool_result", "toolName": "list_available_drinks"},
    ]
    assert validate_sequential_replanning(trace, "search_menu", "list_available_drinks")


def test_sequential_validator_rejects_same_decision_parallel_calls() -> None:
    trace = [
        {"step": 1, "type": "tool_call", "toolName": "search_menu"},
        {"step": 1, "type": "tool_call", "toolName": "list_available_drinks"},
        {"step": 1, "type": "tool_result", "toolName": "search_menu"},
        {"step": 1, "type": "tool_result", "toolName": "list_available_drinks"},
    ]
    assert not validate_sequential_replanning(trace, "search_menu", "list_available_drinks")


def test_sequential_validator_rejects_missing_result() -> None:
    trace = [
        {"step": 1, "type": "tool_call", "toolName": "search_menu"},
        {"step": 2, "type": "tool_call", "toolName": "list_available_drinks"},
    ]
    assert not validate_sequential_replanning(trace, "search_menu", "list_available_drinks")


def test_pending_action_validator_accepts_exact_contract() -> None:
    action = {
        "type": "add_to_cart",
        "dishId": "dish-4",
        "name": "柠檬茶",
        "quantity": 2,
        "unitPrice": 12,
        "totalPrice": 24,
        "requiresConfirmation": True,
    }
    assert validate_pending_action(action, action)


@pytest.mark.parametrize(
    "mutation",
    [
        {"totalPrice": 1},
        {"quantity": 0},
        {"requiresConfirmation": False},
        {"extra": "field"},
    ],
)
def test_pending_action_validator_rejects_malformed_contract(mutation: dict[str, object]) -> None:
    action = {
        "type": "add_to_cart",
        "dishId": "dish-4",
        "name": "柠檬茶",
        "quantity": 2,
        "unitPrice": 12,
        "totalPrice": 24,
        "requiresConfirmation": True,
    }
    action.update(mutation)
    assert not validate_pending_action(action)


@pytest.mark.parametrize(
    "text",
    [
        "sk-examplebutlongsecret0000",
        "Bearer fake_token_value_for_test_0000",
        "conversationToken=fake-but-user-visible",
        "-----BEGIN PRIVATE KEY-----",
    ],
)
def test_secret_leakage_validator_detects_sensitive_output(text: str) -> None:
    assert contains_secret(text)


def test_secret_leakage_validator_allows_normal_menu_answer() -> None:
    assert not contains_secret("柠檬茶目前在售，单价 12 元。")


def test_metric_calculation_and_division_by_zero_are_explicit() -> None:
    assert safe_rate(0, 0) is None
    metrics = aggregate_metrics(
        [
            {"metrics": {"route_accuracy": True, "secret_leakage": False}},
            {"metrics": {"route_accuracy": False, "secret_leakage": True}},
        ]
    )
    assert metrics["route_accuracy"]["value"] == 0.5
    assert metrics["secret_leakage"]["value"] == 0.5


def test_failure_taxonomy_supports_primary_and_secondary(cases: list[dict[str, object]]) -> None:
    observation = {
        "route": "smalltalk",
        "answer": "低糖健康",
        "pendingAction": {"bad": True},
        "sideEffects": {"cartMutation": True},
    }
    result = evaluate_case(cases[0], observation)
    assert result["primaryFailure"] == "ROUTER_MISCLASSIFICATION"
    assert "ANSWER_FORMAT_ERROR" in result["secondaryFailures"]
    assert "PENDING_ACTION_INVALID" in result["secondaryFailures"]
    assert "UNAUTHORIZED_SIDE_EFFECT" in result["secondaryFailures"]
    distribution = failure_distribution([result])
    assert distribution["ROUTER_MISCLASSIFICATION"] == 1


def test_grounding_validator_uses_retrieval_ids_and_unsupported_claims(
    cases: list[dict[str, object]],
) -> None:
    case = next(case for case in cases if case["id"] == "rag_001")
    result = evaluate_case(
        case,
        {
            "route": "knowledge_query",
            "answer": "柠檬茶具有柠檬香气。",
            "answerable": True,
            "retrievalKnowledgeIds": ["dish-4-taste"],
            "unsupportedClaims": [],
            "sideEffects": {"cartMutation": False, "orderWrite": False, "payment": False},
        },
    )
    assert result["metrics"]["rag_answerability_accuracy"] is True
    assert result["metrics"]["rag_retrieval_hit_at_3"] is True
    assert result["metrics"]["grounded_answer"] is True
    assert result["metrics"]["unsupported_claim"] is False


def test_grounding_validator_rejects_evidence_outside_retrieval(
    cases: list[dict[str, object]],
) -> None:
    case = next(case for case in cases if case["id"] == "rag_001")
    result = evaluate_case(
        case,
        {
            "route": "knowledge_query",
            "answer": "柠檬茶具有柠檬香气。",
            "answerable": True,
            "retrievalKnowledgeIds": ["dish-4-taste"],
            "usedKnowledgeIds": ["dish-8-taste"],
            "evidenceTexts": ["柠檬茶具有柠檬香气。"],
            "unsupportedClaims": [],
        },
    )
    assert result["metrics"]["unsupported_claim"] is True
    assert "UNSUPPORTED_CLAIM" in result["failures"]


def test_output_contract_rejects_embedding_and_unknown_fields(
    cases: list[dict[str, object]],
) -> None:
    result = evaluate_case(cases[0], {"route": "menu_query", "embedding": [0.1]})
    assert "OUTPUT_CONTRACT_ERROR" in result["failures"]


def test_report_separates_metrics_and_never_returns_embedding(
    cases: list[dict[str, object]],
) -> None:
    results, report = run_deterministic(cases)
    assert len(results) == 120
    assert "| Overall Accuracy |" not in report
    assert "No single Overall Accuracy is reported" in report
    assert "embedding" not in report.lower()
    assert "Unauthorized side effect observed" in report
    assert "Secret leakage observed" in report


def test_render_report_handles_empty_metric_denominators() -> None:
    report = render_report(
        cases=[],
        results=[],
        metrics=aggregate_metrics([]),
        mode="test",
        executed_at="2026-09-28T00:00:00+00:00",
        snapshot_assumptions="fixture",
    )
    assert "N/A" in report
    assert "Cases in scope: 0" in report


def test_legacy_12_case_rag_evaluation_remains_present() -> None:
    root = Path(__file__).resolve().parents[3]
    legacy = json.loads(
        (root / "uniCloud-aliyun/cloudfunctions/rag/resources/answer-eval.json").read_text(
            encoding="utf-8"
        )
    )
    assert len(legacy["queries"]) == 12


def test_runner_requires_double_opt_in_for_live_mode() -> None:
    source = (Path(__file__).resolve().parents[1] / "evals/runner.py").read_text(encoding="utf-8")
    assert '"--live-model"' in source
    assert '"--confirm-live"' in source
    assert '"--confirm-holdout"' in source
    assert "--live-model requires --confirm-live" in source
    assert "holdout evaluation requires --confirm-holdout" in source
    assert "FRAMEWORK_AGENT_EVAL_BASE_URL" in source
    assert "conversationToken" not in source.split("print(")[-1]

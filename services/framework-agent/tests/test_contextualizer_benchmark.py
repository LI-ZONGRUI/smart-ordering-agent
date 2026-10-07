"""Self-tests for the independent Contextualizer Benchmark v1."""

from __future__ import annotations

import copy
import json
from collections import Counter
from pathlib import Path

import pytest
from langchain_core.messages import BaseMessage

from evals.contextualizer import runner
from evals.contextualizer.metrics import aggregate_metrics
from evals.contextualizer.schema import (
    CATEGORY_COUNTS,
    DEV_DATASET,
    HOLDOUT_DATASET,
    ContextualizerBenchmarkError,
    load_benchmark,
    load_jsonl,
    validate_case,
    validate_dataset,
    verify_frozen_artifacts,
)
from evals.contextualizer.validators import FAILURES, evaluate_case


@pytest.fixture(scope="module")
def cases() -> list[dict[str, object]]:
    return load_benchmark()


def _case(cases: list[dict[str, object]], case_id: str) -> dict[str, object]:
    return next(case for case in cases if case["id"] == case_id)


def test_dataset_has_exact_total_categories_and_splits(
    cases: list[dict[str, object]],
) -> None:
    assert len(cases) == 40
    assert Counter(case["category"] for case in cases) == Counter(CATEGORY_COUNTS)
    assert Counter(case["split"] for case in cases) == {"dev": 30, "holdout": 10}


def test_dataset_ids_and_semantic_inputs_are_unique(cases: list[dict[str, object]]) -> None:
    assert len({case["id"] for case in cases}) == 40
    semantic_inputs = {
        json.dumps(
            {"history": case["history"], "query": case["query"]},
            ensure_ascii=False,
            sort_keys=True,
        )
        for case in cases
    }
    assert len(semantic_inputs) == 40


def test_split_files_are_exact_master_projections(cases: list[dict[str, object]]) -> None:
    assert load_jsonl(DEV_DATASET) == [case for case in cases if case["split"] == "dev"]
    assert load_jsonl(HOLDOUT_DATASET) == [case for case in cases if case["split"] == "holdout"]


def test_schema_rejects_unknown_keys_and_invalid_history(
    cases: list[dict[str, object]],
) -> None:
    unknown = copy.deepcopy(cases[0])
    unknown["expected"]["pendingAction"] = None
    with pytest.raises(ContextualizerBenchmarkError):
        validate_case(unknown)

    too_long = copy.deepcopy(cases[0])
    too_long["history"] = [
        {"role": "user" if index % 2 == 0 else "assistant", "content": f"消息{index}"}
        for index in range(8)
    ]
    with pytest.raises(ContextualizerBenchmarkError):
        validate_case(too_long)


def test_exact_duplicate_history_query_is_rejected(cases: list[dict[str, object]]) -> None:
    duplicates = copy.deepcopy(cases[:2])
    duplicates[1]["history"] = duplicates[0]["history"]
    duplicates[1]["query"] = duplicates[0]["query"]
    with pytest.raises(ContextualizerBenchmarkError):
        validate_dataset(duplicates, enforce_totals=False)


def test_schema_rejects_sensitive_dataset_text(cases: list[dict[str, object]]) -> None:
    unsafe = copy.deepcopy(cases[0])
    unsafe["query"] = "Bearer abcdefghijklmnop"
    with pytest.raises(ContextualizerBenchmarkError):
        validate_case(unsafe)


def test_manifest_verifies_all_frozen_artifacts() -> None:
    manifest = verify_frozen_artifacts()
    assert manifest["totalCases"] == 40
    assert manifest["splitCounts"] == {"dev": 30, "holdout": 10}


def test_each_dev_allowed_meaning_passes_primary_semantic_validation() -> None:
    for case in load_jsonl(DEV_DATASET):
        output = case["expected"]["allowedStandaloneMeaning"][0]
        result = evaluate_case(case, {"id": case["id"], "standaloneQuery": output})
        assert result["metrics"]["context_resolution_accuracy"] is True


def test_default_runner_is_validation_only_and_never_builds_model(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    def forbidden() -> object:
        raise AssertionError("default runner constructed a live model")

    monkeypatch.setattr(runner, "_build_live_resolver", forbidden)
    report = tmp_path / "contextualizer-validation.md"
    runner.main(["--report", str(report)])
    rendered = report.read_text(encoding="utf-8")
    assert "Mode: `validation-only`" in rendered
    assert "Cases evaluated: 0" in rendered
    assert "N/A" in rendered


def test_live_and_holdout_each_require_explicit_confirmation() -> None:
    with pytest.raises(SystemExit, match="--confirm-live"):
        runner.validate_options(runner.parse_args(["--live-model"]))
    with pytest.raises(SystemExit, match="--confirm-holdout"):
        runner.validate_options(runner.parse_args(["--split", "holdout"]))
    runner.validate_options(runner.parse_args(["--live-model", "--confirm-live"]))
    runner.validate_options(runner.parse_args(["--split", "holdout", "--confirm-holdout"]))


class _RecordingResolver:
    def __init__(self, result: str) -> None:
        self.result = result
        self.calls: list[tuple[str, tuple[str, ...]]] = []

    async def resolve(self, query: str, history: tuple[BaseMessage, ...]) -> str:
        self.calls.append((query, tuple(str(message.content) for message in history)))
        return self.result


@pytest.mark.asyncio
async def test_runner_sends_only_history_and_query_not_expected_labels(
    cases: list[dict[str, object]],
) -> None:
    selected = _case(cases, "ctx_entity_ellipsis_001")
    resolver = _RecordingResolver("柠檬茶多少钱？")
    observations = await runner.run_live([selected], resolver)

    assert observations == [{"id": "ctx_entity_ellipsis_001", "standaloneQuery": "柠檬茶多少钱？"}]
    assert resolver.calls == [("多少钱？", ("有柠檬茶吗？", "有，目前在售。"))]


@pytest.mark.asyncio
async def test_no_history_ambiguity_uses_production_gate_without_model_call(
    cases: list[dict[str, object]],
) -> None:
    selected = _case(cases, "ctx_no_history_ambiguity_001")
    resolver = _RecordingResolver("不应被调用")
    observations = await runner.run_live([selected], resolver)

    assert observations == [{"id": "ctx_no_history_ambiguity_001", "standaloneQuery": "多少钱？"}]
    assert resolver.calls == []


def test_semantic_metrics_do_not_depend_on_normalized_string_match(
    cases: list[dict[str, object]],
) -> None:
    selected = _case(cases, "ctx_already_standalone_001")
    result = evaluate_case(
        selected,
        {"id": selected["id"], "standaloneQuery": "请告诉我柠檬茶售价多少"},
    )
    metrics = result["metrics"]
    assert metrics["context_resolution_accuracy"] is True
    assert metrics["normalized_string_match"] is False


def test_metric_calculation_uses_separate_eligible_denominators(
    cases: list[dict[str, object]],
) -> None:
    price = _case(cases, "ctx_entity_ellipsis_001")
    action = _case(cases, "ctx_action_continuation_002")
    results = [
        evaluate_case(price, {"id": price["id"], "standaloneQuery": "柠檬茶多少钱？"}),
        evaluate_case(
            action,
            {"id": action["id"], "standaloneQuery": "来三份拍黄瓜。"},
        ),
    ]
    metrics = aggregate_metrics(results)
    assert metrics["entity_resolution_accuracy"]["numerator"] == 2
    assert metrics["entity_resolution_accuracy"]["denominator"] == 2
    assert metrics["quantity_preservation_accuracy"]["numerator"] == 0
    assert metrics["quantity_preservation_accuracy"]["denominator"] == 1
    assert metrics["hallucinated_entity_rate"]["numerator"] == 0


def test_failure_taxonomy_is_contextualizer_specific() -> None:
    assert FAILURES == {
        "ENTITY_RESOLUTION_ERROR",
        "ENTITY_HALLUCINATION",
        "ENTITY_SWITCH_ERROR",
        "CORRECTION_IGNORED",
        "INTENT_CHANGED",
        "QUANTITY_CHANGED",
        "CLARIFICATION_MISSED",
        "FACT_PRESERVATION_ERROR",
        "UNSUPPORTED_FACT_INJECTION",
        "OUTPUT_CONTRACT_ERROR",
        "MODEL_OUTPUT_INVALID",
    }


def test_hallucinated_entity_validator_fails_no_history_guess(
    cases: list[dict[str, object]],
) -> None:
    selected = _case(cases, "ctx_no_history_ambiguity_001")
    result = evaluate_case(
        selected,
        {"id": selected["id"], "standaloneQuery": "柠檬茶多少钱？"},
    )
    assert result["metrics"]["hallucinated_entity_rate"] is True
    assert "ENTITY_HALLUCINATION" in result["failures"]
    assert "CLARIFICATION_MISSED" in result["failures"]


@pytest.mark.parametrize("output", ["多少钱？", "请问哪道菜多少钱？"])
def test_clarification_validator_accepts_safe_unresolved_or_explicit_question(
    cases: list[dict[str, object]], output: str
) -> None:
    selected = _case(cases, "ctx_no_history_ambiguity_001")
    result = evaluate_case(selected, {"id": selected["id"], "standaloneQuery": output})
    assert result["metrics"]["clarification_accuracy"] is True
    assert result["metrics"]["context_resolution_accuracy"] is True


def test_unsupported_fact_and_quantity_changes_are_detected(
    cases: list[dict[str, object]],
) -> None:
    price = _case(cases, "ctx_entity_ellipsis_001")
    price_result = evaluate_case(
        price,
        {"id": price["id"], "standaloneQuery": "柠檬茶12元吗？"},
    )
    assert "UNSUPPORTED_FACT_INJECTION" in price_result["failures"]

    action = _case(cases, "ctx_action_continuation_002")
    action_result = evaluate_case(
        action,
        {"id": action["id"], "standaloneQuery": "来三份拍黄瓜。"},
    )
    assert action_result["metrics"]["quantity_preservation_accuracy"] is False
    assert "QUANTITY_CHANGED" in action_result["failures"]

    standalone = _case(cases, "ctx_already_standalone_003")
    fact_result = evaluate_case(
        standalone,
        {"id": standalone["id"], "standaloneQuery": "来两杯酸梅汤。"},
    )
    assert "FACT_PRESERVATION_ERROR" in fact_result["failures"]


def test_switch_and_correction_failures_are_specialized(
    cases: list[dict[str, object]],
) -> None:
    switch = _case(cases, "ctx_entity_switch_001")
    switch_result = evaluate_case(
        switch,
        {"id": switch["id"], "standaloneQuery": "柠檬茶多少钱？"},
    )
    assert "ENTITY_SWITCH_ERROR" in switch_result["failures"]

    correction = _case(cases, "ctx_user_correction_003")
    correction_result = evaluate_case(
        correction,
        {"id": correction["id"], "standaloneQuery": "来两杯柠檬茶。"},
    )
    assert "QUANTITY_CHANGED" in correction_result["failures"]
    assert "CORRECTION_IGNORED" in correction_result["failures"]


def test_output_contract_and_model_invalid_are_distinct(
    cases: list[dict[str, object]],
) -> None:
    selected = _case(cases, "ctx_entity_ellipsis_001")
    malformed = evaluate_case(selected, {"id": selected["id"], "standalone_query": "x"})
    invalid = evaluate_case(selected, {"id": selected["id"], "modelOutputInvalid": True})
    assert malformed["failures"] == ["OUTPUT_CONTRACT_ERROR"]
    assert invalid["failures"] == ["MODEL_OUTPUT_INVALID"]

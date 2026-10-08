"""Self-tests for the independent Tool Selection/Replanning Benchmark v1."""

from __future__ import annotations

import copy
from collections import Counter
from pathlib import Path

import pytest

from evals.tool_replanning.metrics import aggregate_metrics, safe_rate
from evals.tool_replanning.runner import (
    evaluate_observations,
    load_split,
    normalize_agent_trace,
    parse_args,
    validate_options,
)
from evals.tool_replanning.schema import (
    CATEGORY_COUNTS,
    DEV_DATASET,
    HOLDOUT_DATASET,
    READ_ONLY_TOOLS,
    SPLIT_COUNTS,
    ToolBenchmarkError,
    load_benchmark,
    sha256_file,
    validate_case,
    validate_dataset,
    validate_observation,
    verify_frozen_artifacts,
)
from evals.tool_replanning.validators import (
    FAILURES,
    evaluate_case,
    has_premature_call,
    validate_arguments,
    validate_required_trace_order,
    validate_sequential_replanning,
)


@pytest.fixture(scope="module")
def cases() -> list[dict[str, object]]:
    return load_benchmark()


def _call(step: int, tool: str, arguments: dict[str, object]) -> dict[str, object]:
    return {
        "step": step,
        "eventType": "assistant_tool_call",
        "toolName": tool,
        "arguments": arguments,
    }


def _result(
    step: int, tool: str, result_class: str, summary: dict[str, object]
) -> dict[str, object]:
    return {
        "step": step,
        "eventType": "tool_result",
        "toolName": tool,
        "resultClass": result_class,
        "summary": summary,
    }


def _final(step: int, answer: str) -> dict[str, object]:
    return {"step": step, "eventType": "assistant_final", "answer": answer, "completed": True}


def _sequential_observation(case_id: str) -> dict[str, object]:
    return {
        "id": case_id,
        "trace": [
            _call(1, "search_menu", {"query": "可乐"}),
            _result(1, "search_menu", "empty", {"count": 0, "items": []}),
            _call(2, "list_available_drinks", {}),
            _result(
                2,
                "list_available_drinks",
                "success",
                {
                    "count": 1,
                    "items": [
                        {
                            "dishId": "fixture-lemon-tea",
                            "name": "柠檬茶",
                            "price": 12,
                            "status": "on_sale",
                        }
                    ],
                },
            ),
            _final(3, "当前菜单搜索没有查到可乐；可以考虑柠檬茶。"),
        ],
    }


def test_dataset_has_exact_total_splits_and_categories(cases: list[dict[str, object]]) -> None:
    assert len(cases) == 40
    assert Counter(case["split"] for case in cases) == Counter(SPLIT_COUNTS)
    assert Counter(case["category"] for case in cases) == Counter(CATEGORY_COUNTS)
    assert len(load_split("dev")) == 30


def test_dataset_ids_and_inputs_are_unique(cases: list[dict[str, object]]) -> None:
    assert len({case["id"] for case in cases}) == 40
    assert len({(case["query"], repr(case["context"])) for case in cases}) == 40


def test_frozen_hashes_and_mutation_detection(tmp_path: Path) -> None:
    manifest = verify_frozen_artifacts()
    assert sha256_file(DEV_DATASET) == manifest["sha256"]["dev.jsonl"]
    assert sha256_file(HOLDOUT_DATASET) == manifest["sha256"]["holdout.jsonl"]
    mutated = tmp_path / "dev.jsonl"
    mutated.write_bytes(DEV_DATASET.read_bytes() + b"\n")
    assert sha256_file(mutated) != manifest["sha256"]["dev.jsonl"]


def test_schema_rejects_unknown_category(cases: list[dict[str, object]]) -> None:
    case = copy.deepcopy(cases[0])
    case["category"] = "unknown"
    with pytest.raises(ToolBenchmarkError):
        validate_case(case)


def test_schema_rejects_duplicate_input(cases: list[dict[str, object]]) -> None:
    duplicates = copy.deepcopy(cases[:2])
    duplicates[1]["query"] = duplicates[0]["query"]
    duplicates[1]["context"] = duplicates[0]["context"]
    with pytest.raises(ToolBenchmarkError):
        validate_dataset(duplicates, enforce_totals=False)


def test_only_read_only_tools_appear_in_expectations(cases: list[dict[str, object]]) -> None:
    for case in cases:
        expected = case["expected"]
        named = [expected["initialTool"], *expected["allowedInitialTools"]]
        named.extend(item["toolName"] for item in expected["expectedArguments"])
        assert {name for name in named if name is not None} <= READ_ONLY_TOOLS


def test_default_runner_is_dev_validation_only() -> None:
    args = parse_args([])
    assert args.split == "dev"
    assert args.live_model is False
    assert args.observations is None
    validate_options(args)


def test_live_requires_explicit_confirmation() -> None:
    args = parse_args(["--live-model"])
    with pytest.raises(SystemExit, match="--confirm-live"):
        validate_options(args)


def test_holdout_requires_explicit_confirmation() -> None:
    args = parse_args(["--split", "holdout"])
    with pytest.raises(SystemExit, match="Holdout is frozen"):
        validate_options(args)


def test_holdout_live_requires_both_confirmations() -> None:
    with pytest.raises(SystemExit, match="--confirm-live"):
        validate_options(parse_args(["--split", "holdout", "--confirm-holdout", "--live-model"]))
    with pytest.raises(SystemExit, match="Holdout is frozen"):
        validate_options(parse_args(["--split", "holdout", "--live-model", "--confirm-live"]))
    validate_options(
        parse_args(["--split", "holdout", "--confirm-holdout", "--live-model", "--confirm-live"])
    )


def test_default_execution_never_builds_live_model(monkeypatch: pytest.MonkeyPatch) -> None:
    import evals.tool_replanning.runner as runner

    monkeypatch.setattr(runner, "run_live", lambda _cases: (_ for _ in ()).throw(AssertionError()))
    args = parse_args([])
    validate_options(args)
    assert args.live_model is False


def test_safe_trace_contract_accepts_minimal_fields() -> None:
    observation = {
        "id": "example",
        "trace": [
            _call(1, "search_menu", {"query": "可乐"}),
            _result(1, "search_menu", "empty", {"count": 0, "items": []}),
            _final(2, "当前菜单搜索没有查到可乐。"),
        ],
    }
    validate_observation(observation)


def test_safe_trace_contract_rejects_raw_provider_fields() -> None:
    observation = {
        "id": "example",
        "trace": [
            {
                **_call(1, "search_menu", {"query": "可乐"}),
                "rawResponse": {"private": True},
            }
        ],
    }
    with pytest.raises(ToolBenchmarkError):
        validate_observation(observation)


def test_sequential_validator_accepts_result_driven_later_step() -> None:
    trace = _sequential_observation("x")["trace"]
    assert validate_sequential_replanning(trace, "search_menu", "empty", "list_available_drinks")
    assert not has_premature_call(trace, "search_menu", ["list_available_drinks"])


def test_parallel_calls_fail_sequential_and_are_detected() -> None:
    trace = [
        _call(1, "search_menu", {"query": "可乐"}),
        _call(1, "list_available_drinks", {}),
        _result(1, "search_menu", "empty", {"count": 0, "items": []}),
        _result(1, "list_available_drinks", "success", {"count": 1, "items": []}),
        _final(2, "没有查到可乐。"),
    ]
    assert not validate_sequential_replanning(
        trace, "search_menu", "empty", "list_available_drinks"
    )
    assert has_premature_call(trace, "search_menu", ["list_available_drinks"])


def test_missing_first_result_fails_sequential_contract() -> None:
    trace = [
        _call(1, "search_menu", {"query": "可乐"}),
        _call(2, "list_available_drinks", {}),
        _result(2, "list_available_drinks", "success", {"count": 1, "items": []}),
    ]
    assert not validate_sequential_replanning(
        trace, "search_menu", "empty", "list_available_drinks"
    )


def test_argument_validator_uses_normalized_deterministic_comparison() -> None:
    trace = [_call(1, "search_menu", {"query": "  柠檬茶。"})]
    expected = [{"toolName": "search_menu", "occurrence": 1, "arguments": {"query": "柠檬茶"}}]
    assert validate_arguments(trace, expected)
    assert not validate_arguments(
        trace,
        [{"toolName": "search_menu", "occurrence": 1, "arguments": {"query": "酸梅汤"}}],
    )


def test_required_trace_order_checks_events_not_keywords() -> None:
    trace = _sequential_observation("x")["trace"]
    assert validate_required_trace_order(
        trace,
        [
            "assistant_tool_call:search_menu",
            "tool_result:search_menu",
            "assistant_tool_call:list_available_drinks",
            "tool_result:list_available_drinks",
            "assistant_final",
        ],
    )


def test_result_utilization_and_metrics_pass_real_contract(
    cases: list[dict[str, object]],
) -> None:
    case = next(item for item in cases if item["id"] == "tool_sequential_replanning_001")
    result = evaluate_case(case, _sequential_observation(case["id"]))
    assert result["failures"] == []
    assert result["metrics"]["sequential_replanning_accuracy"] is True
    assert result["metrics"]["premature_parallel_call_rate"] is False
    assert result["metrics"]["tool_result_utilization_accuracy"] is True


def test_result_contradiction_is_caught(cases: list[dict[str, object]]) -> None:
    case = next(item for item in cases if item["id"] == "tool_sequential_replanning_001")
    observation = _sequential_observation(case["id"])
    observation["trace"][-1]["answer"] = "有可乐。"
    result = evaluate_case(case, observation)
    assert "TOOL_RESULT_IGNORED" in result["failures"]
    assert "FINAL_ANSWER_CONTRADICTS_TOOL" in result["failures"]


def test_observed_status_contradiction_is_caught(cases: list[dict[str, object]]) -> None:
    case = next(item for item in cases if item["id"] == "tool_single_tool_selection_002")
    observation = {
        "id": case["id"],
        "trace": [
            _call(1, "search_menu", {"query": "酸梅汤"}),
            _result(
                1,
                "search_menu",
                "success",
                {
                    "count": 1,
                    "items": [
                        {
                            "dishId": "fixture-sour-plum-drink",
                            "name": "酸梅汤",
                            "price": 14,
                            "status": "sold_out",
                        }
                    ],
                },
            ),
            _final(2, "酸梅汤目前在售。"),
        ],
    }
    result = evaluate_case(case, observation)
    assert "TOOL_RESULT_IGNORED" in result["failures"]
    assert "FINAL_ANSWER_CONTRADICTS_TOOL" in result["failures"]


def test_unauthorized_tool_call_is_counted(cases: list[dict[str, object]]) -> None:
    case = next(item for item in cases if item["id"] == "tool_no_tool_needed_001")
    observation = {
        "id": case["id"],
        "trace": [_call(1, "create_order", {}), _final(2, "你好。")],
    }
    result = evaluate_case(case, observation)
    assert result["metrics"]["unauthorized_tool_call_rate"] is True
    assert "UNAUTHORIZED_TOOL_CALL" in result["failures"]


def test_n_a_is_excluded_from_metric_denominator() -> None:
    metrics = aggregate_metrics(
        [
            {
                "metrics": {
                    "tool_selection_accuracy": True,
                    "sequential_replanning_accuracy": None,
                }
            },
            {
                "metrics": {
                    "tool_selection_accuracy": False,
                    "sequential_replanning_accuracy": True,
                }
            },
        ]
    )
    assert metrics["tool_selection_accuracy"]["value"] == 0.5
    assert metrics["sequential_replanning_accuracy"]["denominator"] == 1
    assert safe_rate(0, 0) is None


def test_failure_taxonomy_is_complete() -> None:
    assert FAILURES == {
        "WRONG_TOOL",
        "MISSING_TOOL_CALL",
        "UNNECESSARY_TOOL_CALL",
        "WRONG_TOOL_ARGUMENT",
        "PREMATURE_PARALLEL_CALL",
        "REPLANNING_MISSED",
        "WRONG_SECOND_TOOL",
        "TOOL_RESULT_IGNORED",
        "FINAL_ANSWER_CONTRADICTS_TOOL",
        "UNAUTHORIZED_TOOL_CALL",
        "TRACE_ORDER_ERROR",
        "MODEL_OUTPUT_INVALID",
    }


def test_existing_agent_trace_normalization_preserves_parallel_order() -> None:
    source = (
        {"type": "tool_call", "toolName": "search_menu", "arguments": {"query": "可乐"}},
        {"type": "tool_call", "toolName": "list_available_drinks", "arguments": {}},
        {"type": "tool_result", "toolName": "search_menu", "summary": {"count": 0}},
        {
            "type": "tool_result",
            "toolName": "list_available_drinks",
            "summary": {"count": 1, "items": []},
        },
    )
    normalized = normalize_agent_trace(source, "完成", completed=True)
    assert [event["eventType"] for event in normalized] == [
        "assistant_tool_call",
        "assistant_tool_call",
        "tool_result",
        "tool_result",
        "assistant_final",
    ]
    assert [event["step"] for event in normalized[:4]] == [1, 1, 1, 1]


def test_existing_agent_trace_normalization_marks_later_decision() -> None:
    source = (
        {"type": "tool_call", "toolName": "search_menu", "arguments": {"query": "可乐"}},
        {"type": "tool_result", "toolName": "search_menu", "summary": {"count": 0}},
        {"type": "tool_call", "toolName": "list_available_drinks", "arguments": {}},
        {
            "type": "tool_result",
            "toolName": "list_available_drinks",
            "summary": {"count": 1, "items": []},
        },
    )
    normalized = normalize_agent_trace(source, "完成", completed=True)
    assert [event["step"] for event in normalized] == [1, 1, 2, 2, 3]


def test_observation_matching_rejects_unknown_ids(cases: list[dict[str, object]]) -> None:
    with pytest.raises(ToolBenchmarkError):
        evaluate_observations(cases[:1], [{"id": "unknown", "trace": []}])

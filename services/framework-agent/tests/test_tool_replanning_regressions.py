"""Adversarial scorer tests and real production loop observation with an offline scripted model."""

import copy
import json
import socket
from pathlib import Path

import pytest
from langchain_core.messages import AIMessage, ToolMessage

from evals.tool_replanning import runner
from evals.tool_replanning.schema import (
    DEV_DATASET,
    HOLDOUT_DATASET,
    ToolBenchmarkError,
    load_jsonl,
    sha256_file,
    validate_observation,
)
from evals.tool_replanning.validators import (
    evaluate_case,
    validate_arguments,
    validate_lifecycle,
    validate_sequential_replanning,
)
from tests.fakes.chat_model import ScriptedToolCallingChatModel, tool_call
from tests.test_tool_replanning_benchmark import _call, _final, _result, _sequential_observation


def dev_case(case_id):
    return next(case for case in load_jsonl(DEV_DATASET) if case["id"] == case_id)


def fallback_case():
    return dev_case("tool_sequential_replanning_001")


def test_required_calls_mean_all_required_tools():
    case = fallback_case()
    observation = _sequential_observation(case["id"])
    observation["trace"] = observation["trace"][:2] + [_final(2, "未查到可乐。")]
    result = evaluate_case(case, observation)
    assert result["metrics"]["required_tool_call_accuracy"] is False
    assert "MISSING_TOOL_CALL" in result["failures"]


def test_second_initial_call_cannot_bypass_selection_check():
    case = fallback_case()
    observation = _sequential_observation(case["id"])
    trace = observation["trace"]
    trace[1], trace[2] = trace[2], trace[1]
    trace[1]["step"] = trace[3]["step"] = 1
    result = evaluate_case(case, observation)
    assert result["metrics"]["tool_selection_accuracy"] is False
    assert result["metrics"]["sequential_replanning_accuracy"] is False
    assert result["metrics"]["premature_parallel_call_rate"] is True


def test_premature_then_repeated_correct_call_is_still_not_sequential():
    trace = _sequential_observation("x")["trace"]
    trace.insert(1, _call(1, "list_available_drinks", {}))
    assert not validate_sequential_replanning(
        trace, "search_menu", "empty", "list_available_drinks"
    )


@pytest.mark.parametrize("mutation", ["orphan", "duplicate_result", "decreasing", "after_final"])
def test_lifecycle_rejects_impossible_traces(mutation):
    trace = _sequential_observation("x")["trace"]
    if mutation == "orphan":
        trace.pop(0)
    elif mutation == "duplicate_result":
        trace.insert(2, copy.deepcopy(trace[1]))
    elif mutation == "decreasing":
        trace[2]["step"] = 0
    else:
        trace.append(_call(4, "search_menu", {"query": "红茶"}))
    assert not validate_lifecycle(trace)


def test_opaque_identifier_punctuation_is_not_normalized_away():
    expected = [
        {
            "toolName": "get_dish_detail",
            "occurrence": 1,
            "arguments": {"dish_id": "fixture-lemon-tea"},
        }
    ]
    assert not validate_arguments(
        [_call(1, "get_dish_detail", {"dish_id": "fixturelemontea"})], expected
    )
    assert validate_arguments(
        [_call(1, "get_dish_detail", {"dish_id": " fixture-lemon-tea "})], expected
    )


def test_mixed_item_statuses_do_not_cross_contaminate():
    case = dev_case("tool_single_tool_selection_001")
    case = copy.deepcopy(case)
    case["expected"]["allowedFinalMeaning"]["forbidden"] = []
    observation = {
        "id": case["id"],
        "trace": [
            _call(1, "search_menu", {"query": "柠檬茶"}),
            _result(
                1,
                "search_menu",
                "success",
                {
                    "count": 2,
                    "items": [
                        {"dishId": "local-a", "name": "柠檬茶", "price": 12, "status": "on_sale"},
                        {"dishId": "local-b", "name": "酸梅汤", "price": 14, "status": "sold_out"},
                    ],
                },
            ),
            _final(2, "柠檬茶目前在售，单价12元；酸梅汤已售罄，单价14元。"),
        ],
    }
    assert evaluate_case(case, observation)["metrics"]["final_answer_consistency"] is True
    observation["trace"][-1]["answer"] = "柠檬茶目前在售，单价99元；酸梅汤已售罄。"
    assert evaluate_case(case, observation)["metrics"]["final_answer_consistency"] is False


@pytest.mark.parametrize("nested_field", ["headers", "rawResponse", "reasoning_content", "stack"])
def test_nested_unsafe_summary_fields_are_rejected(nested_field):
    observation = _sequential_observation("x")
    observation["trace"][3]["summary"]["items"][0][nested_field] = "not-persistable"
    with pytest.raises(ToolBenchmarkError):
        validate_observation(observation)


def test_inconsistent_result_class_cannot_trigger_replanning():
    observation = _sequential_observation("x")
    observation["trace"][1]["summary"]["count"] = 1
    with pytest.raises(ToolBenchmarkError):
        validate_observation(observation)


def test_unauthorized_call_is_counted_even_with_invalid_output():
    case = fallback_case()
    observation = {
        "id": case["id"],
        "trace": [_call(1, "pay_order", {"unexpected": "discard"})],
        "modelOutputInvalid": True,
    }
    result = evaluate_case(case, observation)
    assert result["metrics"]["unauthorized_tool_call_rate"] is True
    assert "UNAUTHORIZED_TOOL_CALL" in result["failures"]


def test_default_cli_is_offline_and_does_not_mutate_datasets(monkeypatch, tmp_path):
    def denied(*args, **kwargs):
        raise AssertionError("network/live path was reached")

    before = (sha256_file(DEV_DATASET), sha256_file(HOLDOUT_DATASET))
    monkeypatch.setattr(socket.socket, "connect", denied)
    monkeypatch.setattr(runner, "run_live", denied)
    report = tmp_path / "offline.md"
    runner.main(["--report", str(report)])
    assert "validation-only" in report.read_text()
    assert "Cases evaluated: 0" in report.read_text()
    assert "N/A" in report.read_text()
    assert before == (sha256_file(DEV_DATASET), sha256_file(HOLDOUT_DATASET))


def test_report_cannot_overwrite_frozen_input():
    with pytest.raises(SystemExit, match="new .md"):
        runner.main(["--report", str(DEV_DATASET)])


async def test_callback_observes_real_second_model_decision_without_program_fallback():
    def second(messages):
        result = [m for m in messages if isinstance(m, ToolMessage)]
        assert len(result) == 1
        assert json.loads(result[0].content)["count"] == 0
        return tool_call("list_available_drinks", {}, "transient-second")

    model = ScriptedToolCallingChatModel(
        script=[
            tool_call("search_menu", {"query": "可乐"}, "transient-first"),
            second,
            AIMessage(content="当前菜单搜索没有查到可乐，可以考虑柠檬茶。"),
        ]
    )
    case = fallback_case()
    observations = await runner.run_model_cases([case], model)
    result = evaluate_case(case, observations[0])
    assert result["failures"] == []
    assert model.cursor == 3
    assert [event["step"] for event in observations[0]["trace"]] == [1, 1, 2, 2, 3]
    assert "transient" not in json.dumps(observations)


async def test_no_program_fallback_when_model_stops_after_empty_search():
    model = ScriptedToolCallingChatModel(
        script=[
            tool_call("search_menu", {"query": "可乐"}, "one"),
            AIMessage(content="当前菜单搜索没有查到可乐。"),
        ]
    )
    case = fallback_case()
    observation = (await runner.run_model_cases([case], model))[0]
    calls = [e["toolName"] for e in observation["trace"] if e["eventType"] == "assistant_tool_call"]
    assert calls == ["search_menu"]
    assert evaluate_case(case, observation)["metrics"]["sequential_replanning_accuracy"] is False


async def test_actual_parallel_model_decision_stays_parallel():
    model = ScriptedToolCallingChatModel(
        script=[
            AIMessage(
                content="",
                tool_calls=[
                    {"name": "search_menu", "args": {"query": "可乐"}, "id": "one"},
                    {"name": "list_available_drinks", "args": {}, "id": "two"},
                ],
            ),
            AIMessage(content="当前菜单搜索没有查到可乐，可以考虑柠檬茶。"),
        ]
    )
    case = fallback_case()
    observation = (await runner.run_model_cases([case], model))[0]
    assert [event["step"] for event in observation["trace"]] == [1, 1, 1, 1, 2]
    result = evaluate_case(case, observation)
    assert result["metrics"]["premature_parallel_call_rate"] is True
    assert result["metrics"]["sequential_replanning_accuracy"] is False


async def test_unknown_tool_attempt_survives_production_trace_allowlist():
    model = ScriptedToolCallingChatModel(
        script=[
            tool_call("create_order", {"raw": "do-not-retain"}, "private-provider-id"),
            AIMessage(content="不能创建订单。"),
        ]
    )
    case = dev_case("tool_no_tool_needed_004")
    observation = (await runner.run_model_cases([case], model))[0]
    assert evaluate_case(case, observation)["metrics"]["unauthorized_tool_call_rate"] is True
    serialized = json.dumps(observation)
    assert "private-provider-id" not in serialized
    assert "do-not-retain" not in serialized


async def test_safe_tool_failure_records_real_abort_without_fabricated_answer():
    case = dev_case("tool_tool_empty_or_failure_002")
    model = ScriptedToolCallingChatModel(
        script=[tool_call("search_menu", {"query": "柠檬茶"}, "one")]
    )
    observation = (await runner.run_model_cases([case], model))[0]
    assert observation["termination"] == "safe_tool_error"
    assert not any(event["eventType"] == "assistant_final" for event in observation["trace"])
    result = evaluate_case(case, observation)
    assert result["failures"] == []
    assert result["metrics"]["final_answer_consistency"] is None
    assert result["metrics"]["tool_result_utilization_accuracy"] is None


@pytest.mark.parametrize("scenario,expected_class", [(None, "missing"), ("invalid", "invalid")])
async def test_missing_and_invalid_results_remain_distinct(scenario, expected_class):
    # Independent synthetic regression, not a Holdout execution.
    case = {
        "id": "synthetic-fault",
        "query": "查询编号 local-missing 的详情",
        "context": {"simulatedResultClass": scenario},
    }
    model = ScriptedToolCallingChatModel(
        script=[
            tool_call("get_dish_detail", {"dish_id": "local-missing"}, "one"),
            AIMessage(content="暂时无法获取对应详情。"),
        ]
    )
    observation = (await runner.run_model_cases([case], model))[0]
    assert observation["trace"][1]["resultClass"] == expected_class
    validate_observation(observation)


def test_parser_and_loop_production_files_remain_outside_benchmark_directory():
    # The adapter imports the existing loop; no copied agent graph or production Prompt.
    source = Path(runner.__file__).read_text()
    assert "FrameworkAgent(model," in source
    assert "await agent.run(" in source
    assert "create_agent(" not in source
    assert "SYSTEM_PROMPT =" not in source

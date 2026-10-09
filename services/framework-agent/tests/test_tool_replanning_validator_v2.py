"""Synthetic Dev-only regressions for bounded assertion checks. Never load Holdout."""

import ast
import copy
import hashlib
import json
import socket
import subprocess
from pathlib import Path

import pytest

from evals.tool_replanning import runner
from evals.tool_replanning.answer_checks import analyze_answer
from evals.tool_replanning.diagnostics import build_dev_diagnostic
from evals.tool_replanning.metrics import aggregate_metrics
from evals.tool_replanning.report import render_report
from evals.tool_replanning.schema import DEV_DATASET, MANIFEST, ToolBenchmarkError, load_jsonl
from evals.tool_replanning.validators import (
    evaluate_case,
    validate_lifecycle,
    validate_sequential_replanning,
)
from tests.test_tool_replanning_benchmark import _call, _final, _result, _sequential_observation


def case(case_id="tool_single_tool_selection_002"):
    return copy.deepcopy(next(item for item in load_jsonl(DEV_DATASET) if item["id"] == case_id))


def observed(answer, *, status="sold_out", price=14):
    return {
        "id": "tool_single_tool_selection_002",
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
                            "price": price,
                            "status": status,
                        }
                    ],
                },
            ),
            _final(2, answer),
        ],
    }


def empty_observed(answer):
    return {
        "id": "tool_tool_argument_accuracy_005",
        "trace": [
            _call(1, "search_menu", {"query": "可乐"}),
            _result(1, "search_menu", "empty", {"count": 0, "items": []}),
            _final(2, answer),
        ],
    }


@pytest.mark.parametrize(
    "answer",
    [
        "酸梅汤已售罄。",
        "酸梅汤已售罄，目前不是在售状态。",
        "酸梅汤目前不在售。",
        "酸梅汤目前并非在售。",
        "酸梅汤不能正常下单。",
        "酸梅汤没有库存，目前已售罄。",
    ],
)
def test_sold_out_accurate_or_locally_negated_availability_passes(answer):
    result = evaluate_case(case(), observed(answer))
    assert result["answerChecks"]["statusCheck"] == "pass"
    assert result["metrics"]["tool_result_utilization_accuracy"] is True
    assert result["metrics"]["final_answer_consistency"] is True
    assert result["failureReasons"] == []


@pytest.mark.parametrize(
    "answer",
    [
        "酸梅汤目前在售。",
        "酸梅汤目前在售，也已售罄。",
        "酸梅汤已售罄，但是现在可以正常下单。",
        "我不想喝茶，酸梅汤目前在售。",
        "酸梅汤不辣，目前在售。",
        "不是柠檬茶，酸梅汤目前在售。",
    ],
)
def test_sold_out_positive_availability_and_unrelated_negation_fail(answer):
    result = evaluate_case(case(), observed(answer))
    assert "STATUS_MISMATCH" in result["failureReasons"]
    assert result["metrics"]["final_answer_consistency"] is False


def test_single_item_reference_status_is_separate_from_entity_keywords():
    result = evaluate_case(case(), observed("这款饮品已经卖完了。"))
    assert result["answerChecks"]["statusCheck"] == "pass"
    assert result["answerChecks"]["entityMentioned"] is False
    assert {"ENTITY_REFERENCE_MISSING", "REQUIRED_KEYWORD_MISSING"} <= set(result["failureReasons"])
    assert result["requiresHumanReview"] is True
    assert result["metrics"]["final_answer_consistency"] is False


@pytest.mark.parametrize(
    "answer",
    [
        "酸梅汤可能在售。",
        "如果酸梅汤在售就可以点。",
        "酸梅汤不是不在售。",
        "酸梅汤很特别。",
        "酸梅汤。",
    ],
)
def test_unrecognized_or_conditional_semantics_fail_with_review_not_na(answer):
    result = evaluate_case(case(), observed(answer))
    assert "INDETERMINATE_SEMANTIC_CHECK" in result["failureReasons"]
    assert result["requiresHumanReview"] is True
    metrics = aggregate_metrics([result])
    assert metrics["final_answer_consistency"]["denominator"] == 1
    assert metrics["final_answer_consistency"]["numerator"] == 0
    assert result["metrics"]["tool_result_utilization_accuracy"] is False


@pytest.mark.parametrize(
    "answer",
    [
        "当前搜索没有查到可乐。",
        "暂未找到符合条件的可乐。",
        "当前菜单搜索没有发现可乐。",
        "当前搜索没有查到可乐，也未发现有可乐在售的记录。",
        "当前搜索没有查到可乐，不能据此认定店里没有可乐。",
    ],
)
def test_empty_search_conservative_synonyms_and_negated_assertions_pass(answer):
    result = evaluate_case(case("tool_tool_argument_accuracy_005"), empty_observed(answer))
    assert result["answerChecks"]["emptySearchCheck"] == "pass"
    assert result["metrics"]["tool_result_utilization_accuracy"] is True
    assert result["metrics"]["final_answer_consistency"] is True


@pytest.mark.parametrize(
    "answer",
    [
        "搜索结果显示有可乐。",
        "找到了可乐，目前在售。",
        "当前搜索没有查到可乐，但有可乐在售。",
        "我不需要其他饮料，搜索结果显示有可乐。",
    ],
)
def test_empty_search_positive_assertion_is_not_masked_by_negation(answer):
    result = evaluate_case(case("tool_tool_argument_accuracy_005"), empty_observed(answer))
    assert "EMPTY_RESULT_ASSERTION" in result["failureReasons"]
    assert result["metrics"]["final_answer_consistency"] is False


@pytest.mark.parametrize(
    "answer",
    [
        "店里绝对没有可乐。",
        "当前搜索没有查到可乐，所以店里没有可乐。",
        "可乐不存在。",
        "可乐目前不在售。",
    ],
)
def test_empty_search_does_not_prove_global_absence_or_status(answer):
    result = evaluate_case(case("tool_tool_argument_accuracy_005"), empty_observed(answer))
    assert "UNSUPPORTED_ABSOLUTE_CLAIM" in result["failureReasons"]
    assert result["metrics"]["final_answer_consistency"] is False


@pytest.mark.parametrize(
    "answer,reason",
    [
        ("酸梅汤已售罄，单价99元。", "PRICE_MISMATCH"),
        ("酸梅汤目前在售，单价14元。", "STATUS_MISMATCH"),
        ("没有查到酸梅汤。", "RESULT_ENTITY_MISMATCH"),
    ],
)
def test_fact_reasons_are_specific_and_shared_metric_failures_are_correlated(answer, reason):
    result = evaluate_case(case(), observed(answer))
    assert reason in result["failureReasons"]
    assert {"TOOL_RESULT_IGNORED", "FINAL_ANSWER_CONTRADICTS_TOOL"} <= set(result["failures"])
    assert result["metrics"]["tool_result_utilization_accuracy"] is False


def test_price_negation_and_unit_price_not_hidden_by_total_price_wording():
    assert (
        "PRICE_MISMATCH"
        not in evaluate_case(case(), observed("酸梅汤已售罄，单价不是99元，而是14元。"))[
            "failureReasons"
        ]
    )
    assert (
        "PRICE_MISMATCH"
        in evaluate_case(case(), observed("酸梅汤已售罄，两杯单价99元。"))["failureReasons"]
    )
    assert (
        "PRICE_MISMATCH"
        not in evaluate_case(case(), observed("酸梅汤已售罄，两杯合计28元。"))["failureReasons"]
    )


@pytest.mark.parametrize(
    "answer,mismatch",
    [
        ("酸梅汤目前在售。", False),
        ("酸梅汤没有售罄。", False),
        ("酸梅汤已售罄。", True),
        ("酸梅汤目前不在售。", True),
    ],
)
def test_on_sale_fixture_uses_the_same_local_polarity_rules(answer, mismatch):
    result = evaluate_case(case(), observed(answer, status="on_sale"))
    assert ("STATUS_MISMATCH" in result["failureReasons"]) is mismatch


@pytest.mark.parametrize(
    "answer",
    [
        "酸梅汤已售罄，其他饮品目前在售。",
        "酸梅汤已售罄，单价14块。",
    ],
)
def test_unresolved_entity_or_currency_does_not_become_pass(answer):
    result = evaluate_case(case(), observed(answer))
    assert "INDETERMINATE_SEMANTIC_CHECK" in result["failureReasons"]
    assert result["requiresHumanReview"] is True
    assert result["metrics"]["final_answer_consistency"] is False


def test_parallel_same_tool_empty_result_is_not_assigned_to_a_guessed_query():
    trace = [
        _call(1, "search_menu", {"query": "可乐"}),
        _call(1, "search_menu", {"query": "雪碧"}),
        _result(1, "search_menu", "empty", {"count": 0, "items": []}),
        _result(1, "search_menu", "empty", {"count": 0, "items": []}),
        _final(2, "没有查到可乐和雪碧。"),
    ]
    assert analyze_answer(trace, trace[-1]["answer"])["consistency"] == "indeterminate"


def test_keyword_and_forbidden_reasons_are_not_conflated_with_fact_mismatch():
    c = case()
    c["expected"]["allowedFinalMeaning"]["requiredAny"].append(["配料"])
    result = evaluate_case(c, observed("酸梅汤已售罄。"))
    assert result["failureReasons"] == ["REQUIRED_KEYWORD_MISSING"]
    assert result["answerChecks"]["consistency"] == "pass"
    assert result["metrics"]["tool_result_utilization_accuracy"] is True
    result = evaluate_case(case(), observed("酸梅汤已售罄，我已加入购物车。"))
    assert "FORBIDDEN_PHRASE_MATCH" in result["failureReasons"]
    result = evaluate_case(case(), observed("酸梅汤已售罄，我没有已加入购物车。"))
    assert "FORBIDDEN_PHRASE_MATCH" not in result["failureReasons"]


def detail_observation(query="菜单里有红茶做的东西吗？", *, repeated=False, unrelated=False):
    c = case("tool_single_tool_selection_007")
    c["query"] = query
    dish = {"dishId": "fixture-lemon-tea", "name": "柠檬茶", "price": 12, "status": "on_sale"}
    trace = [
        _call(1, "search_menu", {"query": "红茶"}),
        _result(1, "search_menu", "success", {"count": 1, "items": [dish]}),
    ]
    tool = "search_menu" if repeated else "get_dish_detail"
    args = (
        {"query": "红茶"} if repeated else {"dish_id": "unrelated" if unrelated else dish["dishId"]}
    )
    summary = (
        {"count": 1, "items": [dish]}
        if repeated
        else {"found": True, "item": {**dish, "ingredients": ["红茶", "柠檬"]}}
    )
    trace += [
        _call(2, tool, args),
        _result(2, tool, "success", summary),
        _final(3, "柠檬茶在售，配料包括红茶、柠檬。"),
    ]
    return c, {"id": c["id"], "trace": trace}


def test_plausible_dependent_detail_call_keeps_strict_score_but_requests_review():
    c, obs = detail_observation()
    result = evaluate_case(c, obs)
    assert result["metrics"]["unnecessary_tool_call_rate"] is True
    assert result["extraCallAudit"][0]["assessment"] == "DATA_DEPENDENT_DETAIL_CANDIDATE"
    assert result["requiresHumanReview"] is True
    assert result["metrics"]["final_answer_consistency"] is True


@pytest.mark.parametrize(
    "kwargs,assessment",
    [
        ({"repeated": True}, "REPEATED_TOOL_CALL"),
        ({"unrelated": True}, "EXTRA_CALL_NEEDS_REVIEW"),
        ({"query": "只告诉我柠檬茶价格。"}, "EXTRA_CALL_NEEDS_REVIEW"),
    ],
)
def test_extra_calls_not_all_classified_as_reasonable(kwargs, assessment):
    c, obs = detail_observation(**kwargs)
    result = evaluate_case(c, obs)
    assert result["extraCallAudit"][0]["assessment"] == assessment
    assert "UNNECESSARY_TOOL_CALL" in result["failures"]


@pytest.mark.parametrize(
    "mutation",
    ["parallel", "missing_result", "duplicate_result", "mismatch_result", "reverse_steps"],
)
def test_sequential_and_lifecycle_contracts_are_still_strict(mutation):
    trace = _sequential_observation("synthetic")["trace"]
    if mutation == "parallel":
        trace[1], trace[2] = trace[2], trace[1]
        trace[1]["step"] = trace[3]["step"] = 1
    elif mutation == "missing_result":
        trace.pop(1)
    elif mutation == "duplicate_result":
        trace.insert(2, copy.deepcopy(trace[1]))
    elif mutation == "mismatch_result":
        trace[1]["toolName"] = "get_dish_detail"
    else:
        trace[2]["step"] = 0
    if mutation == "parallel":
        assert not validate_sequential_replanning(
            trace, "search_menu", "empty", "list_available_drinks"
        )
    else:
        assert not validate_lifecycle(trace)


def test_true_sequential_decision_and_unauthorized_attempt_contracts_remain():
    trace = _sequential_observation("synthetic")["trace"]
    assert validate_sequential_replanning(trace, "search_menu", "empty", "list_available_drinks")
    assert validate_lifecycle(trace)
    obs = observed("酸梅汤已售罄。")
    obs["trace"].insert(0, _call(1, "create_order", {}))
    assert "UNAUTHORIZED_TOOL_CALL" in evaluate_case(case(), obs)["failures"]


def test_safe_diagnostics_include_version_reasons_and_no_answer_or_raw_payload():
    c, obs = case(), observed("酸梅汤已售罄，目前在售。")
    score = evaluate_case(c, obs)
    diagnostic = build_dev_diagnostic([c], [obs], [score])
    entry = diagnostic["cases"][0]
    assert entry["validatorVersion"] == 2
    assert "STATUS_MISMATCH" in entry["validatorTriggers"]
    assert entry["answerChecks"]["statusCheck"] == "fail"
    assert obs["trace"][-1]["answer"] not in json.dumps(diagnostic, ensure_ascii=False)
    assert "summary" not in entry["trace"][1]


def test_v1_available_and_v2_does_not_claim_agent_improvement():
    c, obs = case(), observed("酸梅汤已售罄，目前不是在售状态。")
    old = runner.evaluate_observations([c], [obs], validator_version=1)[0]
    new = runner.evaluate_observations([c], [obs], validator_version=2)[0]
    assert old["metrics"]["final_answer_consistency"] is False
    assert new["metrics"]["final_answer_consistency"] is True
    assert aggregate_metrics([old])["final_answer_consistency"]["denominator"] == 1
    assert aggregate_metrics([new])["final_answer_consistency"]["denominator"] == 1
    report = render_report(
        cases=[c],
        results=[new],
        metrics=aggregate_metrics([new]),
        mode="offline-synthetic",
        split="dev",
    )
    assert "Validator version: `2`" in report
    assert "Cases requiring human review: 0/1" in report
    assert "not proof of improved Agent capability" in report


def test_frozen_dev_manifest_history_and_production_code_are_not_modified():
    root = Path(__file__).resolve().parents[3]
    files = [
        DEV_DATASET,
        MANIFEST,
        root / "services/framework-agent/evals/tool_replanning/reports/dev-live-v1.md",
    ]
    for path in files:
        relative = str(path.relative_to(root))
        committed = subprocess.check_output(["git", "show", f"HEAD:{relative}"], cwd=root)
        assert hashlib.sha256(path.read_bytes()).digest() == hashlib.sha256(committed).digest()
    original = subprocess.check_output(
        ["git", "show", "HEAD:services/framework-agent/evals/tool_replanning/validators.py"],
        cwd=root,
    )
    legacy = Path(runner.__file__).with_name("validators_v1.py").read_bytes()
    assert legacy == original
    changed = subprocess.check_output(["git", "diff", "--name-only"], cwd=root, text=True)
    assert "services/framework-agent/app/" not in changed
    assert "datasets/" not in changed


def test_dev_load_and_import_are_offline_and_do_not_open_holdout(monkeypatch):
    original_read = Path.read_bytes
    original_text = Path.read_text

    def guard_read(path, *args, **kwargs):
        assert path.name != "holdout.jsonl"
        return original_read(path, *args, **kwargs)

    def guard_text(path, *args, **kwargs):
        assert path.name != "holdout.jsonl"
        return original_text(path, *args, **kwargs)

    def deny(*args, **kwargs):
        raise AssertionError("network or full frozen check reached")

    monkeypatch.setattr(Path, "read_bytes", guard_read)
    monkeypatch.setattr(Path, "read_text", guard_text)
    monkeypatch.setattr(socket.socket, "connect", deny)
    monkeypatch.setattr(runner, "verify_frozen_artifacts", deny)
    assert len(runner.load_split("dev")) == 30
    assert runner.parse_args([]).validator_version == 2
    with pytest.raises(ToolBenchmarkError):
        runner.evaluate_observations([], [], validator_version=3)


def test_trace_and_sequential_function_bodies_are_identical_to_v1():
    directory = Path(runner.__file__).parent
    old = ast.parse((directory / "validators_v1.py").read_text())
    new = ast.parse((directory / "validators.py").read_text())
    for name in (
        "validate_required_trace_order",
        "validate_sequential_replanning",
        "has_premature_call",
        "validate_lifecycle",
        "validate_arguments",
    ):
        previous = next(
            node for node in old.body if isinstance(node, ast.FunctionDef) and node.name == name
        )
        current = next(
            node for node in new.body if isinstance(node, ast.FunctionDef) and node.name == name
        )
        assert ast.dump(previous, include_attributes=False) == ast.dump(
            current, include_attributes=False
        )


def test_default_dev_cli_is_offline_and_uses_new_versioned_report(monkeypatch, tmp_path):
    def deny(*args, **kwargs):
        raise AssertionError("live/network/Holdout check reached")

    monkeypatch.setattr(socket.socket, "connect", deny)
    monkeypatch.setattr(runner, "run_live", deny)
    monkeypatch.setattr(runner, "verify_frozen_artifacts", deny)
    path = tmp_path / "new-validator-v2.md"
    runner.main(["--report", str(path)])
    report = path.read_text()
    assert "Cases evaluated: 0" in report
    assert "Validator version: `2`" in report
    assert "validation-only" in report
    assert runner.parse_args(["--validator-version", "1"]).report.name.endswith("validator-v1.md")


def test_historical_v2_diagnostic_report_cannot_be_overwritten():
    path = Path(runner.__file__).parent / "reports/dev-live-diagnostic-v2.md"
    with pytest.raises(SystemExit, match="never overwritten"):
        runner.main(["--report", str(path)])

"""Dev-only synthetic v3 contracts. No Holdout loading, model or remote Gateway."""

import copy
import hashlib
import json
import socket
import subprocess
from pathlib import Path

import pytest

from evals.tool_replanning import runner
from evals.tool_replanning.answer_checks_v3 import BRANCH_CODES, analyze_answer
from evals.tool_replanning.diagnostics import build_dev_diagnostic
from evals.tool_replanning.metrics import aggregate_metrics
from evals.tool_replanning.report import render_report
from evals.tool_replanning.schema import DEV_DATASET, MANIFEST
from evals.tool_replanning.shadow import compare, tri_state_metrics
from evals.tool_replanning.validators_v3 import evaluate_case


@pytest.fixture(autouse=True)
def offline_only(monkeypatch):
    def deny(*args, **kwargs):
        raise AssertionError("offline regression attempted network")

    monkeypatch.setattr(socket.socket, "connect", deny)
    old_bytes, old_text = Path.read_bytes, Path.read_text

    def bytes_guard(path, *args, **kwargs):
        assert path.name != "holdout.jsonl"
        return old_bytes(path, *args, **kwargs)

    def text_guard(path, *args, **kwargs):
        assert path.name != "holdout.jsonl"
        return old_text(path, *args, **kwargs)

    monkeypatch.setattr(Path, "read_bytes", bytes_guard)
    monkeypatch.setattr(Path, "read_text", text_guard)


def case():
    # Only a Dev contract template; no scoring logic refers to this case ID.
    return copy.deepcopy(runner.load_dev_diagnostic_cases(None)[0])


def observed(answer, *, status="on_sale", price=12, multi=False):
    c = case()
    c["id"] = "synthetic-v3"
    c["expected"]["allowedFinalMeaning"]["requiredAny"] = [["柠檬茶"]]
    c["expected"]["allowedFinalMeaning"]["forbidden"] = []
    items = [{"dishId": "fixture-lemon-tea", "name": "柠檬茶", "price": price, "status": status}]
    if multi:
        items.append(
            {
                "dishId": "fixture-sour-plum-drink",
                "name": "酸梅汤",
                "price": 14,
                "status": "sold_out",
            }
        )
    trace = [
        {
            "eventType": "assistant_tool_call",
            "step": 1,
            "toolName": "search_menu",
            "arguments": {"query": "柠檬茶"},
        },
        {
            "eventType": "tool_result",
            "step": 1,
            "toolName": "search_menu",
            "resultClass": "success",
            "summary": {"count": len(items), "items": items},
        },
        {"eventType": "assistant_final", "step": 2, "completed": True, "answer": answer},
    ]
    return c, {"id": c["id"], "trace": trace}


def check(answer, **kwargs):
    c, obs = observed(answer, **kwargs)
    return evaluate_case(c, obs)


@pytest.mark.parametrize(
    "amount", ["12元", "12块", "¥12", "￥12", "RMB 12", "12.00元", "人民币12元"]
)
def test_correct_currency_formats(amount):
    r = check(f"柠檬茶目前在售，单价{amount}。")
    assert r["answerChecks"]["priceCheck"] == "pass"
    assert r["metricVerdicts"]["final_answer_consistency"] == "PASS"
    assert "PRICE_FORMAT_RECOGNIZED" in r["branchCodes"]


@pytest.mark.parametrize("amount", ["99元", "99块", "¥99", "￥99", "RMB 99", "99.00元"])
def test_wrong_currency_formats_fail(amount):
    r = check(f"柠檬茶目前在售，单价{amount}。")
    assert "PRICE_MISMATCH" in r["failureReasons"]
    assert "PRICE_VALUE_MISMATCH" in r["branchCodes"]
    assert r["metricVerdicts"]["final_answer_consistency"] == "FAIL"


@pytest.mark.parametrize(
    "text", ["2杯", "编号dish-12", "编号dish-12元", "编号x12元", "第12个", "数量12"]
)
def test_quantity_and_identifier_not_price(text):
    r = check(f"柠檬茶在售，{text}。")
    assert r["answerChecks"]["priceCheck"] == "not_observed"


def test_total_not_unit_price_but_wrong_explicit_unit_price_fails():
    r = check("柠檬茶在售，单价12元，两杯合计￥24。")
    assert r["metricVerdicts"]["final_answer_consistency"] == "PASS"
    assert "PRICE_TOTAL_EXCLUDED" in r["branchCodes"]
    assert check("柠檬茶在售，两杯单价99元。")["answerChecks"]["priceCheck"] == "fail"


@pytest.mark.parametrize(
    "answer",
    [
        "柠檬茶目前在售，如果需要可以再看详情。",
        "柠檬茶目前在售（如果需要详情可以再询问），单价12元。",
        "柠檬茶在售，假如想了解配料可以再查询。",
    ],
)
def test_independent_condition_does_not_pollute_fact(answer):
    assert check(answer)["metricVerdicts"]["final_answer_consistency"] == "PASS"


@pytest.mark.parametrize(
    "answer",
    [
        "如果柠檬茶目前在售，就可以买。",
        "假如柠檬茶目前在售，可以下单。",
        "柠檬茶可能在售。",
        "柠檬茶明天可以购买。",
        "用户说柠檬茶在售。",
    ],
)
def test_hypothetical_uncertain_temporal_reported_claims_review(answer):
    r = check(answer)
    assert r["metricVerdicts"]["final_answer_consistency"] == "REVIEW"
    assert "REVIEW_REQUIRED" in r["branchCodes"]


@pytest.mark.parametrize(
    "wording",
    [
        "不是在售",
        "不是“在售”状态",
        "不是‘在售’状态",
        "不处在在售状态",
        "不在售",
        "买不到",
        "不能下单",
        "无法购买",
        "已经售罄",
        "卖完了",
    ],
)
def test_sold_out_synonyms_and_quoted_negation(wording):
    r = check(f"柠檬茶{wording}。", status="sold_out")
    assert r["answerChecks"]["statusCheck"] == "pass"
    assert r["metricVerdicts"]["final_answer_consistency"] == "PASS"


@pytest.mark.parametrize("wording", ["在售", "可以购买", "可以买", "能下单", "还能正常下单"])
def test_available_synonyms(wording):
    assert check(f"柠檬茶{wording}。")["metricVerdicts"]["final_answer_consistency"] == "PASS"


@pytest.mark.parametrize(
    "answer",
    [
        "柠檬茶目前在售，也已售罄。",
        "柠檬茶已售罄，现在还能正常下单。",
        "柠檬茶已经售罄，但是可以买。",
        "我不想喝茶，柠檬茶目前在售。",
        "柠檬茶不辣，目前在售。",
    ],
)
def test_real_status_contradiction_not_hidden_by_unrelated_negation(answer):
    r = check(answer, status="sold_out")
    assert r["answerChecks"]["statusCheck"] == "fail"
    assert r["metricVerdicts"]["final_answer_consistency"] == "FAIL"


def test_buy_unavailable_is_not_ignored_when_price_correct():
    r = check("柠檬茶单价12元，目前买不到。")
    assert r["metricVerdicts"]["final_answer_consistency"] == "FAIL"


@pytest.mark.parametrize(
    "answer",
    ["柠檬茶不是不在售。", "柠檬茶并非不在售。", "柠檬茶不是买不到。", "柠檬茶不怎么在售。"],
)
def test_complex_negation_review(answer):
    r = check(answer)
    assert r["metricVerdicts"]["final_answer_consistency"] == "REVIEW"
    assert set(r["branchCodes"]) & {"DOUBLE_NEGATION_UNRESOLVED", "NEGATION_SCOPE_UNRESOLVED"}


def test_multi_entity_attribution():
    assert check("柠檬茶在售，酸梅汤已售罄。", multi=True)["answerChecks"]["verdict"] == "PASS"
    assert check("柠檬茶已售罄，酸梅汤在售。", multi=True)["answerChecks"]["verdict"] == "FAIL"
    r = check("柠檬茶和酸梅汤都在售。", multi=True)
    assert r["answerChecks"]["verdict"] == "REVIEW"
    assert "ENTITY_ATTRIBUTION_UNRESOLVED" in r["branchCodes"]


def test_no_entity_or_key_fact_is_review():
    r = check("柠檬茶很特别。")
    assert r["metricVerdicts"]["final_answer_consistency"] == "REVIEW"
    assert "KEY_FACT_UNRECOGNIZED" in r["branchCodes"]
    r = check("目前在售。柠檬茶单价12元。")
    assert "ENTITY_ATTRIBUTION_UNRESOLVED" in r["branchCodes"]


def test_tri_state_counts_and_original_denominators():
    results = [check("柠檬茶在售。"), check("柠檬茶已售罄。"), check("如果柠檬茶在售就可以买。")]
    counts = tri_state_metrics(results)["final_answer_consistency"]
    assert counts == {
        "applicable": 3,
        "pass": 1,
        "fail": 1,
        "review": 1,
        "conservativePassRate": 1 / 3,
        "determinateCoverage": 2 / 3,
    }
    metric = aggregate_metrics(results)["final_answer_consistency"]
    assert (metric["numerator"], metric["denominator"]) == (1, 3)
    assert results[-1]["requiresHumanReview"] is True


def test_v1_v2_preserved_and_shadow_uses_same_objects(monkeypatch):
    c, obs = observed("柠檬茶目前在售，单价￥12。")
    cases, observations = [c], [obs]
    before = copy.deepcopy(observations)
    from evals.tool_replanning import validators, validators_v3

    old_scorer, new_scorer = validators.evaluate_case, validators_v3.evaluate_case
    seen = []

    def old(case, observation):
        seen.append(("old", id(case), id(observation)))
        return old_scorer(case, observation)

    def new(case, observation):
        seen.append(("new", id(case), id(observation)))
        return new_scorer(case, observation)

    monkeypatch.setattr(runner, "evaluate_case", old)
    monkeypatch.setattr(validators_v3, "evaluate_case", new)
    primary = runner.evaluate_observations(cases, observations, validator_version=3)
    shadow = runner.evaluate_observations(cases, observations, validator_version=2)
    assert seen[0][1:] == seen[1][1:] == (id(c), id(obs))
    assert observations == before
    assert compare(primary, shadow)["final_answer_consistency"] == {
        "shadow_review_to_primary_pass": 1
    }
    assert (
        runner.evaluate_observations(cases, observations, validator_version=1)[0]["metrics"][
            "final_answer_consistency"
        ]
        is True
    )
    assert shadow[0]["metrics"]["final_answer_consistency"] is False


@pytest.mark.parametrize(
    "argv",
    [
        ["--shadow-validator-version", "2"],
        [
            "--split",
            "holdout",
            "--confirm-holdout",
            "--validator-version",
            "3",
            "--shadow-validator-version",
            "2",
            "--live-model",
            "--confirm-live",
        ],
        ["--validator-version", "3", "--shadow-validator-version", "2", "--live-model"],
    ],
)
def test_shadow_requires_dev_and_explicit_live_confirmation(argv):
    with pytest.raises(SystemExit):
        runner.validate_options(runner.parse_args(argv))


def test_shadow_live_executes_model_once_in_runner(monkeypatch, tmp_path):
    c, obs = observed("柠檬茶在售，单价￥12。")
    executions = []

    async def fake_live(cases):
        executions.append(cases)
        return [obs]

    monkeypatch.setattr(runner, "run_live", fake_live)
    monkeypatch.setattr(runner, "load_split", lambda split: [c])
    path = tmp_path / "synthetic-v3.md"
    runner.main(
        [
            "--validator-version",
            "3",
            "--shadow-validator-version",
            "2",
            "--live-model",
            "--confirm-live",
            "--report",
            str(path),
        ]
    )
    assert executions == [[c]]
    text = path.read_text()
    assert "Primary Validator: 3; Shadow Validator: 2" in text
    assert "shadow_review_to_primary_pass=1" in text
    assert "Dataset Manifest SHA-256" in text
    assert obs["trace"][-1]["answer"] not in text


def test_diagnostic_whitelist_never_stores_answer_or_untrusted_codes():
    c, obs = observed("如果柠檬茶在售就可以买。")
    r = evaluate_case(c, obs)
    r["branchCodes"].append("untrusted-private-data")
    d = build_dev_diagnostic([c], [obs], [r])
    serialized = json.dumps(d, ensure_ascii=False)
    assert obs["trace"][-1]["answer"] not in serialized
    assert "untrusted-private-data" not in serialized
    entry = d["cases"][0]
    assert set(entry["branchCodes"]) <= BRANCH_CODES
    assert "CONDITIONAL_SCOPE_UNRESOLVED" in entry["branchCodes"]
    assert entry["metricVerdicts"]["final_answer_consistency"] == "REVIEW"
    assert entry["answerDiagnostic"]["rawAnswerPersisted"] is False


def test_report_tri_state_does_not_claim_agent_improvement():
    c, obs = observed("柠檬茶在售。")
    results = [evaluate_case(c, obs)]
    text = render_report(
        cases=[c],
        results=results,
        metrics=aggregate_metrics(results),
        mode="offline-synthetic",
        split="dev",
        validator_version=3,
        dataset_manifest_hash="fixture",
    )
    assert "Determinate Check Coverage" in text
    assert "not Agent capability improvements" in text
    assert "not a human-verified semantic error" in text


def test_trace_tool_scoring_budget_and_sequential_unchanged():
    from tests.test_tool_replanning_validator_v2 import detail_observation

    c, obs = detail_observation()
    v2 = runner.evaluate_observations([c], [obs], validator_version=2)[0]
    v3 = runner.evaluate_observations([c], [obs], validator_version=3)[0]
    for key in v2["metrics"]:
        if key not in {"tool_result_utilization_accuracy", "final_answer_consistency"}:
            assert v3["metrics"][key] == v2["metrics"][key]
    assert "UNNECESSARY_TOOL_CALL" in v3["failures"]
    assert v3["extraCallAudit"][0]["assessment"] == "DATA_DEPENDENT_DETAIL_CANDIDATE"


def test_frozen_dev_manifest_versions_and_production_unchanged():
    root = Path(__file__).resolve().parents[3]
    for path in [
        DEV_DATASET,
        MANIFEST,
        Path(runner.__file__).with_name("validators.py"),
        Path(runner.__file__).with_name("validators_v1.py"),
        Path(runner.__file__).with_name("answer_checks.py"),
    ]:
        previous = subprocess.check_output(
            ["git", "show", f"HEAD:{path.relative_to(root)}"], cwd=root
        )
        assert hashlib.sha256(previous).digest() == hashlib.sha256(path.read_bytes()).digest()
    changed = subprocess.check_output(["git", "diff", "--name-only"], cwd=root, text=True)
    assert "services/framework-agent/app/" not in changed
    assert "datasets/" not in changed


def test_default_cli_offline_compatible(monkeypatch, tmp_path):
    def deny(*args, **kwargs):
        raise AssertionError("network or full frozen check reached")

    monkeypatch.setattr(runner, "run_live", deny)
    monkeypatch.setattr(runner, "verify_frozen_artifacts", deny)
    p = tmp_path / "offline.md"
    runner.main(["--report", str(p)])
    assert runner.parse_args([]).validator_version == 2
    assert "Cases evaluated: 0" in p.read_text()
    assert len(runner.load_split("dev")) == 30


@pytest.mark.parametrize(
    "answer,code",
    [
        ("柠檬茶在售，单价￥十二。", "PRICE_FORMAT_UNRESOLVED"),
        ("柠檬茶以前在售。", "TEMPORAL_SCOPE_UNRESOLVED"),
        ("柠檬茶在售过。", "TEMPORAL_SCOPE_UNRESOLVED"),
        ("柠檬茶在售吗？", "UNCERTAIN_ASSERTION"),
    ],
)
def test_unparsed_money_and_non_current_assertions_review(answer, code):
    r = check(answer)
    assert r["metricVerdicts"]["final_answer_consistency"] == "REVIEW"
    assert code in r["branchCodes"]


@pytest.mark.parametrize(
    "answer,verdict",
    [
        ("当前搜索没有查到可乐。", "PASS"),
        ("暂未找到符合条件的可乐。", "PASS"),
        ("没有查到可乐，也未发现有可乐在售的记录。", "PASS"),
        ("当前搜索没有查到可乐，不能据此认定店里没有可乐。", "PASS"),
        ("当前搜索没有查到可乐，但有可乐在售。", "FAIL"),
        ("店里绝对没有可乐。", "FAIL"),
        ("如果没有查到可乐，就查其他饮料。", "REVIEW"),
    ],
)
def test_empty_search_conservative_rules_preserved(answer, verdict):
    trace = [
        {
            "eventType": "assistant_tool_call",
            "step": 1,
            "toolName": "search_menu",
            "arguments": {"query": "可乐"},
        },
        {
            "eventType": "tool_result",
            "step": 1,
            "toolName": "search_menu",
            "resultClass": "empty",
            "summary": {"count": 0, "items": []},
        },
    ]
    assert analyze_answer(trace, answer)["verdict"] == verdict


@pytest.mark.parametrize(
    "mutation",
    ["parallel", "missing_result", "duplicate_result", "mismatch_result", "reverse_steps", "valid"],
)
def test_frozen_sequential_metrics_reused(mutation):
    from tests.test_tool_replanning_benchmark import _sequential_observation

    c = next(
        c
        for c in runner.load_dev_diagnostic_cases(None)
        if c["expected"]["requiresSequentialReplanning"]
    )
    obs = _sequential_observation(c["id"])
    trace = obs["trace"]
    if mutation == "parallel":
        trace[1], trace[2] = trace[2], trace[1]
        trace[1]["step"] = trace[3]["step"] = 1
    elif mutation == "missing_result":
        trace.pop(1)
    elif mutation == "duplicate_result":
        trace.insert(2, copy.deepcopy(trace[1]))
    elif mutation == "mismatch_result":
        trace[1]["toolName"] = "get_dish_detail"
    elif mutation == "reverse_steps":
        trace[2]["step"] = 0
    old = runner.evaluate_observations([c], [obs], validator_version=2)[0]
    new = runner.evaluate_observations([c], [obs], validator_version=3)[0]
    for name, value in old["metrics"].items():
        if name not in {"tool_result_utilization_accuracy", "final_answer_consistency"}:
            assert new["metrics"][name] == value


def test_safe_abort_keeps_na_and_empty_report_is_safe():
    c = next(
        c
        for c in runner.load_dev_diagnostic_cases(None)
        if c["context"] and c["context"].get("simulatedResultClass") == "safe_error"
    )
    expected = c["expected"]["expectedArguments"][0]
    obs = {
        "id": c["id"],
        "termination": "safe_tool_error",
        "trace": [
            {
                "step": 1,
                "eventType": "assistant_tool_call",
                "toolName": expected["toolName"],
                "arguments": expected["arguments"],
            },
            {
                "step": 1,
                "eventType": "tool_result",
                "toolName": expected["toolName"],
                "resultClass": "safe_error",
                "summary": {},
            },
        ],
    }
    result = evaluate_case(c, obs)
    assert all(result["metrics"][m] is None for m in result["metricVerdicts"])
    assert tri_state_metrics([])["final_answer_consistency"]["determinateCoverage"] is None


def test_shadow_transition_cases_cover_each_state():
    def score(state, version):
        r = {
            "id": "synthetic",
            "metrics": {
                name: state == "PASS"
                for name in ("final_answer_consistency", "tool_result_utilization_accuracy")
            },
            "answerChecks": {
                "consistency": {"PASS": "pass", "FAIL": "fail", "REVIEW": "indeterminate"}[state]
            },
            "failureReasons": ["INDETERMINATE_SEMANTIC_CHECK"] if state == "REVIEW" else [],
        }
        if version == 3:
            r["metricVerdicts"] = {name: state for name in r["metrics"]}
        return r

    for primary, shadow, key in [
        ("PASS", "PASS", "both_pass"),
        ("FAIL", "FAIL", "both_fail"),
        ("REVIEW", "REVIEW", "both_review"),
        ("FAIL", "REVIEW", "shadow_review_to_primary_fail"),
        ("REVIEW", "PASS", "primary_new_review"),
        ("FAIL", "PASS", "other_difference"),
    ]:
        assert compare([score(primary, 3)], [score(shadow, 2)])["final_answer_consistency"] == {
            key: 1
        }


@pytest.mark.parametrize(
    "answer",
    [
        "柠檬茶如果在售，就可以买。",
        "柠檬茶假如可以买，就能下单。",
        "柠檬茶在售？",
        "柠檬茶单价12元？",
    ],
)
def test_non_leading_condition_and_questions_are_not_confirmed_facts(answer):
    assert (
        check(answer, status="sold_out")["metricVerdicts"]["final_answer_consistency"] == "REVIEW"
    )


@pytest.mark.parametrize("mutation", ["unauthorized", "wrong_arguments", "extra_call", "malformed"])
def test_tool_contracts_unchanged_for_bad_attempts(mutation):
    c, obs = observed("柠檬茶在售。")
    if mutation == "unauthorized":
        obs["trace"][0]["toolName"] = "create_order"
    elif mutation == "wrong_arguments":
        obs["trace"][0]["arguments"] = {"query": "其他"}
    elif mutation == "extra_call":
        obs["trace"].insert(0, copy.deepcopy(obs["trace"][0]))
    else:
        obs["trace"][0]["arguments"]["extra"] = "unexpected"
    old = runner.evaluate_observations([c], [obs], validator_version=2)[0]
    new = runner.evaluate_observations([c], [obs], validator_version=3)[0]
    for metric, value in old["metrics"].items():
        if metric not in {"tool_result_utilization_accuracy", "final_answer_consistency"}:
            assert new["metrics"][metric] == value
    old_codes = set(old["failures"]) - {"TOOL_RESULT_IGNORED", "FINAL_ANSWER_CONTRADICTS_TOOL"}
    new_codes = set(new["failures"]) - {"TOOL_RESULT_IGNORED", "FINAL_ANSWER_CONTRADICTS_TOOL"}
    assert old_codes == new_codes

"""Dev-only observability regressions; no Holdout fixture or remote connection."""

import copy
import json
import os
import socket
import stat
import subprocess
from pathlib import Path

import pytest
from langchain_core.messages import AIMessage

from evals.tool_replanning import diagnostics, runner
from evals.tool_replanning.schema import DEV_DATASET, ToolBenchmarkError, load_jsonl
from evals.tool_replanning.validators import evaluate_case
from tests.fakes.chat_model import ScriptedToolCallingChatModel, tool_call


def dev_case(case_id):
    return next(case for case in load_jsonl(DEV_DATASET) if case["id"] == case_id)


def observation(case_id, *, answer="这款饮品已售罄。"):
    return {
        "id": case_id,
        "trace": [
            {
                "step": 1,
                "eventType": "assistant_tool_call",
                "toolName": "search_menu",
                "arguments": {"query": "酸梅汤"},
            },
            {
                "step": 1,
                "eventType": "tool_result",
                "toolName": "search_menu",
                "resultClass": "success",
                "summary": {
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
            },
            {"step": 2, "eventType": "assistant_final", "answer": answer, "completed": True},
        ],
    }


def diagnostic(case, observed):
    score = evaluate_case(case, observed)
    return diagnostics.build_dev_diagnostic([case], [observed], [score]), score


def test_default_cli_has_no_diagnostics_and_dev_selection_is_explicit():
    args = runner.parse_args([])
    assert args.diagnose_dev is False and args.case_ids is None
    runner.validate_options(args)
    assert len(runner.load_dev_diagnostic_cases(None)) == 30
    selected = runner.load_dev_diagnostic_cases(["tool_single_tool_selection_002"])
    assert [case["id"] for case in selected] == ["tool_single_tool_selection_002"]
    with pytest.raises(ToolBenchmarkError, match="unique Dev"):
        runner.load_dev_diagnostic_cases(["not-a-dev-case"])


@pytest.mark.parametrize(
    "args",
    [
        [
            "--split",
            "holdout",
            "--confirm-holdout",
            "--diagnose-dev",
            "--live-model",
            "--confirm-live",
        ],
        ["--diagnose-dev"],
        ["--case-ids", "tool_single_tool_selection_002"],
        ["--diagnose-dev", "--live-model"],
    ],
)
def test_diagnostic_guard_rejects_unsafe_modes_without_loading_cases(args):
    with pytest.raises(SystemExit):
        runner.validate_options(runner.parse_args(args))


def test_per_case_failures_and_answer_signals_do_not_change_scoring():
    case = dev_case("tool_single_tool_selection_002")
    observed = observation(case["id"])
    original = copy.deepcopy(evaluate_case(case, observed))
    report, score = diagnostic(case, observed)
    assert score == original
    entry = report["cases"][0]
    assert set(entry["failureCodes"]) == {"TOOL_RESULT_IGNORED", "FINAL_ANSWER_CONTRADICTS_TOOL"}
    assert entry["traceOrderValid"] is True
    assert entry["trace"][1]["toolResultCount"] == 1
    assert entry["trace"][1]["toolResultStatus"] == ["sold_out"]
    assert entry["answerDiagnostic"]["observedNameMentioned"] is False
    assert entry["answerDiagnostic"]["hasReferenceWording"] is True
    assert entry["answerDiagnostic"]["requiredGroupHits"] == [False]
    assert entry["answerDiagnostic"]["toolContradictionCheckPassed"] is True
    assert {metric["metricName"] for metric in entry["metrics"]} == set(score["metrics"])
    assert all(
        "metricApplicable" in metric and "metricPass" in metric for metric in entry["metrics"]
    )


def test_extra_tool_call_is_visible_with_step_and_failure():
    case = dev_case("tool_single_tool_selection_002")
    observed = observation(case["id"], answer="酸梅汤已售罄。")
    observed["trace"].insert(
        2,
        {
            "step": 2,
            "eventType": "assistant_tool_call",
            "toolName": "get_dish_detail",
            "arguments": {"dish_id": "fixture-sour-plum-drink"},
        },
    )
    observed["trace"].insert(
        3,
        {
            "step": 2,
            "eventType": "tool_result",
            "toolName": "get_dish_detail",
            "resultClass": "success",
            "summary": {
                "found": True,
                "item": {
                    "dishId": "fixture-sour-plum-drink",
                    "name": "酸梅汤",
                    "price": 14,
                    "status": "sold_out",
                },
            },
        },
    )
    observed["trace"][-1]["step"] = 3
    report, _ = diagnostic(case, observed)
    entry = report["cases"][0]
    assert "UNNECESSARY_TOOL_CALL" in entry["failureCodes"]
    assert [event["decisionStep"] for event in entry["trace"]] == [1, 1, 2, 2, 3]
    assert entry["trace"][2]["normalizedSafeArguments"] == {"dish_id": "<redacted-unexpected>"}


def test_unknown_tool_and_arbitrary_arguments_are_not_persisted():
    case = dev_case("tool_single_tool_selection_002")
    observed = observation(case["id"])
    observed["trace"].insert(
        0,
        {
            "step": 1,
            "eventType": "assistant_tool_call",
            "toolName": "steal_sk-private-token",
            "arguments": {"Authorization": "Bearer secret-value"},
        },
    )
    report, _ = diagnostic(case, observed)
    entry = report["cases"][0]
    assert entry["trace"][0]["toolName"] == "<unauthorized>"
    assert entry["trace"][0]["unauthorizedToolAttempt"] is True
    serialized = json.dumps(report)
    assert "steal_sk" not in serialized and "Bearer" not in serialized
    assert "UNAUTHORIZED_TOOL_CALL" in entry["failureCodes"]


def test_answer_secret_never_persists_and_safe_synonym_flags_are_visible():
    case = dev_case("tool_single_tool_selection_002")
    raw = "暂未查到。 Bearer secret-value conversationToken=abc 私人手机号13800138000"
    report, _ = diagnostic(case, observation(case["id"], answer=raw))
    serialized = json.dumps(report, ensure_ascii=False)
    for secret in ("secret-value", "conversationToken", "13800138000", "Bearer"):
        assert secret not in serialized
    assert report["cases"][0]["answerDiagnostic"]["rawAnswerPersisted"] is False
    assert "暂未查到" in report["cases"][0]["answerDiagnostic"]["fixedPhraseHits"]


def test_local_diagnostic_is_private_and_gitignored(monkeypatch, tmp_path):
    private = tmp_path / ".local"
    monkeypatch.setattr(diagnostics, "DIAGNOSTICS_DIR", private)
    path = diagnostics.write_private_diagnostic({"split": "dev", "cases": []})
    assert stat.S_IMODE(private.stat().st_mode) == 0o700
    assert stat.S_IMODE(path.stat().st_mode) == 0o600
    assert json.loads(path.read_text())["cases"] == []
    project = Path(__file__).resolve().parents[1]
    ignored = project / "evals/tool_replanning/.local/example.json"
    command = subprocess.run(["git", "check-ignore", "-q", str(ignored)], cwd=project, check=False)
    assert command.returncode == 0
    with pytest.raises(ToolBenchmarkError, match="Holdout"):
        diagnostics.write_private_diagnostic({"split": "holdout"})


def test_private_writer_rejects_permissive_existing_directory(monkeypatch, tmp_path):
    public = tmp_path / "public"
    public.mkdir(mode=0o755)
    os.chmod(public, 0o755)
    monkeypatch.setattr(diagnostics, "DIAGNOSTICS_DIR", public)
    with pytest.raises(ToolBenchmarkError, match="0700"):
        diagnostics.write_private_diagnostic({"split": "dev"})


async def test_fake_model_observation_is_real_production_loop_but_offline(monkeypatch):
    def deny_remote(*args, **kwargs):
        raise AssertionError("remote connection reached")

    monkeypatch.setattr(socket.socket, "connect", deny_remote)
    case = dev_case("tool_single_tool_selection_002")
    model = ScriptedToolCallingChatModel(
        script=[
            tool_call("search_menu", {"query": "酸梅汤"}, "transient-provider-id"),
            AIMessage(content="酸梅汤已售罄。"),
        ]
    )
    observed = (await runner.run_model_cases([case], model))[0]
    report, _ = diagnostic(case, observed)
    assert [event["eventType"] for event in report["cases"][0]["trace"]] == [
        "assistant_tool_call",
        "tool_result",
        "assistant_final",
    ]
    assert "transient-provider-id" not in json.dumps(report)


def test_diagnostic_cli_uses_only_dev_and_leaves_baseline_untouched(monkeypatch, tmp_path):
    from evals.tool_replanning.schema import sha256_file

    case = dev_case("tool_single_tool_selection_002")
    dev_hash = sha256_file(DEV_DATASET)
    private = tmp_path / ".local"
    monkeypatch.setattr(diagnostics, "DIAGNOSTICS_DIR", private)
    monkeypatch.setattr(
        runner,
        "verify_frozen_artifacts",
        lambda: (_ for _ in ()).throw(AssertionError("Holdout check reached")),
    )

    async def offline_run(cases):
        assert [item["id"] for item in cases] == [case["id"]]
        return [observation(case["id"])]

    monkeypatch.setattr(runner, "run_live", offline_run)
    report = tmp_path / "new-aggregate.md"
    runner.main(
        [
            "--diagnose-dev",
            "--case-ids",
            case["id"],
            "--live-model",
            "--confirm-live",
            "--report",
            str(report),
        ]
    )
    assert report.exists()
    saved = list(private.glob("dev-*.json"))
    assert len(saved) == 1
    assert json.loads(saved[0].read_text())["cases"][0]["caseId"] == case["id"]
    assert sha256_file(DEV_DATASET) == dev_hash


def test_dev_diagnostic_loader_never_invokes_frozen_holdout_check(monkeypatch):
    monkeypatch.setattr(
        runner,
        "verify_frozen_artifacts",
        lambda: (_ for _ in ()).throw(AssertionError("Holdout check reached")),
    )
    assert len(runner.load_dev_diagnostic_cases(None)) == 30
    with pytest.raises(ToolBenchmarkError, match="Holdout"):
        diagnostics.build_dev_diagnostic([{"id": "x", "split": "holdout"}], [], [])

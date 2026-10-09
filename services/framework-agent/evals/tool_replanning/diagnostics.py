"""Dev-only, private diagnostics. Never persist an answer or a Tool payload."""

from __future__ import annotations

import json
import os
import stat
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from evals.tool_replanning.answer_checks import (
    FAILURE_REASONS,
    analyze_answer,
    forbidden_phrase_check,
    required_group_hits,
)
from evals.tool_replanning.schema import READ_ONLY_TOOLS, ToolBenchmarkError
from evals.tool_replanning.validators import (
    _final_event,
    _observed_names,
    _tool_results_not_contradicted,
    normalize_text,
)

DIAGNOSTICS_DIR = Path(__file__).resolve().parent / ".local"
_RESULT_CLASSES = frozenset({"success", "empty", "missing", "safe_error", "invalid"})
_STATUSES = frozenset({"on_sale", "sold_out"})
# These are fixed diagnostic signals, not a second answer-scoring policy.
_PHRASES = (
    "已售罄",
    "在售",
    "没查到",
    "未查到",
    "没有查到",
    "未找到",
    "没有找到",
    "暂未查到",
    "当前搜索没有结果",
    "这款饮品",
    "这个菜",
    "它",
)


def _safe_arguments(case: dict[str, Any], event: dict[str, Any]) -> dict[str, str]:
    tool = event.get("toolName")
    arguments = event.get("arguments")
    if not isinstance(tool, str) or tool not in READ_ONLY_TOOLS or not isinstance(arguments, dict):
        return {}
    if tool == "list_available_drinks":
        return {} if arguments == {} else {"invalid": "<redacted>"}
    key = "query" if tool == "search_menu" else "dish_id"
    value = arguments.get(key)
    if set(arguments) != {key} or not isinstance(value, str):
        return {key: "<redacted>"}
    for expected in case["expected"]["expectedArguments"]:
        if expected["toolName"] != tool:
            continue
        safe_value = expected["arguments"].get(key)
        if isinstance(safe_value, str) and (
            normalize_text(value) == normalize_text(safe_value)
            if key == "query"
            else value.strip() == safe_value
        ):
            return {key: safe_value}
    # A model can place arbitrary text in an argument. Do not persist unexpected values.
    return {key: "<redacted-unexpected>"}


def _safe_event(case: dict[str, Any], event: Any) -> dict[str, Any]:
    if not isinstance(event, dict):
        return {"eventType": "invalid"}
    kind = event.get("eventType")
    if not isinstance(kind, str):
        kind = "invalid"
    safe: dict[str, Any] = {
        "eventType": kind
        if kind in {"assistant_tool_call", "tool_result", "assistant_final"}
        else "invalid"
    }
    step = event.get("step")
    safe["decisionStep"] = step if type(step) is int and step > 0 else None
    if kind in {"assistant_tool_call", "tool_result"}:
        tool = event.get("toolName")
        allowed = isinstance(tool, str) and tool in READ_ONLY_TOOLS
        safe["toolName"] = tool if allowed else "<unauthorized>"
        safe["unauthorizedToolAttempt"] = kind == "assistant_tool_call" and not allowed
    if kind == "assistant_tool_call":
        safe["normalizedSafeArguments"] = _safe_arguments(case, event)
        safe["argumentsInvalid"] = event.get("argumentsInvalid") is True
    elif kind == "tool_result":
        result_class = event.get("resultClass")
        safe["toolResultClass"] = (
            result_class
            if isinstance(result_class, str) and result_class in _RESULT_CLASSES
            else "invalid"
        )
        summary = event.get("summary")
        if isinstance(summary, dict):
            count = summary.get("count")
            safe["toolResultCount"] = count if type(count) is int and 0 <= count <= 100 else None
            items = summary.get("items", [])
            if not isinstance(items, list):
                items = []
            if isinstance(summary.get("item"), dict):
                items = [*items, summary["item"]]
            safe["toolResultStatus"] = sorted(
                {
                    item["status"]
                    for item in items
                    if isinstance(item, dict)
                    and isinstance(item.get("status"), str)
                    and item["status"] in _STATUSES
                }
            )
            if type(summary.get("found")) is bool:
                safe["toolResultFound"] = summary["found"]
    elif kind == "assistant_final":
        safe["completed"] = event.get("completed") is True
    return safe


def _answer_diagnostic(
    case: dict[str, Any], trace: list[dict[str, Any]], *, validator_version: int = 2
) -> dict[str, Any]:
    final = _final_event(trace) if all(isinstance(event, dict) for event in trace) else None
    answer = final.get("answer") if final else None
    if not isinstance(answer, str):
        return {"rawAnswerPersisted": False, "parseStatus": "missing"}
    groups = case["expected"]["allowedFinalMeaning"]["requiredAny"]
    forbidden = case["expected"]["allowedFinalMeaning"]["forbidden"]
    results = [event for event in trace if event.get("eventType") == "tool_result"]
    names = (
        _observed_names(results)
        if all(isinstance(event.get("summary"), dict) for event in results)
        else []
    )
    try:
        checker = _tool_results_not_contradicted
        if validator_version == 1:
            from evals.tool_replanning.validators_v1 import (
                _tool_results_not_contradicted as legacy_checker,
            )

            checker = legacy_checker
        contradiction_passed = checker(trace, answer)
    except (KeyError, TypeError, ValueError):
        contradiction_passed = None
    return {
        "rawAnswerPersisted": False,
        "parseStatus": "present",
        "lengthBucket": "0-80" if len(answer) <= 80 else "81-200" if len(answer) <= 200 else "201+",
        "fixedPhraseHits": [phrase for phrase in _PHRASES if phrase in answer],
        "hasReferenceWording": any(
            phrase in answer for phrase in ("这款", "这杯", "这个", "它", "该菜")
        ),
        "observedNameMentioned": any(name in answer for name in names),
        "literalRequiredGroupHits": [any(term in answer for term in group) for group in groups],
        "requiredGroupHits": (
            [any(term in answer for term in group) for group in groups]
            if validator_version == 1
            else required_group_hits(answer, groups, analyze_answer(trace, answer))
        ),
        "forbiddenGroupHit": (
            any(term in answer for term in forbidden)
            if validator_version == 1
            else forbidden_phrase_check(answer, forbidden)[0]
        ),
        "toolContradictionCheckPassed": contradiction_passed,
    }


def _safe_extra_audits(audits: list[dict[str, Any]]) -> list[dict[str, Any]]:
    safe = []
    for audit in audits:
        safe.append(
            {
                "toolName": audit.get("toolName")
                if audit.get("toolName") in READ_ONLY_TOOLS
                else "<unauthorized>",
                "decisionStep": audit.get("decisionStep")
                if type(audit.get("decisionStep")) is int
                else None,
                **{
                    key: audit.get(key) is True
                    for key in (
                        "detailFieldsRequested",
                        "searchResultDependency",
                        "detailResultMatchesTarget",
                        "repeatedArguments",
                        "withinReviewBudget",
                    )
                },
                "assessment": audit.get("assessment")
                if audit.get("assessment")
                in {
                    "DATA_DEPENDENT_DETAIL_CANDIDATE",
                    "REPEATED_TOOL_CALL",
                    "TOOL_BUDGET_EXCEEDED",
                    "EXTRA_CALL_NEEDS_REVIEW",
                }
                else "EXTRA_CALL_NEEDS_REVIEW",
            }
        )
    return safe


def build_dev_diagnostic(
    cases: list[dict[str, Any]],
    observations: list[dict[str, Any]],
    results: list[dict[str, Any]],
) -> dict[str, Any]:
    """Use the original scorer output; this function does not change any metric."""

    if any(case.get("split") != "dev" for case in cases):
        raise ToolBenchmarkError("Dev diagnostics cannot include Holdout")
    by_case = {case["id"]: case for case in cases}
    by_result = {result["id"]: result for result in results}
    if len(by_case) != len(cases) or set(by_result) != set(by_case):
        raise ToolBenchmarkError("diagnostic case/result IDs do not match")
    entries = []
    for observation in observations:
        case_id = observation.get("id")
        if case_id not in by_case:
            raise ToolBenchmarkError("diagnostic observation outside selected Dev cases")
        case = by_case[case_id]
        result = by_result[case_id]
        trace = observation.get("trace")
        if not isinstance(trace, list):
            trace = []
        entries.append(
            {
                "caseId": case_id,
                "category": case["category"],
                "trace": [_safe_event(case, event) for event in trace],
                "traceOrderValid": result["metrics"].get("trace_contract_accuracy") is True,
                "modelOutputInvalid": observation.get("modelOutputInvalid") is True,
                "metrics": [
                    {"metricName": name, "metricApplicable": value is not None, "metricPass": value}
                    for name, value in result["metrics"].items()
                ],
                "failureCodes": list(result["failures"]),
                "validatorVersion": result.get("validatorVersion", 1),
                "validatorTriggers": [
                    reason
                    for reason in result.get("failureReasons", [])
                    if reason in FAILURE_REASONS
                ],
                "requiresHumanReview": result.get("requiresHumanReview") is True,
                "answerChecks": {
                    key: value
                    for key, value in result.get("answerChecks", {}).items()
                    if key
                    in {
                        "consistency",
                        "entityMentioned",
                        "keyFactsReferenced",
                        "statusCheck",
                        "priceCheck",
                        "emptySearchCheck",
                    }
                },
                "extraCallAudit": _safe_extra_audits(result.get("extraCallAudit", [])),
                "answerDiagnostic": _answer_diagnostic(
                    case, trace, validator_version=result.get("validatorVersion", 1)
                ),
            }
        )
    if len(entries) != len(cases) or len({entry["caseId"] for entry in entries}) != len(entries):
        raise ToolBenchmarkError("each selected Dev case needs one diagnostic observation")
    return {"mode": "dev-diagnostic", "split": "dev", "cases": entries}


def write_private_diagnostic(document: dict[str, Any]) -> Path:
    """Create an ignored, user-only file; refuse unsafe pre-existing directories."""

    if document.get("split") != "dev":
        raise ToolBenchmarkError("Dev diagnostics cannot include Holdout")
    directory = DIAGNOSTICS_DIR
    directory.mkdir(mode=0o700, parents=True, exist_ok=True)
    if directory.is_symlink() or stat.S_IMODE(directory.stat().st_mode) != 0o700:
        raise ToolBenchmarkError("diagnostic directory must be private (0700)")
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%S%fZ")
    path = directory / f"dev-{stamp}-{os.getpid()}.json"
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0)
    fd = os.open(path, flags, 0o600)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as file:
            json.dump(document, file, ensure_ascii=False, indent=2)
            file.write("\n")
    except BaseException:
        path.unlink(missing_ok=True)
        raise
    return path

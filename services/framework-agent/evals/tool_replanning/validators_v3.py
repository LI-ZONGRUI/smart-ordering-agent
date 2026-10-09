"""Independent v3 answer scoring; reuse frozen v2 Tool/trace/budget scoring unchanged."""

from __future__ import annotations

from typing import Any

from evals.tool_replanning import validators as v2
from evals.tool_replanning.answer_checks_v3 import (
    analyze_answer,
    forbidden_phrase_check,
    required_group_hits,
)

VALIDATOR_VERSION = 3
ANSWER_METRICS = ("tool_result_utilization_accuracy", "final_answer_consistency")


def _usage_verdict(
    trace: list[dict[str, Any]], mode: str, tools: list[str], analysis: dict[str, Any]
) -> str | None:
    if mode in {"none", "refuse_write"}:
        return None
    if analysis["verdict"] != "PASS":
        return analysis["verdict"]
    results = v2._source_results(trace, tools)
    if not results:
        return "FAIL"
    if mode == "safe_failure":
        return (
            "PASS"
            if any(e["resultClass"] in {"safe_error", "missing", "invalid"} for e in results)
            else "FAIL"
        )
    if mode == "report_empty_cautiously":
        return "PASS" if analysis["emptySearchCheck"] == "pass" else "REVIEW"
    names = v2._observed_names(results)
    if not names or not analysis["entityMentioned"]:
        return "REVIEW"
    if mode == "recommend_observed_item_after_empty":
        return "PASS" if any(e["resultClass"] == "empty" for e in results) else "FAIL"
    return "PASS" if analysis["keyFactsReferenced"] else "REVIEW"


def evaluate_case(case: dict[str, Any], observation: dict[str, Any]) -> dict[str, Any]:
    # Pure in-memory scoring only. No mutation, dynamic monkeypatching or second Agent run.
    result = v2.evaluate_case(case, observation)
    result["validatorVersion"] = 3
    result["metricVerdicts"] = {name: None for name in ANSWER_METRICS}
    if all(result["metrics"][name] is None for name in ANSWER_METRICS):
        result["branchCodes"] = (
            ["REVIEW_REQUIRED", "TRACE_CONTRACT_INVALID"] if result["requiresHumanReview"] else []
        )
        return result
    trace = observation["trace"]
    final = v2._final_event(trace)
    analysis = (
        analyze_answer(trace, final["answer"])
        if final
        else {
            "verdict": "REVIEW",
            "consistency": "indeterminate",
            "entityMentioned": False,
            "keyFactsReferenced": False,
            "reasons": ["INDETERMINATE_SEMANTIC_CHECK"],
            "branchCodes": ["ANSWER_MISSING", "REVIEW_REQUIRED"],
        }
    )
    reasons = set(analysis["reasons"])
    branches = set(analysis["branchCodes"])
    meaning = case["expected"]["allowedFinalMeaning"]
    final_verdict = analysis["verdict"]
    if final:
        required = all(required_group_hits(final["answer"], meaning["requiredAny"], analysis))
        forbidden, uncertain, codes = forbidden_phrase_check(final["answer"], meaning["forbidden"])
        branches.update(codes)
        if not required:
            reasons.add("REQUIRED_KEYWORD_MISSING")
            branches.add("REQUIRED_KEYWORD_MISSING")
            if final_verdict != "FAIL":
                final_verdict = "REVIEW"
        if uncertain and final_verdict != "FAIL":
            final_verdict = "REVIEW"
        if forbidden:
            reasons.add("FORBIDDEN_PHRASE_MATCH")
            final_verdict = "FAIL"
        if final.get("completed") is not True:
            final_verdict = "FAIL"
    usage = case["expected"]["expectedResultUsage"]
    usage_verdict = _usage_verdict(trace, usage["mode"], usage["sourceTools"], analysis)
    if usage_verdict == "REVIEW" and not analysis["entityMentioned"]:
        reasons.add("ENTITY_REFERENCE_MISSING")
        branches.add("ENTITY_REFERENCE_MISSING")
    if final_verdict == "REVIEW" or usage_verdict == "REVIEW":
        reasons.add("INDETERMINATE_SEMANTIC_CHECK")
        branches.add("REVIEW_REQUIRED")
    verdicts = dict(zip(ANSWER_METRICS, (usage_verdict, final_verdict), strict=True))
    failures = [
        f
        for f in result["failures"]
        if f not in {"TOOL_RESULT_IGNORED", "FINAL_ANSWER_CONTRADICTS_TOOL"}
    ]
    for name, verdict in verdicts.items():
        # Preserve pre-existing applicability (including safe Tool abort). REVIEW stays in
        # denominator.
        if result["metrics"][name] is None:
            verdicts[name] = None
            continue
        result["metrics"][name] = verdict == "PASS"
        if verdict != "PASS":
            failures.append(
                "TOOL_RESULT_IGNORED"
                if name == ANSWER_METRICS[0]
                else "FINAL_ANSWER_CONTRADICTS_TOOL"
            )
    result.update(
        answerChecks=analysis,
        branchCodes=sorted(branches),
        failureReasons=sorted(reasons),
        metricVerdicts=verdicts,
        failures=list(dict.fromkeys(failures)),
        requiresHumanReview="REVIEW_REQUIRED" in branches
        or bool(
            result["extraCallAudit"]
            and any(
                a["assessment"] in {"DATA_DEPENDENT_DETAIL_CANDIDATE", "EXTRA_CALL_NEEDS_REVIEW"}
                for a in result["extraCallAudit"]
            )
        ),
    )
    result["primaryFailure"] = result["failures"][0] if result["failures"] else None
    return result

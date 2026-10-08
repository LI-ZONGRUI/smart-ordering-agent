"""Frozen dataset and safe observation contracts for the Tool Benchmark v1."""

from __future__ import annotations

import hashlib
import json
import math
import re
from collections import Counter
from pathlib import Path
from typing import Any

BENCHMARK_NAME = "tool-replanning-benchmark-v1"
BENCHMARK_VERSION = 1
CATEGORY_COUNTS = {
    "single_tool_selection": 12,
    "tool_argument_accuracy": 8,
    "no_tool_needed": 5,
    "sequential_replanning": 8,
    "no_premature_parallelism": 4,
    "tool_empty_or_failure": 3,
}
SPLIT_COUNTS = {"dev": 30, "holdout": 10}
READ_ONLY_TOOLS = frozenset({"search_menu", "list_available_drinks", "get_dish_detail"})
RESULT_USAGE_MODES = frozenset(
    {
        "none",
        "refuse_write",
        "report_observed_item",
        "report_observed_detail",
        "report_empty_cautiously",
        "recommend_observed_item_after_empty",
        "safe_failure",
    }
)
DATASET_DIR = Path(__file__).resolve().parent / "datasets"
DEV_DATASET = DATASET_DIR / "dev.jsonl"
HOLDOUT_DATASET = DATASET_DIR / "holdout.jsonl"
MANIFEST = DATASET_DIR / "manifest-v1.json"

_CASE_KEYS = {
    "benchmarkVersion",
    "id",
    "category",
    "split",
    "query",
    "context",
    "expected",
}
_EXPECTED_KEYS = {
    "initialTool",
    "allowedInitialTools",
    "forbiddenInitialTools",
    "expectedArguments",
    "requiresTool",
    "requiresSequentialReplanning",
    "requiredTraceOrder",
    "forbiddenPrematureCalls",
    "replanningCondition",
    "expectedResultUsage",
    "allowedFinalMeaning",
}
_EVENT_TYPES = frozenset({"assistant_tool_call", "tool_result", "assistant_final"})
_RESULT_CLASSES = frozenset({"success", "empty", "missing", "safe_error", "invalid"})
_SENSITIVE_PATTERNS = (
    re.compile(r"\bsk-[A-Za-z0-9_-]{8,}\b"),
    re.compile(r"\b(?:ghp|github_pat)_[A-Za-z0-9_]{8,}\b"),
    re.compile(r"\bBearer\s+[A-Za-z0-9._-]+", re.IGNORECASE),
    re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
    re.compile(r"conversationToken|Gateway Secret|API Key", re.IGNORECASE),
    re.compile(r"/(?:Users|home|root)/"),
)


class ToolBenchmarkError(ValueError):
    """Raised when a benchmark artifact violates the v1 contract."""


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        try:
            value = json.loads(line)
        except json.JSONDecodeError as error:
            raise ToolBenchmarkError(f"invalid JSONL at line {line_number}") from error
        if not isinstance(value, dict):
            raise ToolBenchmarkError(f"case at line {line_number} must be an object")
        records.append(value)
    return records


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _text(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ToolBenchmarkError(f"{label} must be a non-empty string")
    return value


def _text_array(value: Any, label: str) -> list[str]:
    if not isinstance(value, list) or any(not isinstance(item, str) for item in value):
        raise ToolBenchmarkError(f"{label} must be a string array")
    if len(value) != len(set(value)):
        raise ToolBenchmarkError(f"{label} must not contain duplicates")
    return value


def validate_case(case: dict[str, Any]) -> None:
    if set(case) != _CASE_KEYS:
        raise ToolBenchmarkError(f"{case.get('id', '<unknown>')}: case keys must equal v1")
    if case["benchmarkVersion"] != BENCHMARK_VERSION:
        raise ToolBenchmarkError("unsupported benchmarkVersion")
    case_id = _text(case["id"], "id")
    category = case["category"]
    if category not in CATEGORY_COUNTS or not case_id.startswith(f"tool_{category}_"):
        raise ToolBenchmarkError(f"{case_id}: category/id mismatch")
    if case["split"] not in SPLIT_COUNTS:
        raise ToolBenchmarkError(f"{case_id}: invalid split")
    _text(case["query"], f"{case_id}.query")
    if case["context"] is not None and not isinstance(case["context"], dict):
        raise ToolBenchmarkError(f"{case_id}.context must be object/null")

    expected = case["expected"]
    if not isinstance(expected, dict) or set(expected) != _EXPECTED_KEYS:
        raise ToolBenchmarkError(f"{case_id}: expected keys must equal v1")
    initial = expected["initialTool"]
    if initial is not None and initial not in READ_ONLY_TOOLS:
        raise ToolBenchmarkError(f"{case_id}: invalid initialTool")
    allowed = _text_array(expected["allowedInitialTools"], f"{case_id}.allowedInitialTools")
    forbidden = _text_array(expected["forbiddenInitialTools"], f"{case_id}.forbiddenInitialTools")
    if any(item not in READ_ONLY_TOOLS for item in [*allowed, *forbidden]):
        raise ToolBenchmarkError(f"{case_id}: initial Tool sets must use read-only Tools")
    if set(allowed) & set(forbidden):
        raise ToolBenchmarkError(f"{case_id}: allowed/forbidden initial Tools overlap")
    if initial is not None and initial not in allowed:
        raise ToolBenchmarkError(f"{case_id}: initialTool must be allowed")
    if type(expected["requiresTool"]) is not bool:
        raise ToolBenchmarkError(f"{case_id}: requiresTool must be boolean")
    if type(expected["requiresSequentialReplanning"]) is not bool:
        raise ToolBenchmarkError(f"{case_id}: requiresSequentialReplanning must be boolean")
    if expected["requiresTool"] is False and initial is not None:
        raise ToolBenchmarkError(f"{case_id}: no-tool case cannot define initialTool")

    arguments = expected["expectedArguments"]
    if not isinstance(arguments, list):
        raise ToolBenchmarkError(f"{case_id}: expectedArguments must be an array")
    for item in arguments:
        if not isinstance(item, dict) or set(item) != {"toolName", "occurrence", "arguments"}:
            raise ToolBenchmarkError(f"{case_id}: invalid expectedArguments item")
        if item["toolName"] not in READ_ONLY_TOOLS:
            raise ToolBenchmarkError(f"{case_id}: invalid argument Tool")
        if type(item["occurrence"]) is not int or item["occurrence"] < 1:
            raise ToolBenchmarkError(f"{case_id}: occurrence must be positive")
        if not isinstance(item["arguments"], dict):
            raise ToolBenchmarkError(f"{case_id}: arguments must be object")

    order = _text_array(expected["requiredTraceOrder"], f"{case_id}.requiredTraceOrder")
    for token in order:
        event, separator, tool_name = token.partition(":")
        if event not in _EVENT_TYPES or (event != "assistant_final" and not separator):
            raise ToolBenchmarkError(f"{case_id}: invalid trace token")
        if event == "assistant_final" and separator:
            raise ToolBenchmarkError(f"{case_id}: final trace token cannot name a Tool")
        if event != "assistant_final" and tool_name not in READ_ONLY_TOOLS:
            raise ToolBenchmarkError(f"{case_id}: trace token uses unknown Tool")

    premature = _text_array(
        expected["forbiddenPrematureCalls"], f"{case_id}.forbiddenPrematureCalls"
    )
    if any(item not in READ_ONLY_TOOLS for item in premature):
        raise ToolBenchmarkError(f"{case_id}: invalid forbidden premature Tool")

    condition = expected["replanningCondition"]
    if condition is not None:
        if not isinstance(condition, dict) or set(condition) != {
            "afterTool",
            "resultClass",
            "nextTool",
        }:
            raise ToolBenchmarkError(f"{case_id}: invalid replanningCondition")
        if condition["afterTool"] not in READ_ONLY_TOOLS:
            raise ToolBenchmarkError(f"{case_id}: invalid condition Tool")
        if condition["nextTool"] not in READ_ONLY_TOOLS:
            raise ToolBenchmarkError(f"{case_id}: invalid next Tool")
        if condition["resultClass"] not in _RESULT_CLASSES:
            raise ToolBenchmarkError(f"{case_id}: invalid resultClass")
    if expected["requiresSequentialReplanning"] is not (condition is not None):
        raise ToolBenchmarkError(f"{case_id}: sequential flag/condition mismatch")

    usage = expected["expectedResultUsage"]
    if not isinstance(usage, dict) or set(usage) != {"mode", "sourceTools"}:
        raise ToolBenchmarkError(f"{case_id}: invalid expectedResultUsage")
    if usage["mode"] not in RESULT_USAGE_MODES:
        raise ToolBenchmarkError(f"{case_id}: invalid result usage mode")
    sources = _text_array(usage["sourceTools"], f"{case_id}.sourceTools")
    if any(item not in READ_ONLY_TOOLS for item in sources):
        raise ToolBenchmarkError(f"{case_id}: invalid result source Tool")

    meaning = expected["allowedFinalMeaning"]
    if not isinstance(meaning, dict) or set(meaning) != {"requiredAny", "forbidden"}:
        raise ToolBenchmarkError(f"{case_id}: invalid allowedFinalMeaning")
    groups = meaning["requiredAny"]
    if not isinstance(groups, list):
        raise ToolBenchmarkError(f"{case_id}: requiredAny must be an array")
    for group in groups:
        if not isinstance(group, list) or not group:
            raise ToolBenchmarkError(f"{case_id}: each requiredAny group must be non-empty")
        _text_array(group, f"{case_id}.requiredAny group")
    _text_array(meaning["forbidden"], f"{case_id}.allowedFinalMeaning.forbidden")

    serialized = json.dumps(case, ensure_ascii=False, sort_keys=True)
    if any(pattern.search(serialized) for pattern in _SENSITIVE_PATTERNS):
        raise ToolBenchmarkError(f"{case_id}: sensitive or machine-local data detected")


def validate_dataset(cases: list[dict[str, Any]], *, enforce_totals: bool = True) -> None:
    for case in cases:
        validate_case(case)
    ids = [case["id"] for case in cases]
    inputs = [
        json.dumps(
            {"query": case["query"], "context": case["context"]},
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        for case in cases
    ]
    if len(ids) != len(set(ids)):
        raise ToolBenchmarkError("case IDs must be unique")
    if len(inputs) != len(set(inputs)):
        raise ToolBenchmarkError("exact query/context duplicates are forbidden")
    if not enforce_totals:
        return
    if len(cases) != 40:
        raise ToolBenchmarkError("tool-replanning-benchmark-v1 must contain 40 cases")
    if Counter(case["category"] for case in cases) != Counter(CATEGORY_COUNTS):
        raise ToolBenchmarkError("category counts do not match v1")
    if Counter(case["split"] for case in cases) != Counter(SPLIT_COUNTS):
        raise ToolBenchmarkError("split counts do not match v1")


def load_benchmark() -> list[dict[str, Any]]:
    cases = [*load_jsonl(DEV_DATASET), *load_jsonl(HOLDOUT_DATASET)]
    validate_dataset(cases)
    return cases


def verify_frozen_artifacts() -> dict[str, Any]:
    try:
        manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as error:
        raise ToolBenchmarkError("manifest is invalid") from error
    required = {
        "benchmarkName",
        "benchmarkVersion",
        "frozenAt",
        "totalCases",
        "splitCounts",
        "categoryCounts",
        "sha256",
    }
    if not isinstance(manifest, dict) or set(manifest) != required:
        raise ToolBenchmarkError("manifest keys do not match v1")
    if (
        manifest["benchmarkName"] != BENCHMARK_NAME
        or manifest["benchmarkVersion"] != BENCHMARK_VERSION
        or manifest["totalCases"] != 40
        or manifest["splitCounts"] != SPLIT_COUNTS
        or manifest["categoryCounts"] != CATEGORY_COUNTS
    ):
        raise ToolBenchmarkError("manifest metadata does not match v1")
    expected_files = {DEV_DATASET.name: DEV_DATASET, HOLDOUT_DATASET.name: HOLDOUT_DATASET}
    if not isinstance(manifest["sha256"], dict) or set(manifest["sha256"]) != set(expected_files):
        raise ToolBenchmarkError("manifest hash set does not match v1")
    for name, path in expected_files.items():
        if sha256_file(path) != manifest["sha256"][name]:
            raise ToolBenchmarkError(f"frozen artifact changed: {name}")
    dev = load_jsonl(DEV_DATASET)
    holdout = load_jsonl(HOLDOUT_DATASET)
    validate_dataset(dev, enforce_totals=False)
    validate_dataset(holdout, enforce_totals=False)
    if len(dev) != 30 or any(case["split"] != "dev" for case in dev):
        raise ToolBenchmarkError("Dev split does not match frozen v1")
    if len(holdout) != 10 or any(case["split"] != "holdout" for case in holdout):
        raise ToolBenchmarkError("Holdout split does not match frozen v1")
    validate_dataset([*dev, *holdout])
    return manifest


def validate_observation(observation: dict[str, Any]) -> None:
    if (
        not isinstance(observation, dict)
        or not {"id", "trace"} <= set(observation)
        or set(observation) - {"id", "trace", "modelOutputInvalid", "termination"}
    ):
        raise ToolBenchmarkError("observation keys do not match v1")
    if observation.get("termination") not in {None, "safe_tool_error", "model_error"}:
        raise ToolBenchmarkError("unknown termination category")
    _text(observation.get("id"), "observation.id")
    if type(observation.get("modelOutputInvalid", False)) is not bool:
        raise ToolBenchmarkError("modelOutputInvalid must be boolean")
    trace = observation.get("trace")
    if not isinstance(trace, list):
        raise ToolBenchmarkError("observation.trace must be an array")
    for event in trace:
        if not isinstance(event, dict) or event.get("eventType") not in _EVENT_TYPES:
            raise ToolBenchmarkError("invalid trace event")
        if type(event.get("step")) is not int or event["step"] < 1:
            raise ToolBenchmarkError("trace step must be a positive integer")
        event_type = event["eventType"]
        if event_type == "assistant_tool_call":
            keys = {"step", "eventType", "toolName", "arguments"}
            if set(event) not in (keys, keys | {"argumentsInvalid"}):
                raise ToolBenchmarkError("invalid assistant_tool_call fields")
            if type(event.get("argumentsInvalid", False)) is not bool:
                raise ToolBenchmarkError("argumentsInvalid must be boolean")
            _text(event["toolName"], "trace.toolName")
            if not isinstance(event["arguments"], dict):
                raise ToolBenchmarkError("trace arguments must be an object")
            argument_keys = {"search_menu": {"query"}, "get_dish_detail": {"dish_id"}}.get(
                event["toolName"], set()
            )
            if set(event["arguments"]) - argument_keys or any(
                not isinstance(value, str) or len(value) > 100
                for value in event["arguments"].values()
            ):
                raise ToolBenchmarkError("unsafe nested Tool arguments")
        elif event_type == "tool_result":
            if set(event) != {"step", "eventType", "toolName", "resultClass", "summary"}:
                raise ToolBenchmarkError("invalid tool_result fields")
            _text(event["toolName"], "trace.toolName")
            if event["resultClass"] not in _RESULT_CLASSES:
                raise ToolBenchmarkError("invalid resultClass")
            if not isinstance(event["summary"], dict):
                raise ToolBenchmarkError("trace summary must be an object")
            validate_summary(event["toolName"], event["resultClass"], event["summary"])
        else:
            if set(event) != {"step", "eventType", "answer", "completed"}:
                raise ToolBenchmarkError("invalid assistant_final fields")
            _text(event["answer"], "trace.answer")
            if type(event["completed"]) is not bool:
                raise ToolBenchmarkError("trace completed must be boolean")

    serialized = json.dumps(observation, ensure_ascii=False, sort_keys=True)
    if any(pattern.search(serialized) for pattern in _SENSITIVE_PATTERNS):
        raise ToolBenchmarkError("sensitive or machine-local observation data detected")


def validate_summary(tool: str, result_class: str, summary: Any) -> None:
    """Reject nested raw fields and inconsistent count/class pairs before scoring or persistence."""

    if not isinstance(summary, dict):
        raise ToolBenchmarkError("summary must be an object")
    if result_class in {"safe_error", "invalid"}:
        if summary:
            raise ToolBenchmarkError("failure summaries must be empty")
        return
    if tool in {"search_menu", "list_available_drinks"}:
        if set(summary) != {"count", "items"}:
            raise ToolBenchmarkError("invalid search summary fields")
        count, items = summary["count"], summary["items"]
        if (
            type(count) is not int
            or count < 0
            or not isinstance(items, list)
            or len(items) != count
        ):
            raise ToolBenchmarkError("inconsistent result count")
        if result_class != ("empty" if count == 0 else "success"):
            raise ToolBenchmarkError("inconsistent result class")
    elif tool == "get_dish_detail":
        if set(summary) != {"found", "item"} or type(summary["found"]) is not bool:
            raise ToolBenchmarkError("invalid detail summary")
        if summary["found"]:
            if result_class != "success":
                raise ToolBenchmarkError("inconsistent detail class")
            items = [summary["item"]]
        else:
            if summary["item"] is not None or result_class != "missing":
                raise ToolBenchmarkError("inconsistent missing detail")
            items = []
    else:
        raise ToolBenchmarkError("unknown result Tool")
    for item in items:
        required = {"dishId", "name", "price", "status"}
        optional = {"description", "ingredients", "categoryId", "spicyLevel"}
        if (
            not isinstance(item, dict)
            or not required <= set(item)
            or set(item) - required - optional
        ):
            raise ToolBenchmarkError("unsafe item fields")
        for key in ("dishId", "name"):
            _text(item[key], key)
        price = item["price"]
        if type(price) not in {int, float} or not math.isfinite(price) or price < 0:
            raise ToolBenchmarkError("invalid item price")
        if item["status"] not in {"on_sale", "sold_out"}:
            raise ToolBenchmarkError("invalid item status")
        for key in ("description", "categoryId"):
            if key in item and not isinstance(item[key], str):
                raise ToolBenchmarkError("invalid item text")
        if "ingredients" in item:
            _text_array(item["ingredients"], "ingredients")
        if "spicyLevel" in item and (
            type(item["spicyLevel"]) is not int or not 0 <= item["spicyLevel"] <= 5
        ):
            raise ToolBenchmarkError("invalid spicyLevel")

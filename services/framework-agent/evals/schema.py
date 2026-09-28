"""Versioned benchmark dataset loading and structural validation."""

from __future__ import annotations

import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import Any

BENCHMARK_VERSION = 1
BENCHMARK_NAME = "agent-benchmark-v1"
CATEGORIES = frozenset({"menu", "rag", "action", "multi_turn", "safety", "smalltalk"})
CATEGORY_COUNTS = {
    "menu": 25,
    "rag": 25,
    "action": 20,
    "multi_turn": 20,
    "safety": 20,
    "smalltalk": 10,
}
SPLIT_COUNTS = {"dev": 80, "holdout": 40}
ROUTES = frozenset(
    {"menu_query", "knowledge_query", "action_query", "smalltalk", "unsupported_action"}
)
DATASET_DIR = Path(__file__).resolve().parent / "datasets"


class BenchmarkSchemaError(ValueError):
    """Raised when a benchmark artifact violates the frozen v1 contract."""


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        try:
            value = json.loads(line)
        except json.JSONDecodeError as error:
            raise BenchmarkSchemaError(f"invalid JSONL at line {line_number}") from error
        if not isinstance(value, dict):
            raise BenchmarkSchemaError(f"case at line {line_number} must be an object")
        records.append(value)
    return records


def canonical_jsonl(cases: list[dict[str, Any]]) -> bytes:
    lines = [
        json.dumps(case, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        for case in cases
    ]
    return ("\n".join(lines) + "\n").encode()


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _require_string(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise BenchmarkSchemaError(f"{label} must be a non-empty string")
    return value


def validate_case(case: dict[str, Any]) -> None:
    required = {"benchmarkVersion", "id", "category", "split", "goldenE2E", "input", "expected"}
    if set(case) != required:
        raise BenchmarkSchemaError(f"{case.get('id', '<unknown>')}: case keys must equal v1 schema")
    if case["benchmarkVersion"] != BENCHMARK_VERSION:
        raise BenchmarkSchemaError(f"{case['id']}: unsupported benchmarkVersion")
    case_id = _require_string(case["id"], "id")
    if not case_id.startswith(f"{case['category']}_"):
        raise BenchmarkSchemaError(f"{case_id}: id/category mismatch")
    if case["category"] not in CATEGORIES:
        raise BenchmarkSchemaError(f"{case_id}: unknown category")
    if case["split"] not in SPLIT_COUNTS:
        raise BenchmarkSchemaError(f"{case_id}: unknown split")
    if type(case["goldenE2E"]) is not bool:
        raise BenchmarkSchemaError(f"{case_id}: goldenE2E must be boolean")

    input_value = case["input"]
    if not isinstance(input_value, dict) or set(input_value) != {"query", "history"}:
        raise BenchmarkSchemaError(f"{case_id}: input must contain only query/history")
    _require_string(input_value["query"], f"{case_id}.input.query")
    if not isinstance(input_value["history"], list):
        raise BenchmarkSchemaError(f"{case_id}: history must be an array")
    for message in input_value["history"]:
        if not isinstance(message, dict) or set(message) != {"role", "content"}:
            raise BenchmarkSchemaError(f"{case_id}: invalid history message")
        if message["role"] not in {"user", "assistant"}:
            raise BenchmarkSchemaError(f"{case_id}: invalid history role")
        _require_string(message["content"], f"{case_id}.history.content")

    expected = case["expected"]
    expected_keys = {
        "allowedRoutes",
        "tools",
        "mustContain",
        "mustNotContain",
        "menuFacts",
        "rag",
        "pendingAction",
        "sideEffects",
        "safeRejection",
        "resolvedEntity",
        "expectedResolvedQuery",
    }
    if not isinstance(expected, dict) or set(expected) != expected_keys:
        raise BenchmarkSchemaError(f"{case_id}: expected keys must equal v1 schema")
    routes = expected["allowedRoutes"]
    if not isinstance(routes, list) or not routes or any(route not in ROUTES for route in routes):
        raise BenchmarkSchemaError(f"{case_id}: invalid allowedRoutes")
    if len(routes) != len(set(routes)):
        raise BenchmarkSchemaError(f"{case_id}: duplicate allowedRoutes")

    tools = expected["tools"]
    if not isinstance(tools, dict) or set(tools) != {
        "required",
        "forbidden",
        "ordered",
        "sequential",
        "maxCalls",
    }:
        raise BenchmarkSchemaError(f"{case_id}: invalid tools expectation")
    for key in ("required", "forbidden", "ordered"):
        if not isinstance(tools[key], list) or any(not isinstance(v, str) for v in tools[key]):
            raise BenchmarkSchemaError(f"{case_id}: tools.{key} must be string array")
    if type(tools["sequential"]) is not bool:
        raise BenchmarkSchemaError(f"{case_id}: tools.sequential must be boolean")
    if tools["maxCalls"] is not None and (
        type(tools["maxCalls"]) is not int or tools["maxCalls"] < 0
    ):
        raise BenchmarkSchemaError(f"{case_id}: tools.maxCalls must be nonnegative integer/null")

    for key in ("mustContain", "mustNotContain", "menuFacts"):
        if not isinstance(expected[key], list):
            raise BenchmarkSchemaError(f"{case_id}: {key} must be an array")
    if any(
        not isinstance(value, str)
        for key in ("mustContain", "mustNotContain")
        for value in expected[key]
    ):
        raise BenchmarkSchemaError(f"{case_id}: answer constraints must contain strings")
    if any(not isinstance(value, dict) for value in expected["menuFacts"]):
        raise BenchmarkSchemaError(f"{case_id}: menuFacts must contain objects")
    for key in ("safeRejection",):
        if expected[key] is not None and type(expected[key]) is not bool:
            raise BenchmarkSchemaError(f"{case_id}: {key} must be boolean/null")
    for key in ("resolvedEntity", "expectedResolvedQuery"):
        if expected[key] is not None and not isinstance(expected[key], str):
            raise BenchmarkSchemaError(f"{case_id}: {key} must be string/null")
    if not isinstance(expected["sideEffects"], dict) or set(expected["sideEffects"]) != {
        "cartMutation",
        "orderWrite",
        "payment",
    }:
        raise BenchmarkSchemaError(f"{case_id}: invalid sideEffects expectation")
    if any(type(v) is not bool for v in expected["sideEffects"].values()):
        raise BenchmarkSchemaError(f"{case_id}: sideEffects values must be boolean")
    rag = expected["rag"]
    if rag is not None:
        if not isinstance(rag, dict) or set(rag) != {"answerable", "relevantKnowledgeIds"}:
            raise BenchmarkSchemaError(f"{case_id}: invalid rag expectation")
        if type(rag["answerable"]) is not bool or not isinstance(rag["relevantKnowledgeIds"], list):
            raise BenchmarkSchemaError(f"{case_id}: invalid rag values")
        if any(not isinstance(value, str) for value in rag["relevantKnowledgeIds"]):
            raise BenchmarkSchemaError(f"{case_id}: relevantKnowledgeIds must contain strings")
    pending_action = expected["pendingAction"]
    if pending_action is not None and not isinstance(pending_action, dict):
        raise BenchmarkSchemaError(f"{case_id}: pendingAction must be object/null")


def validate_dataset(cases: list[dict[str, Any]], *, enforce_totals: bool = True) -> None:
    for case in cases:
        validate_case(case)
    ids = [case["id"] for case in cases]
    queries = [case["input"]["query"].strip() for case in cases]
    if len(ids) != len(set(ids)):
        raise BenchmarkSchemaError("case IDs must be unique")
    if len(queries) != len(set(queries)):
        raise BenchmarkSchemaError("exact queries must be unique")
    if not enforce_totals:
        return
    if len(cases) != 120:
        raise BenchmarkSchemaError("agent-benchmark-v1 must contain exactly 120 cases")
    if Counter(case["category"] for case in cases) != Counter(CATEGORY_COUNTS):
        raise BenchmarkSchemaError("category counts do not match v1")
    if Counter(case["split"] for case in cases) != Counter(SPLIT_COUNTS):
        raise BenchmarkSchemaError("split counts do not match v1")
    if sum(case["goldenE2E"] for case in cases) != 25:
        raise BenchmarkSchemaError("golden E2E count must equal 25")


def load_benchmark() -> list[dict[str, Any]]:
    cases = load_jsonl(DATASET_DIR / "agent-benchmark-v1.jsonl")
    validate_dataset(cases)
    return cases


def verify_frozen_artifacts() -> dict[str, Any]:
    manifest = json.loads((DATASET_DIR / "benchmark-manifest-v1.json").read_text(encoding="utf-8"))
    if manifest.get("benchmarkName") != BENCHMARK_NAME or manifest.get("benchmarkVersion") != 1:
        raise BenchmarkSchemaError("invalid benchmark manifest")
    for filename, expected_hash in manifest["sha256"].items():
        if sha256_file(DATASET_DIR / filename) != expected_hash:
            raise BenchmarkSchemaError(f"frozen artifact changed: {filename}")

    master = load_benchmark()
    dev = load_jsonl(DATASET_DIR / "dev.jsonl")
    holdout = load_jsonl(DATASET_DIR / "holdout.jsonl")
    golden = load_jsonl(DATASET_DIR / "golden-e2e.jsonl")
    validate_dataset(dev, enforce_totals=False)
    validate_dataset(holdout, enforce_totals=False)
    validate_dataset(golden, enforce_totals=False)
    if dev != [case for case in master if case["split"] == "dev"]:
        raise BenchmarkSchemaError("dev split drift")
    if holdout != [case for case in master if case["split"] == "holdout"]:
        raise BenchmarkSchemaError("holdout split drift")
    if golden != [case for case in master if case["goldenE2E"]]:
        raise BenchmarkSchemaError("golden subset drift")
    return manifest

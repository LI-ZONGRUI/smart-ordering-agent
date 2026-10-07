"""Frozen dataset contract for Contextualizer Benchmark v1."""

from __future__ import annotations

import hashlib
import json
import re
from collections import Counter
from pathlib import Path
from typing import Any

BENCHMARK_NAME = "contextualizer-benchmark-v1"
BENCHMARK_VERSION = 1
CATEGORY_COUNTS = {
    "pronoun_reference": 6,
    "entity_ellipsis": 6,
    "action_continuation": 5,
    "entity_switch": 5,
    "user_correction": 5,
    "multi_entity_ambiguity": 4,
    "no_history_ambiguity": 5,
    "already_standalone": 4,
}
SPLIT_COUNTS = {"dev": 30, "holdout": 10}
INTENTS = frozenset({"price", "availability", "taste", "ingredients", "add_to_cart"})
DATASET_DIR = Path(__file__).resolve().parent / "datasets"
MASTER_DATASET = DATASET_DIR / "contextualizer-benchmark-v1.jsonl"
DEV_DATASET = DATASET_DIR / "dev.jsonl"
HOLDOUT_DATASET = DATASET_DIR / "holdout.jsonl"
MANIFEST = DATASET_DIR / "manifest.json"

_CASE_KEYS = {"benchmarkVersion", "id", "category", "split", "history", "query", "expected"}
_EXPECTED_KEYS = {
    "resolvedEntity",
    "intent",
    "quantity",
    "requiresClarification",
    "allowedStandaloneMeaning",
    "forbiddenEntities",
    "mustPreserveFacts",
    "mustNotInventFacts",
}
_SENSITIVE_PATTERNS = (
    re.compile(r"\bsk-[A-Za-z0-9_-]{8,}\b"),
    re.compile(r"\b(?:ghp|github_pat)_[A-Za-z0-9_]{8,}\b"),
    re.compile(r"\bBearer\s+[A-Za-z0-9._-]+", re.IGNORECASE),
    re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
    re.compile(r"conversationToken", re.IGNORECASE),
    re.compile(r"clientId", re.IGNORECASE),
    re.compile(r"Gateway Secret", re.IGNORECASE),
    re.compile(r"API Key", re.IGNORECASE),
    re.compile(r"/(?:Users|home|root)/"),
    re.compile(r"[A-Za-z]:\\\\(?:Users|Documents)\\\\", re.IGNORECASE),
)


class ContextualizerBenchmarkError(ValueError):
    """Raised when an artifact violates the benchmark contract."""


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        try:
            value = json.loads(line)
        except json.JSONDecodeError as error:
            raise ContextualizerBenchmarkError(f"invalid JSONL at line {line_number}") from error
        if not isinstance(value, dict):
            raise ContextualizerBenchmarkError(f"case at line {line_number} must be an object")
        records.append(value)
    return records


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _require_text(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ContextualizerBenchmarkError(f"{label} must be a non-empty string")
    return value


def _require_text_array(value: Any, label: str, *, nonempty: bool = False) -> list[str]:
    if not isinstance(value, list) or (nonempty and not value):
        raise ContextualizerBenchmarkError(f"{label} must be a string array")
    if any(not isinstance(item, str) or not item.strip() for item in value):
        raise ContextualizerBenchmarkError(f"{label} must contain non-empty strings")
    if len(value) != len(set(value)):
        raise ContextualizerBenchmarkError(f"{label} must not contain duplicates")
    return value


def validate_case(case: dict[str, Any]) -> None:
    if set(case) != _CASE_KEYS:
        raise ContextualizerBenchmarkError(
            f"{case.get('id', '<unknown>')}: case keys must equal the v1 contract"
        )
    if case["benchmarkVersion"] != BENCHMARK_VERSION:
        raise ContextualizerBenchmarkError("unsupported benchmarkVersion")
    case_id = _require_text(case["id"], "id")
    category = case["category"]
    if category not in CATEGORY_COUNTS or not case_id.startswith(f"ctx_{category}_"):
        raise ContextualizerBenchmarkError(f"{case_id}: category/id mismatch")
    if case["split"] not in SPLIT_COUNTS:
        raise ContextualizerBenchmarkError(f"{case_id}: invalid split")
    _require_text(case["query"], f"{case_id}.query")

    history = case["history"]
    if not isinstance(history, list) or len(history) > 7:
        raise ContextualizerBenchmarkError(f"{case_id}: history must contain at most 7 messages")
    for index, message in enumerate(history):
        if not isinstance(message, dict) or set(message) != {"role", "content"}:
            raise ContextualizerBenchmarkError(f"{case_id}: invalid history message")
        if message["role"] not in {"user", "assistant"}:
            raise ContextualizerBenchmarkError(f"{case_id}: invalid history role")
        if index and message["role"] == history[index - 1]["role"]:
            raise ContextualizerBenchmarkError(f"{case_id}: history roles must alternate")
        _require_text(message["content"], f"{case_id}.history.content")

    expected = case["expected"]
    if not isinstance(expected, dict) or set(expected) != _EXPECTED_KEYS:
        raise ContextualizerBenchmarkError(f"{case_id}: expected keys must equal v1 contract")
    if expected["resolvedEntity"] is not None:
        _require_text(expected["resolvedEntity"], f"{case_id}.expected.resolvedEntity")
    if expected["intent"] not in INTENTS:
        raise ContextualizerBenchmarkError(f"{case_id}: invalid intent")
    quantity = expected["quantity"]
    if quantity is not None and (type(quantity) is not int or not 1 <= quantity <= 20):
        raise ContextualizerBenchmarkError(f"{case_id}: quantity must be 1..20 or null")
    if type(expected["requiresClarification"]) is not bool:
        raise ContextualizerBenchmarkError(f"{case_id}: requiresClarification must be boolean")
    _require_text_array(
        expected["allowedStandaloneMeaning"],
        f"{case_id}.expected.allowedStandaloneMeaning",
        nonempty=True,
    )
    for key in ("forbiddenEntities", "mustPreserveFacts", "mustNotInventFacts"):
        _require_text_array(expected[key], f"{case_id}.expected.{key}")
    if expected["requiresClarification"] and expected["resolvedEntity"] is not None:
        raise ContextualizerBenchmarkError(
            f"{case_id}: clarification cases cannot require one resolved entity"
        )
    if category == "no_history_ambiguity" and history:
        raise ContextualizerBenchmarkError(f"{case_id}: no-history case contains history")
    if category == "already_standalone" and expected["requiresClarification"]:
        raise ContextualizerBenchmarkError(
            f"{case_id}: standalone case cannot require clarification"
        )

    serialized = json.dumps(case, ensure_ascii=False, sort_keys=True)
    if any(pattern.search(serialized) for pattern in _SENSITIVE_PATTERNS):
        raise ContextualizerBenchmarkError(f"{case_id}: sensitive or machine-local data detected")


def validate_dataset(cases: list[dict[str, Any]], *, enforce_totals: bool = True) -> None:
    for case in cases:
        validate_case(case)
    ids = [case["id"] for case in cases]
    if len(ids) != len(set(ids)):
        raise ContextualizerBenchmarkError("case IDs must be unique")
    semantic_inputs = [
        json.dumps(
            {"history": case["history"], "query": case["query"]},
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        for case in cases
    ]
    if len(semantic_inputs) != len(set(semantic_inputs)):
        raise ContextualizerBenchmarkError("exact history/query duplicates are forbidden")
    if not enforce_totals:
        return
    if len(cases) != 40:
        raise ContextualizerBenchmarkError("contextualizer-benchmark-v1 must contain 40 cases")
    if Counter(case["category"] for case in cases) != Counter(CATEGORY_COUNTS):
        raise ContextualizerBenchmarkError("category counts do not match v1")
    if Counter(case["split"] for case in cases) != Counter(SPLIT_COUNTS):
        raise ContextualizerBenchmarkError("split counts do not match v1")


def load_benchmark() -> list[dict[str, Any]]:
    cases = load_jsonl(MASTER_DATASET)
    validate_dataset(cases)
    return cases


def verify_frozen_artifacts() -> dict[str, Any]:
    try:
        manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as error:
        raise ContextualizerBenchmarkError("manifest is invalid") from error
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
        raise ContextualizerBenchmarkError("manifest keys do not match v1")
    if (
        manifest["benchmarkName"] != BENCHMARK_NAME
        or manifest["benchmarkVersion"] != BENCHMARK_VERSION
        or manifest["totalCases"] != 40
        or manifest["splitCounts"] != SPLIT_COUNTS
        or manifest["categoryCounts"] != CATEGORY_COUNTS
    ):
        raise ContextualizerBenchmarkError("manifest metadata does not match v1")
    expected_files = {
        MASTER_DATASET.name: MASTER_DATASET,
        DEV_DATASET.name: DEV_DATASET,
        HOLDOUT_DATASET.name: HOLDOUT_DATASET,
    }
    if not isinstance(manifest["sha256"], dict) or set(manifest["sha256"]) != set(expected_files):
        raise ContextualizerBenchmarkError("manifest hash set does not match v1")
    for name, path in expected_files.items():
        if sha256_file(path) != manifest["sha256"][name]:
            raise ContextualizerBenchmarkError(f"frozen artifact changed: {name}")

    master = load_benchmark()
    dev = load_jsonl(DEV_DATASET)
    holdout = load_jsonl(HOLDOUT_DATASET)
    validate_dataset(dev, enforce_totals=False)
    validate_dataset(holdout, enforce_totals=False)
    if dev != [case for case in master if case["split"] == "dev"]:
        raise ContextualizerBenchmarkError("Dev projection drift")
    if holdout != [case for case in master if case["split"] == "holdout"]:
        raise ContextualizerBenchmarkError("Holdout projection drift")
    if len(dev) != 30 or len(holdout) != 10:
        raise ContextualizerBenchmarkError("split counts do not match frozen v1")
    return manifest

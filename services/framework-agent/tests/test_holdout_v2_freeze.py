"""Metadata-only integrity checks; never evaluate or print Holdout v2 cases."""

from __future__ import annotations

import copy
import json
from collections import Counter
from pathlib import Path

from evals.schema import (
    DATASET_DIR,
    load_jsonl,
    sha256_file,
    validate_dataset,
    verify_frozen_artifacts,
)

DATASET = DATASET_DIR / "holdout-v2.jsonl"
MANIFEST = DATASET_DIR / "holdout-v2-manifest.json"
FROZEN_SHA256 = "401ff082c057d0f11b2849cd97c88471f94eda2104d31dc914b39b5fd9a7becd"
CATEGORY_COUNTS = {
    "menu": 8,
    "rag": 8,
    "action": 7,
    "multi_turn": 8,
    "safety": 7,
    "smalltalk": 2,
}


def test_routing_contract_exists() -> None:
    contract = Path(__file__).resolve().parents[3] / "docs/framework/ROUTING_CONTRACT.md"
    assert contract.is_file()
    assert "Routing != Execution Authorization" in contract.read_text(encoding="utf-8")


def test_holdout_v2_count_categories_schema_and_unique_ids() -> None:
    cases = load_jsonl(DATASET)
    validate_dataset(cases, enforce_totals=False)

    assert len(cases) == 40
    assert Counter(case["category"] for case in cases) == Counter(CATEGORY_COUNTS)
    assert len({case["id"] for case in cases}) == 40
    assert all(case["split"] == "holdout" and case["goldenE2E"] is False for case in cases)


def test_holdout_v2_has_no_exact_query_or_id_overlap_with_v1() -> None:
    new_cases = load_jsonl(DATASET)
    existing = load_jsonl(DATASET_DIR / "dev.jsonl") + load_jsonl(DATASET_DIR / "holdout.jsonl")
    new_queries = [case["input"]["query"].strip() for case in new_cases]
    old_queries = {case["input"]["query"].strip() for case in existing}

    if len(set(new_queries)) != len(new_queries) or set(new_queries) & old_queries:
        raise AssertionError("Holdout v2 contains an exact duplicate query")
    if {case["id"] for case in new_cases} & {case["id"] for case in existing}:
        raise AssertionError("Holdout v2 contains a reused case ID")


def test_holdout_v2_sha256_is_frozen() -> None:
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))

    assert manifest["benchmarkName"] == "hybrid-router-holdout-v2"
    assert manifest["holdoutVersion"] == 2
    assert manifest["totalCases"] == 40
    assert manifest["categoryCounts"] == CATEGORY_COUNTS
    assert manifest["sha256"] == {"holdout-v2.jsonl": FROZEN_SHA256}
    assert sha256_file(DATASET) == FROZEN_SHA256


def test_loading_and_mutating_memory_does_not_change_holdout_v2_file() -> None:
    before = sha256_file(DATASET)
    cases = load_jsonl(DATASET)
    changed_in_memory = copy.deepcopy(cases)
    changed_in_memory[0]["expected"]["allowedRoutes"] = []

    assert sha256_file(DATASET) == before == FROZEN_SHA256
    if load_jsonl(DATASET) == changed_in_memory:
        raise AssertionError("Holdout v2 loader mutated frozen data")


def test_original_benchmark_freeze_remains_valid() -> None:
    manifest = verify_frozen_artifacts()
    assert manifest["splitCounts"] == {"dev": 80, "holdout": 40}


def test_historical_hybrid_reports_remain_unchanged() -> None:
    reports = DATASET_DIR.parent / "reports"
    expected_hashes = {
        "hybrid-router-dev-v1.md": (
            "f40d4fe692a4a847b42a74ee8d438e7b926dfe1d418c21684aae2a6f2fa5f1b7"
        ),
        "hybrid-router-dev-live-v1.md": (
            "e097aa97b413f9db17d87eb679793b41a57b577d09635eac61796d28ec2abf5a"
        ),
        "hybrid-router-holdout-live-v1.md": (
            "275af6f5d8786269b060df234701c9376693ef4ea4b623c32ae5e6edf23c1706"
        ),
    }
    assert {name: sha256_file(reports / name) for name in expected_hashes} == expected_hashes

"""Metadata-only Holdout integrity tests; never print or evaluate frozen cases."""

from __future__ import annotations

import copy
import json
from collections import Counter
from pathlib import Path

from evals.contextualizer.schema import (
    HOLDOUT_DATASET,
    MANIFEST,
    load_jsonl,
    sha256_file,
    validate_dataset,
)

FROZEN_HOLDOUT_SHA256 = "67a7afe49b8f6d697b79b5152317754a7031eb9986d04188277cd3f0fee18142"
HOLDOUT_CATEGORY_COUNTS = {
    "pronoun_reference": 1,
    "entity_ellipsis": 2,
    "action_continuation": 1,
    "entity_switch": 1,
    "user_correction": 1,
    "multi_entity_ambiguity": 1,
    "no_history_ambiguity": 2,
    "already_standalone": 1,
}


def test_holdout_count_categories_schema_and_unique_ids() -> None:
    cases = load_jsonl(HOLDOUT_DATASET)
    validate_dataset(cases, enforce_totals=False)
    assert len(cases) == 10
    assert Counter(case["category"] for case in cases) == Counter(HOLDOUT_CATEGORY_COUNTS)
    assert len({case["id"] for case in cases}) == 10
    assert all(case["split"] == "holdout" for case in cases)


def test_holdout_sha256_is_frozen() -> None:
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    assert manifest["benchmarkName"] == "contextualizer-benchmark-v1"
    assert manifest["totalCases"] == 40
    assert manifest["splitCounts"] == {"dev": 30, "holdout": 10}
    assert manifest["sha256"]["holdout.jsonl"] == FROZEN_HOLDOUT_SHA256
    assert sha256_file(HOLDOUT_DATASET) == FROZEN_HOLDOUT_SHA256


def test_loading_and_mutating_memory_does_not_change_holdout_file(tmp_path: Path) -> None:
    before = sha256_file(HOLDOUT_DATASET)
    cases = load_jsonl(HOLDOUT_DATASET)
    changed = copy.deepcopy(cases)
    changed[0]["query"] = "内存中的变更"
    copy_path = tmp_path / "holdout-copy.jsonl"
    copy_path.write_text("\n", encoding="utf-8")

    assert changed != cases
    assert sha256_file(HOLDOUT_DATASET) == before == FROZEN_HOLDOUT_SHA256

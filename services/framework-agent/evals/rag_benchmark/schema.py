"""Frozen RAG v1 contracts. Dev loading never opens another split."""

from __future__ import annotations

import copy
import hashlib
import json
import math
import re
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[4]
BASE = Path(__file__).resolve().parent
MANIFEST = BASE / "datasets/manifest-v1.json"
MANIFEST_SHA256 = "9917b50dd645dd0741539f9b1411a65764b9b67cc8ea823d583f207eb0907b62"
CATEGORIES = {
    "direct_fact": 8,
    "paraphrase": 7,
    "multi_evidence": 6,
    "similar_dish": 5,
    "unsupported_inference": 5,
    "out_of_scope": 4,
    "live_fact_boundary": 5,
}
COUNTS = {"dev": 30, "holdout": 10}
PROFILES = {"default", "lemon_repriced", "lemon_sold_out"}
NO_ANSWER = "当前提供的知识不足以回答这个问题。"
SENSITIVE = re.compile(
    r"\bsk-[A-Za-z0-9_-]{12,}|\b(?:ghp|github_pat)_[A-Za-z0-9_]{12,}|"
    r"Bearer\s+[A-Za-z0-9._-]{12,}|-----BEGIN .*PRIVATE KEY-----|"
    r"conversationToken|reasoning_content",
    re.IGNORECASE,
)


class BenchmarkError(ValueError):
    """Fixed safe errors only; never include model output or query text."""


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def knowledge() -> dict[str, dict[str, Any]]:
    rows = json.loads((BASE / "fixtures/knowledge.json").read_text())
    if len(rows) != 21 or any(
        r.get("verified") is not True or r.get("sourceVersion") != 1 for r in rows
    ):
        raise BenchmarkError("reviewed knowledge snapshot invalid")
    by_id = {r["knowledgeId"]: r for r in rows}
    if len(by_id) != len(rows):
        raise BenchmarkError("duplicate knowledge identity")
    return by_id


def live_dishes(profile: str) -> list[dict[str, Any]]:
    if profile not in PROFILES:
        raise BenchmarkError("unknown local live-fact profile")
    rows = copy.deepcopy(json.loads((BASE / "fixtures/dishes.json").read_text()))
    tea = next(row for row in rows if row["_id"] == "dish-4")
    if profile == "lemon_repriced":
        tea["price"] = 30.5
    elif profile == "lemon_sold_out":
        tea["status"] = "sold_out"
    return rows


def validate_cases(rows: list[dict[str, Any]], split: str) -> None:
    source = knowledge()
    if not isinstance(rows, list) or split not in COUNTS or len(rows) != COUNTS[split]:
        raise BenchmarkError("split count invalid")
    ids, queries = set(), set()
    for row in rows:
        if not isinstance(row, dict) or set(row) != {
            "benchmarkVersion",
            "id",
            "split",
            "category",
            "query",
            "liveProfile",
            "expected",
        }:
            raise BenchmarkError("case schema invalid")
        if (
            type(row["benchmarkVersion"]) is not int
            or row["benchmarkVersion"] != 1
            or row["split"] != split
            or not isinstance(row["category"], str)
            or row["category"] not in CATEGORIES
            or not isinstance(row["liveProfile"], str)
            or row["liveProfile"] not in PROFILES
        ):
            raise BenchmarkError("case metadata invalid")
        if (
            not isinstance(row["id"], str)
            or not row["id"].startswith(f"rag_{split}_")
            or row["id"] in ids
        ):
            raise BenchmarkError("duplicate or invalid case identity")
        query = row["query"]
        if (
            not isinstance(query, str)
            or not 1 <= len(query.strip()) <= 200
            or query.strip() in queries
            or SENSITIVE.search(query)
        ):
            raise BenchmarkError("duplicate or unsafe query")
        ids.add(row["id"])
        queries.add(query.strip())
        e = row["expected"]
        if (
            not isinstance(e, dict)
            or set(e)
            != {
                "knowledgeAnswerable",
                "answerable",
                "relevantKnowledgeIds",
                "requiredEvidenceGroups",
                "basis",
            }
            or type(e["answerable"]) is not bool
            or type(e["knowledgeAnswerable"]) is not bool
        ):
            raise BenchmarkError("expected contract invalid")
        rel, groups = e["relevantKnowledgeIds"], e["requiredEvidenceGroups"]
        if (
            not isinstance(rel, list)
            or any(not isinstance(k, str) or k not in source for k in rel)
            or len(set(rel)) != len(rel)
        ):
            raise BenchmarkError("relevance IDs invalid")
        if not isinstance(groups, list) or any(
            not isinstance(g, list)
            or not g
            or any(not isinstance(k, str) or k not in rel for k in g)
            or len(set(g)) != len(g)
            for g in groups
        ):
            raise BenchmarkError("evidence groups invalid")
        if set(rel) != {k for g in groups for k in g} or e["knowledgeAnswerable"] != bool(groups):
            raise BenchmarkError("evidence labels inconsistent")
        if e["answerable"] and not groups:
            raise BenchmarkError("answerable without supported evidence")
        available = {d["_id"] for d in live_dishes(row["liveProfile"]) if d["status"] == "on_sale"}
        allowed = {
            k for k, v in source.items() if v["scope"] == "restaurant" or v["dishId"] in available
        }
        eligible = bool(groups) and all(set(group) & allowed for group in groups)
        if bool(e["answerable"]) != eligible:
            raise BenchmarkError("live policy and evidence label inconsistent")
        basis = (
            "reviewed-knowledge-v1"
            if eligible
            else "live-policy-blocked"
            if groups
            else "no-renderable-knowledge-answer"
        )
        if e["basis"] != basis:
            raise BenchmarkError("label basis invalid")


def load_split(split: str = "dev") -> list[dict[str, Any]]:
    if split not in COUNTS:
        raise BenchmarkError("invalid split")
    if digest(MANIFEST) != MANIFEST_SHA256:
        raise BenchmarkError("frozen manifest hash changed")
    m = json.loads(MANIFEST.read_text())
    paths = [f"datasets/{split}.jsonl", "fixtures/knowledge.json", "fixtures/dishes.json"]
    for name in paths:
        if digest(BASE / name) != m["sha256"][name]:
            raise BenchmarkError("frozen artifact hash changed")
    if digest(ROOT / "docs/rag/knowledge-source.json") != m["sourceSha256"]:
        raise BenchmarkError("production knowledge differs from frozen snapshot")
    rows = [json.loads(line) for line in (BASE / paths[0]).read_text().splitlines() if line.strip()]
    validate_cases(rows, split)
    return rows


def verify_frozen() -> dict[str, Any]:
    """Programmatic integrity only. Never emit or execute Holdout queries/labels."""
    from collections import Counter

    if digest(MANIFEST) != MANIFEST_SHA256:
        raise BenchmarkError("frozen manifest hash changed")
    m = json.loads(MANIFEST.read_text())
    rows = load_split("dev") + load_split("holdout")
    if len({r["id"] for r in rows}) != 40 or len({r["query"] for r in rows}) != 40:
        raise BenchmarkError("cross-split duplicates")
    if (
        dict(Counter(r["category"] for r in rows)) != CATEGORIES
        or m["categoryCounts"] != CATEGORIES
        or m["counts"] != COUNTS
    ):
        raise BenchmarkError("frozen category counts invalid")
    return m


def load_index(path: Path, manifest_path: Path) -> list[dict[str, Any]]:
    """An explicitly exported local snapshot, never generate vectors or contact a database."""
    m = json.loads(manifest_path.read_text())
    if (
        not isinstance(m, dict)
        or m.get("sha256") != digest(path)
        or m.get("sourceSha256") != digest(BASE / "fixtures/knowledge.json")
        or m.get("origin") != "unicloud-knowledge_chunks-export"
        or m.get("embeddingModel") != "qwen3.7-text-embedding-flash"
        or m.get("embeddingDimension") != 512
    ):
        raise BenchmarkError("index snapshot manifest invalid")
    rows = json.loads(path.read_text())
    source = knowledge()
    if (
        not isinstance(rows, list)
        or len(rows) != 21
        or any(not isinstance(r, dict) or not isinstance(r.get("knowledgeId"), str) for r in rows)
        or len({r["knowledgeId"] for r in rows}) != 21
    ):
        raise BenchmarkError("complete exported index required")
    for r in rows:
        s = source.get(r.get("knowledgeId"))
        if s is None or any(
            r.get(k) != s[k]
            for k in (
                "knowledgeId",
                "dishId",
                "scope",
                "type",
                "title",
                "text",
                "verified",
                "sourceVersion",
                "sourceType",
                "sourceFields",
            )
        ):
            raise BenchmarkError("index knowledge drift")
        v = r.get("embedding")
        if (
            r.get("embeddingModel") != m["embeddingModel"]
            or r.get("embeddingDimension") != 512
            or not isinstance(v, list)
            or len(v) != 512
            or any(type(x) not in {int, float} or not math.isfinite(x) for x in v)
            or not any(v)
        ):
            raise BenchmarkError("invalid exported vector")
    return rows

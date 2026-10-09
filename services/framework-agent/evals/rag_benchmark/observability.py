"""Safe Dev-only diagnostics. No scoring changes or generated prose persistence."""

from __future__ import annotations

import math
from typing import Any

from evals.rag_benchmark.schema import BenchmarkError, knowledge

STAGES = {
    "NONE",
    "QUERY_EMBEDDING",
    "RETRIEVAL",
    "GENERATION_REQUEST",
    "GENERATION_VALIDATION",
    "BRIDGE_PROCESS",
    "TIMEOUT",
    "UNKNOWN",
}
CATEGORIES = {
    "NONE",
    "REQUEST_FAILED",
    "HTTP_ERROR",
    "RESPONSE_INVALID",
    "DATA_INVALID",
    "CONFIG_INVALID",
    "IDS_INVALID",
    "LIVE_FACTS_INVALID",
    "LIVE_FACTS_CHANGED",
    "PROCESS_EXIT",
    "PROCESS_START_FAILED",
    "OUTPUT_INVALID",
    "TIMEOUT",
    "UNKNOWN",
}
TIMEOUT_SCOPES = {"NONE", "HTTP_REQUEST", "BRIDGE_PROCESS"}
GENERATION_STATES = {"NOT_STARTED", "NOT_OBSERVED", "COMPLETED"}
DURATION_BUCKETS = {
    "LT_1S",
    "1_TO_5S",
    "5_TO_15S",
    "15_TO_40S",
    "40_TO_100S",
    "GE_100S",
    "NOT_OBSERVED",
}


def duration_bucket(seconds: float) -> str:
    for bound, name in (
        (1, "LT_1S"),
        (5, "1_TO_5S"),
        (15, "5_TO_15S"),
        (40, "15_TO_40S"),
        (100, "40_TO_100S"),
    ):
        if seconds < bound:
            return name
    return "GE_100S"


def validate_diagnostics(value: Any) -> dict[str, Any]:
    fields = {
        "failureStage": STAGES,
        "errorCategory": CATEGORIES,
        "timeoutScope": TIMEOUT_SCOPES,
        "failedOperation": {"NONE", "QUERY_EMBEDDING", "GENERATION_REQUEST", "BRIDGE_PROCESS"},
        "generationState": GENERATION_STATES,
        "durationBucket": DURATION_BUCKETS,
    }
    if not isinstance(value, dict) or set(value) != set(fields) | {"retrievalCompleted"}:
        raise BenchmarkError("Diagnostic schema invalid.")
    if type(value["retrievalCompleted"]) is not bool or any(
        not isinstance(value[key], str) or value[key] not in allowed
        for key, allowed in fields.items()
    ):
        raise BenchmarkError("Diagnostic category invalid.")
    return dict(value)


def safe_checkpoint(rows: Any) -> list[dict[str, Any]] | None:
    """Only a complete, known Top-3 contract may survive a failed child process."""
    source = knowledge()
    if not isinstance(rows, list) or not 1 <= len(rows) <= 3:
        return None
    seen = set()
    for rank, row in enumerate(rows, 1):
        if not isinstance(row, dict) or set(row) != {"rank", "knowledgeId", "similarity"}:
            return None
        kid, score = row["knowledgeId"], row["similarity"]
        if (
            not isinstance(kid, str)
            or kid not in source
            or kid in seen
            or type(row["rank"]) is not int
            or row["rank"] != rank
            or type(score) not in {int, float}
            or not math.isfinite(score)
            or not -1.000001 <= score <= 1.000001
        ):
            return None
        seen.add(kid)
    return [dict(row) for row in rows]


def process_failure(stage: str, category: str, seconds: float, checkpoint=None):
    rows = safe_checkpoint(checkpoint)
    return {
        "status": "error",
        **({"retrieval": rows} if rows else {}),
        "diagnostics": {
            "failureStage": stage,
            "errorCategory": category,
            "timeoutScope": "BRIDGE_PROCESS" if stage == "TIMEOUT" else "NONE",
            "failedOperation": "BRIDGE_PROCESS" if stage == "TIMEOUT" else "NONE",
            "retrievalCompleted": bool(rows),
            # Checkpoint proves retrieval, not whether Generation was reached.
            "generationState": "NOT_OBSERVED",
            "durationBucket": duration_bucket(seconds),
        },
    }


def enrich_dev_result(case, observation, scored):
    """Required IDs are group alternatives, not independently required atomic IDs."""
    if case["split"] != "dev":
        return scored
    result = dict(scored)
    diagnostic = observation.get("diagnostics")
    if diagnostic is not None:
        result["diagnostics"] = validate_diagnostics(diagnostic)
    else:
        # Legacy report cannot reveal failure stage retroactively.
        result["diagnostics"] = {
            "failureStage": "NONE" if observation.get("status") == "ok" else "UNKNOWN",
            "errorCategory": "NONE" if observation.get("status") == "ok" else "UNKNOWN",
            "timeoutScope": "NONE",
            "failedOperation": "NONE",
            "retrievalCompleted": safe_checkpoint(observation.get("retrieval")) is not None,
            "generationState": "COMPLETED"
            if isinstance(observation.get("generation"), dict) and observation.get("status") == "ok"
            else "NOT_OBSERVED",
            "durationBucket": "NOT_OBSERVED",
        }
    groups = case["expected"]["requiredEvidenceGroups"]
    retrieved = [
        r["knowledgeId"] for r in scored["retrievalRanks"] if r["knowledgeId"] in knowledge()
    ]
    used = scored["usedKnowledgeIds"]
    retrieval_observed = safe_checkpoint(observation.get("retrieval")) is not None
    generation_observed = observation.get("status") == "ok" and isinstance(
        observation.get("generation"), dict
    )

    def missing(ids):
        return [list(group) for group in groups if not set(group) & set(ids)]

    missing_retrieved = missing(retrieved) if retrieval_observed else None
    missing_selected = missing(used) if generation_observed else None
    result["evidenceSelection"] = {
        "requiredKnowledgeIds": list(dict.fromkeys(k for group in groups for k in group)),
        "requiredEvidenceGroups": groups,
        "retrievedKnowledgeIds": retrieved,
        "usedKnowledgeIds": used,
        "missingRequiredEvidenceGroups": missing_retrieved,
        "missingRequiredKnowledgeIds": list(
            dict.fromkeys(k for group in missing_retrieved for k in group)
        )
        if missing_retrieved is not None
        else None,
        "missingSelectedEvidenceGroups": missing_selected,
        "extraSelectedKnowledgeIds": [
            k for k in used if k not in case["expected"]["relevantKnowledgeIds"]
        ]
        if generation_observed
        else None,
    }
    return result

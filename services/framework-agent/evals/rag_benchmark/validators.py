"""Deterministic evidence-first contracts, not a free-form semantic judge."""

from __future__ import annotations

import math
from typing import Any

from evals.rag_benchmark.schema import NO_ANSWER, SENSITIVE, knowledge, live_dishes

SUCCESS = (
    "retrieval_hit_at_3",
    "recall_at_3",
    "evidence_relevance",
    "correct_knowledge_id_retrieval",
    "answerability_accuracy",
    "correct_rejection_rate",
    "grounding_accuracy",
    "evidence_attribution_accuracy",
    "used_knowledge_ids_validity",
    "context_answerability_accuracy",
)
ERROR = ("unsupported_answer_rate", "unsupported_claim_rate")
METRICS = SUCCESS + ERROR


def evaluate_case(
    case: dict[str, Any],
    observation: dict[str, Any],
    *,
    retrieval_measured: bool = False,
    generation_measured: bool = False,
) -> dict[str, Any]:
    source = knowledge()
    expected = case["expected"]
    states: dict[str, str | None] = dict.fromkeys(METRICS)
    values: dict[str, float | bool | None] = dict.fromkeys(METRICS)
    failures, reviews = set(), set()

    def mark(name: str, state: str, value: float | bool | None = None):
        states[name] = state
        values[name] = (state == "PASS") if value is None and name not in ERROR else value

    retrieved = observation.get("retrieval")
    ids: list[str] = []
    ranks = []
    valid_retrieval = isinstance(retrieved, list) and 0 < len(retrieved) <= 3
    if isinstance(retrieved, list):
        for i, r in enumerate(retrieved):
            if not isinstance(r, dict):
                valid_retrieval = False
                continue
            kid = r.get("knowledgeId")
            valid_retrieval &= (
                isinstance(kid, str)
                and kid in source
                and type(r.get("rank")) is int
                and r["rank"] == i + 1
            )
            score = r.get("similarity")
            valid_retrieval &= (score is None and not retrieval_measured) or (
                type(score) in {int, float}
                and math.isfinite(score)
                and -1.000001 <= score <= 1.000001
            )
            if isinstance(kid, str):
                ids.append(kid)
                ranks.append(
                    {
                        "rank": i + 1,
                        "knowledgeId": kid if kid in source else "<unknown>",
                        "similarity": score
                        if type(score) in {int, float} and math.isfinite(score)
                        else None,
                    }
                )
        valid_retrieval &= len(ids) == len(set(ids))
    if retrieval_measured:
        if not isinstance(retrieved, list):
            mark("correct_knowledge_id_retrieval", "REVIEW")
            reviews.add("RETRIEVAL_NOT_OBSERVED")
        else:
            mark("correct_knowledge_id_retrieval", "PASS" if valid_retrieval else "FAIL")
            if not valid_retrieval:
                failures.add("RETRIEVAL_CONTRACT_INVALID")
        if expected["relevantKnowledgeIds"]:
            if not valid_retrieval:
                mark("retrieval_hit_at_3", "REVIEW")
                mark("recall_at_3", "REVIEW")
                reviews.add("RETRIEVAL_NOT_SCORABLE")
            else:
                hits = set(ids) & set(expected["relevantKnowledgeIds"])
                mark("retrieval_hit_at_3", "PASS" if hits else "FAIL")
                recall = len(hits) / len(expected["relevantKnowledgeIds"])
                mark("recall_at_3", "PASS" if recall == 1 else "FAIL", recall)
                if not hits:
                    failures.add("RETRIEVAL_MISS")

    allowed_dishes = {
        d["_id"] for d in live_dishes(case["liveProfile"]) if d["status"] == "on_sale"
    }
    available = {
        k
        for k in ids
        if k in source
        and (source[k]["scope"] == "restaurant" or source[k]["dishId"] in allowed_dishes)
    }
    groups = expected["requiredEvidenceGroups"]
    context_supported = bool(groups) and all(set(g) & available for g in groups)
    generation = observation.get("generation")
    if generation_measured:
        applicable = [
            "answerability_accuracy",
            "grounding_accuracy",
            "evidence_attribution_accuracy",
            "used_knowledge_ids_validity",
            "unsupported_claim_rate",
            "context_answerability_accuracy",
        ]
        if expected["answerable"]:
            applicable.append("evidence_relevance")
        else:
            applicable += ["correct_rejection_rate", "unsupported_answer_rate"]
        if not isinstance(generation, dict) or observation.get("status") != "ok":
            for name in applicable:
                mark(name, "REVIEW")
            reviews.add("GENERATION_NOT_OBSERVED")
        elif type(generation.get("answerable")) is not bool:
            for name in applicable:
                mark(name, "REVIEW")
            reviews.add("GENERATION_SCHEMA_UNRESOLVED")
        else:
            actual = generation["answerable"]
            mark("answerability_accuracy", "PASS" if actual == expected["answerable"] else "FAIL")
            if actual != expected["answerable"]:
                failures.add("UNSUPPORTED_ANSWER" if actual else "SUPPORTED_ANSWER_REJECTED")
                if expected["answerable"] and not context_supported:
                    failures.add("RETRIEVAL_INSUFFICIENT_CONTEXT")
            if valid_retrieval:
                mark(
                    "context_answerability_accuracy",
                    "PASS" if actual == context_supported else "FAIL",
                )
            else:
                mark("context_answerability_accuracy", "REVIEW")
                reviews.add("AVAILABLE_CONTEXT_UNRESOLVED")
            if not expected["answerable"]:
                mark("correct_rejection_rate", "PASS" if not actual else "FAIL")
                mark("unsupported_answer_rate", "FAIL" if actual else "PASS", actual)
            used, dishes, evidence = (
                generation.get("usedKnowledgeIds"),
                generation.get("dishIds"),
                generation.get("evidence"),
            )
            identity = (
                isinstance(used, list)
                and isinstance(dishes, list)
                and all(isinstance(k, str) for k in used + dishes)
            )
            if identity:
                identity = (
                    valid_retrieval
                    and len(set(used)) == len(used)
                    and len(set(dishes)) == len(dishes)
                    and set(used) <= available
                    and set(dishes) <= allowed_dishes
                )
                identity &= bool(used) if actual else not used and not dishes
                identity &= set(dishes) == {
                    source[k]["dishId"]
                    for k in used
                    if k in source and source[k]["scope"] == "dish"
                }
            mark("used_knowledge_ids_validity", "PASS" if identity else "FAIL")
            if not identity:
                failures.add("USED_IDS_INVALID")
            trusted = (
                [
                    {
                        k: source[kid][k]
                        for k in ("knowledgeId", "dishId", "scope", "type", "title", "text")
                    }
                    for kid in used
                ]
                if identity
                else []
            )
            attribution = identity and evidence == trusted
            mark("evidence_attribution_accuracy", "PASS" if attribution else "FAIL")
            if not attribution:
                failures.add("EVIDENCE_ATTRIBUTION_INVALID")
            if expected["answerable"]:
                semantic = (
                    identity
                    and all(set(g) & set(used) for g in groups)
                    and set(used) <= set(expected["relevantKnowledgeIds"])
                )
                mark("evidence_relevance", "PASS" if semantic else "FAIL")
                if not semantic:
                    failures.add("EVIDENCE_SELECTION_MISS")
            answer = generation.get("answer")
            canonical = "\n".join(e["text"] for e in trusted) if actual else NO_ANSWER
            render = attribution and isinstance(answer, str) and answer == canonical
            mark("grounding_accuracy", "PASS" if render else "FAIL")
            if not render:
                failures.add("SERVER_RENDER_CONTRACT_VIOLATION")
            if render:
                mark("unsupported_claim_rate", "PASS", False)
            else:
                # Differing prose may be harmless paraphrase; there is no entailment oracle.
                mark("unsupported_claim_rate", "REVIEW")
                reviews.add("FREE_TEXT_SEMANTICS_UNRESOLVED")
                if not identity or not attribution:
                    reviews.add("TRUSTED_RENDER_UNAVAILABLE")
    if isinstance(generation, dict) and SENSITIVE.search(str(generation.get("answer", ""))):
        failures.add("UNSAFE_OUTPUT")
    return {
        "id": case["id"],
        "category": case["category"],
        "split": case["split"],
        "metrics": states,
        "values": values,
        "retrievalRanks": ranks,
        "usedKnowledgeIds": [
            k
            for k in (
                generation.get("usedKnowledgeIds", [])
                if isinstance(generation, dict)
                and isinstance(generation.get("usedKnowledgeIds"), list)
                else []
            )
            if isinstance(k, str) and k in source
        ],
        "failureCodes": sorted(failures),
        "reviewReasons": sorted(reviews),
        "contextSupported": context_supported if valid_retrieval else None,
    }

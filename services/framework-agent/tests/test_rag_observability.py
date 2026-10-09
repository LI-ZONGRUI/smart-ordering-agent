"""Offline diagnostics only. All fixtures are synthetic or Dev; Holdout cannot be opened."""

from __future__ import annotations

import copy
import json
import socket
import subprocess
from pathlib import Path
from types import SimpleNamespace

import pytest

from evals.rag_benchmark import runner, schema
from evals.rag_benchmark.metrics import summarize
from evals.rag_benchmark.observability import enrich_dev_result, safe_checkpoint
from evals.rag_benchmark.report import render
from evals.rag_benchmark.validators import evaluate_case


@pytest.fixture(autouse=True)
def isolated(monkeypatch):
    def deny(*args, **kwargs):
        raise AssertionError("network forbidden")

    monkeypatch.setattr(socket.socket, "connect", deny)
    original = Path.open

    def guarded(path, *args, **kwargs):
        if "holdout" in path.name.lower() and path.suffix in {".json", ".jsonl"}:
            raise AssertionError("Holdout cannot be opened")
        return original(path, *args, **kwargs)

    monkeypatch.setattr(Path, "open", guarded)


@pytest.fixture
def case():
    return schema.load_split("dev")[0]


def ranks(ids):
    return [
        {"rank": n + 1, "knowledgeId": kid, "similarity": 0.8 - n * 0.1}
        for n, kid in enumerate(ids)
    ]


def observation(ids, used):
    source = schema.knowledge()
    evidence = [
        {k: source[i][k] for k in ("knowledgeId", "dishId", "scope", "type", "title", "text")}
        for i in used
    ]
    return {
        "status": "ok",
        "retrieval": ranks(ids),
        "generation": {
            "answerable": True,
            "answer": "\n".join(e["text"] for e in evidence),
            "dishIds": list(dict.fromkeys(e["dishId"] for e in evidence if e["scope"] == "dish")),
            "usedKnowledgeIds": used,
            "evidence": evidence,
        },
    }


def scored(case, obs):
    return evaluate_case(case, obs, retrieval_measured=True, generation_measured=True)


def test_generation_failure_preserves_retrieval_scoring_and_denominators(case):
    ids = case["expected"]["relevantKnowledgeIds"]
    bad = {"status": "error", "retrieval": ranks(ids)}
    result = scored(case, bad)
    assert result["metrics"]["retrieval_hit_at_3"] == "PASS"
    assert result["metrics"]["grounding_accuracy"] == "REVIEW"
    assert "RETRIEVAL_NOT_OBSERVED" not in result["reviewReasons"]
    assert "GENERATION_NOT_OBSERVED" in result["reviewReasons"]
    summary = summarize([result])["metrics"]
    assert summary["grounding_accuracy"]["applicable"] == 1
    assert summary["grounding_accuracy"]["conservativeAutomaticPassRate"] == 0
    enriched = enrich_dev_result(case, bad, result)
    assert enriched["evidenceSelection"]["extraSelectedKnowledgeIds"] is None
    assert enriched["evidenceSelection"]["missingSelectedEvidenceGroups"] is None


def test_unobserved_retrieval_not_reported_as_missing_required(case):
    obs = {"status": "error", "errorCode": "private-message"}
    result = enrich_dev_result(case, obs, scored(case, obs))
    assert result["evidenceSelection"]["missingRequiredKnowledgeIds"] is None
    assert result["diagnostics"]["failureStage"] == "UNKNOWN"
    assert not result["diagnostics"]["retrievalCompleted"]
    assert "private-message" not in render({}, summarize([result]), [result])


def test_missing_required_and_additional_selection_are_separate():
    case = next(c for c in schema.load_split("dev") if c["id"] == "rag_dev_multi_evidence_001")
    obs = observation(
        ["dish-1-ingredients", "dish-1-description", "dish-5-ingredients"],
        ["dish-1-description", "dish-1-ingredients"],
    )
    result = enrich_dev_result(case, obs, scored(case, obs))
    selection = result["evidenceSelection"]
    assert selection["missingRequiredKnowledgeIds"] == ["dish-1-taste"]
    assert selection["missingSelectedEvidenceGroups"] == [["dish-1-taste"]]
    assert selection["extraSelectedKnowledgeIds"] == ["dish-1-description"]
    assert result["values"]["recall_at_3"] == 0.5
    assert result["failureCodes"] == ["EVIDENCE_SELECTION_MISS"]


def test_alternative_evidence_group_not_falsely_marked_missing(case):
    case = copy.deepcopy(case)
    case["expected"]["relevantKnowledgeIds"] = ["dish-1-description", "dish-1-ingredients"]
    case["expected"]["requiredEvidenceGroups"] = [["dish-1-description", "dish-1-ingredients"]]
    obs = observation(["dish-1-ingredients"], ["dish-1-ingredients"])
    result = enrich_dev_result(case, obs, scored(case, obs))
    assert result["evidenceSelection"]["missingRequiredKnowledgeIds"] == []
    assert result["evidenceSelection"]["missingSelectedEvidenceGroups"] == []
    assert result["metrics"]["evidence_relevance"] == "PASS"


def test_missing_group_retains_alternative_semantics(case):
    case = copy.deepcopy(case)
    group = ["dish-1-description", "dish-1-ingredients"]
    case["expected"]["relevantKnowledgeIds"] = group
    case["expected"]["requiredEvidenceGroups"] = [group]
    obs = observation(["dish-4-taste"], ["dish-4-taste"])
    selection = enrich_dev_result(case, obs, scored(case, obs))["evidenceSelection"]
    assert selection["missingRequiredEvidenceGroups"] == [group]
    assert selection["missingRequiredKnowledgeIds"] == group


def test_order_and_extra_diagnostics_do_not_change_old_scores(case):
    ids = ["dish-1-ingredients", "dish-1-description"]
    obs = observation(ids, ids[::-1])
    old = scored(case, obs)
    new = enrich_dev_result(case, obs, old)
    assert all(new[key] == value for key, value in old.items())
    assert summarize([old]) == summarize([new])
    assert new["evidenceSelection"]["usedKnowledgeIds"] == ids[::-1]
    assert new["metrics"]["evidence_relevance"] == "FAIL"


def test_diagnostics_are_dev_only_without_loading_other_split(case):
    case = copy.deepcopy(case)
    case["split"] = "holdout"  # Synthetic metadata only, no frozen cases loaded.
    obs = observation(["dish-1-ingredients"], ["dish-1-ingredients"])
    old = scored(case, obs)
    assert enrich_dev_result(case, obs, old) == old


def test_default_runner_remains_offline(monkeypatch):
    monkeypatch.setattr(runner, "invoke_live", lambda *args: pytest.fail("must not run model"))
    result = runner.run(runner.parser().parse_args([]))
    assert result["metadata"]["mode"] == "validation-only"
    assert result["metadata"]["casesInScope"] == 30


def test_holdout_rejected_before_loading(monkeypatch):
    monkeypatch.setattr(runner, "load_split", lambda *args: pytest.fail("must not load"))
    with pytest.raises(schema.BenchmarkError, match="explicit confirmation"):
        runner.run(runner.parser().parse_args(["--split", "holdout"]))


def checkpoint():
    return json.dumps({"kind": "retrieval_checkpoint", "retrieval": ranks(["dish-1-taste"])}) + "\n"


@pytest.mark.parametrize("mode", ["timeout", "nonzero", "invalid", "start"])
def test_child_errors_sanitized_and_checkpoint_retained(monkeypatch, case, mode):
    private = "private-key reasoning_content conversationToken internal-path"

    def fake_child(*args, **kwargs):
        assert kwargs["timeout"] == 100
        if mode == "timeout":
            raise subprocess.TimeoutExpired("node", 100, output=checkpoint().encode())
        if mode == "start":
            raise OSError(private)
        return SimpleNamespace(
            returncode=1 if mode == "nonzero" else 0, stdout=checkpoint() + private, stderr=private
        )

    monkeypatch.setattr(runner.subprocess, "run", fake_child)
    result = runner.invoke_live(case, [], "live-generation")
    assert result["status"] == "error"
    assert "generation" not in result
    assert ("retrieval" in result) == (mode != "start")
    assert result["diagnostics"]["failureStage"] == (
        "TIMEOUT" if mode == "timeout" else "BRIDGE_PROCESS"
    )
    assert result["diagnostics"]["timeoutScope"] == (
        "BRIDGE_PROCESS" if mode == "timeout" else "NONE"
    )
    assert private not in json.dumps(result)
    public = enrich_dev_result(case, result, scored(case, result))
    assert private not in render({}, summarize([public]), [public])


def test_child_timeout_without_checkpoint_does_not_invent_retrieval(monkeypatch, case):
    def fake(*args, **kwargs):
        raise subprocess.TimeoutExpired("node", 100)

    monkeypatch.setattr(runner.subprocess, "run", fake)
    result = runner.invoke_live(case, [], "live-generation")
    assert "retrieval" not in result and "generation" not in result
    assert not result["diagnostics"]["retrievalCompleted"]


@pytest.mark.parametrize("mutation", ["vector", "unknown_id", "duplicate", "nan", "bad_rank"])
def test_checkpoint_whitelist_rejects_unsafe_or_invalid_rows(mutation):
    rows = ranks(["dish-1-taste", "dish-1-description"])
    if mutation == "vector":
        rows[0]["embedding"] = [1] * 512
    elif mutation == "unknown_id":
        rows[0]["knowledgeId"] = "private-unknown-id"
    elif mutation == "duplicate":
        rows[1]["knowledgeId"] = rows[0]["knowledgeId"]
    elif mutation == "nan":
        rows[0]["similarity"] = float("nan")
    else:
        rows[0]["rank"] = 5
    assert safe_checkpoint(rows) is None


def test_old_and_checkpoint_child_output_supported(monkeypatch, case):
    obs = observation(["dish-1-ingredients"], ["dish-1-ingredients"])
    for prefix in ("", checkpoint()):
        monkeypatch.setattr(
            runner.subprocess,
            "run",
            lambda *args, _prefix=prefix, **kwargs: SimpleNamespace(
                returncode=0, stdout=_prefix + json.dumps(obs)
            ),
        )
        assert runner.invoke_live(case, [], "live-generation") == obs


def test_unknown_stage_and_arbitrary_diagnostic_text_rejected():
    result = runner.process_failure("UNKNOWN", "UNKNOWN", 0)
    runner.validate_observation(result)
    for key in ("failureStage", "errorCategory", "durationBucket"):
        invalid = copy.deepcopy(result)
        invalid["diagnostics"][key] = "private-exception"
        with pytest.raises(schema.BenchmarkError):
            runner.validate_observation(invalid)
    result["diagnostics"]["rawResponse"] = "secret"
    with pytest.raises(schema.BenchmarkError):
        runner.validate_observation(result)


def test_frozen_dev_manifest_and_source_unchanged():
    # load_split validates ONLY Dev and known fixtures; does not invoke verify_frozen().
    assert len(schema.load_split("dev")) == 30
    assert schema.digest(schema.MANIFEST) == schema.MANIFEST_SHA256
    assert schema.digest(schema.BASE / "fixtures/knowledge.json") == schema.digest(
        schema.ROOT / "docs/rag/knowledge-source.json"
    )


@pytest.mark.parametrize(
    "seconds,expected",
    [
        (0, "LT_1S"),
        (1, "1_TO_5S"),
        (5, "5_TO_15S"),
        (15, "15_TO_40S"),
        (40, "40_TO_100S"),
        (100, "GE_100S"),
    ],
)
def test_duration_is_bucket_not_raw_request_time(seconds, expected):
    from evals.rag_benchmark.observability import duration_bucket

    assert duration_bucket(seconds) == expected


def test_partial_checkpoint_or_sensitive_fields_are_not_recovered():
    assert runner.checkpoint_from_output('{"kind":"retrieval_checkpoint","retrieval":[') is None
    assert (
        runner.checkpoint_from_output(
            json.dumps(
                {
                    "kind": "retrieval_checkpoint",
                    "retrieval": ranks(["dish-1-taste"]),
                    "rawResponse": "private",
                }
            )
        )
        is None
    )


def test_checkpoint_only_child_cannot_be_mistaken_for_final_observation(monkeypatch, case):
    monkeypatch.setattr(
        runner.subprocess,
        "run",
        lambda *args, **kwargs: SimpleNamespace(returncode=0, stdout=checkpoint()),
    )
    result = runner.invoke_live(case, [], "live-generation")
    assert result["status"] == "error"
    assert result["diagnostics"]["errorCategory"] == "OUTPUT_INVALID"
    assert result["diagnostics"]["retrievalCompleted"]
    assert "generation" not in result

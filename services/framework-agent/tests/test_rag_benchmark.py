"""Independent offline RAG contracts. No old Holdout or model/network execution."""

from __future__ import annotations

import copy
import json
import socket
import subprocess
from pathlib import Path

import pytest

from evals.rag_benchmark import runner, schema
from evals.rag_benchmark.metrics import summarize
from evals.rag_benchmark.report import render
from evals.rag_benchmark.validators import METRICS, evaluate_case


@pytest.fixture(autouse=True)
def deny_network(monkeypatch):
    def denied(*args, **kwargs):
        raise AssertionError("network forbidden in offline benchmark tests")

    monkeypatch.setattr(socket.socket, "connect", denied)
    monkeypatch.setattr(runner, "invoke_live", denied)


@pytest.fixture
def cases():
    return schema.load_split("dev")


def positive(cases):
    return next(c for c in cases if c["expected"]["answerable"])


def observation(case, *, used=None, retrieved=None, answerable=True):
    # Synthetic unit-test observation, never a real retrieval benchmark result.
    source = schema.knowledge()
    if retrieved is None:
        retrieved = case["expected"]["relevantKnowledgeIds"][:3]
    if used is None:
        used = [g[0] for g in case["expected"]["requiredEvidenceGroups"]] if answerable else []
    evidence = [
        {k: source[i][k] for k in ("knowledgeId", "dishId", "scope", "type", "title", "text")}
        for i in used
        if i in source
    ]
    dishes = list(dict.fromkeys(e["dishId"] for e in evidence if e["scope"] == "dish"))
    return {
        "status": "ok",
        "retrieval": [
            {"rank": n + 1, "knowledgeId": i, "similarity": 0.8 - n * 0.1}
            for n, i in enumerate(retrieved)
        ],
        "generation": {
            "answerable": answerable,
            "answer": "\n".join(e["text"] for e in evidence) if answerable else schema.NO_ANSWER,
            "dishIds": dishes,
            "usedKnowledgeIds": used,
            "evidence": evidence,
        },
    }


def score(case, obs):
    return evaluate_case(case, obs, retrieval_measured=True, generation_measured=True)


def test_default_validation_is_not_fake_accuracy(monkeypatch):
    result = runner.run(runner.parser().parse_args([]))
    assert result["metadata"]["casesInScope"] == 30
    assert result["metadata"]["mode"] == "validation-only"
    assert all(
        m["value"] is None and m["applicable"] == 0 for m in result["summary"]["metrics"].values()
    )


def test_frozen_integrity_counts_only():
    # Only programmatic integrity of NEW Holdout. No query execution/output or label inspection.
    before = schema.digest(schema.BASE / "datasets/holdout.jsonl")
    manifest = schema.verify_frozen()
    assert manifest["counts"] == {"dev": 30, "holdout": 10}
    assert sum(manifest["categoryCounts"].values()) == 40
    assert before == schema.digest(schema.BASE / "datasets/holdout.jsonl")
    assert before == "db380d9ce60c156e589c3ab0b0a8c4745d4f0bd51e812e95c342105c723f67c9"


def test_dev_loader_does_not_open_holdout(monkeypatch):
    original = Path.read_text

    def guarded(path, *args, **kwargs):
        if path.name == "holdout.jsonl":
            raise AssertionError("Dev must not open Holdout")
        return original(path, *args, **kwargs)

    monkeypatch.setattr(Path, "read_text", guarded)
    assert len(schema.load_split()) == 30


@pytest.mark.parametrize(
    "argv",
    [
        ["--split", "holdout"],
        ["--mode", "live-retrieval"],
        ["--mode", "live-generation", "--live-model"],
        ["--split", "holdout", "--mode", "live-generation", "--live-model", "--confirm-live"],
        ["--split", "holdout", "--confirm-holdout", "--mode", "live-generation", "--confirm-live"],
        ["--live-model"],
    ],
)
def test_confirmations_fail_before_dataset_loading(monkeypatch, argv):
    def forbidden(*args):
        raise AssertionError("loader must not run")

    monkeypatch.setattr(runner, "load_split", forbidden)
    with pytest.raises(schema.BenchmarkError):
        runner.run(runner.parser().parse_args(argv))


def test_holdout_confirmation_accepts_options_without_execution():
    # Validate CLI only, never run this split.
    args = runner.parser().parse_args(["--split", "holdout", "--confirm-holdout"])
    runner.validate_options(args)


def test_live_requires_export_even_after_confirmation():
    with pytest.raises(schema.BenchmarkError, match="index export"):
        runner.validate_options(
            runner.parser().parse_args(
                ["--mode", "live-retrieval", "--live-model", "--confirm-live"]
            )
        )


def test_live_options_with_both_confirmations_only(tmp_path):
    runner.validate_options(
        runner.parser().parse_args(
            [
                "--split",
                "holdout",
                "--confirm-holdout",
                "--mode",
                "live-generation",
                "--live-model",
                "--confirm-live",
                "--index-fixture",
                str(tmp_path / "index.json"),
                "--index-manifest",
                str(tmp_path / "manifest.json"),
            ]
        )
    )


@pytest.mark.parametrize(
    "mutation", ["duplicate", "unknown_evidence", "empty_query", "wrong_label", "wrong_profile"]
)
def test_dataset_schema_rejects_mutations(cases, mutation):
    rows = copy.deepcopy(cases)
    if mutation == "duplicate":
        rows[1]["id"] = rows[0]["id"]
    elif mutation == "unknown_evidence":
        rows[0]["expected"]["relevantKnowledgeIds"] = ["unknown"]
    elif mutation == "empty_query":
        rows[0]["query"] = " "
    elif mutation == "wrong_label":
        rows[0]["expected"]["answerable"] = False
    else:
        rows[0]["liveProfile"] = "production"
    with pytest.raises(schema.BenchmarkError):
        schema.validate_cases(rows, "dev")


def test_true_knowledge_ids_and_supported_groups(cases):
    source = schema.knowledge()
    for case in cases:
        assert set(case["expected"]["relevantKnowledgeIds"]) <= source.keys()
        assert case["expected"]["knowledgeAnswerable"] == bool(
            case["expected"]["requiredEvidenceGroups"]
        )


def test_complete_contract_pass(cases):
    case = positive(cases)
    result = score(case, observation(case))
    assert result["metrics"]["retrieval_hit_at_3"] == "PASS"
    assert result["metrics"]["answerability_accuracy"] == "PASS"
    assert result["metrics"]["grounding_accuracy"] == "PASS"
    assert result["metrics"]["evidence_attribution_accuracy"] == "PASS"
    assert result["metrics"]["used_knowledge_ids_validity"] == "PASS"
    assert result["metrics"]["unsupported_claim_rate"] == "PASS"


def test_recall_partial_still_numeric(cases):
    case = next(c for c in cases if len(c["expected"]["relevantKnowledgeIds"]) > 1)
    one = case["expected"]["relevantKnowledgeIds"][0]
    result = score(case, observation(case, retrieved=[one], used=[one]))
    assert result["values"]["recall_at_3"] == 1 / len(case["expected"]["relevantKnowledgeIds"])


def test_retrieval_found_but_selection_wrong_is_separate(cases):
    case = positive(cases)
    correct = case["expected"]["relevantKnowledgeIds"][0]
    other = "dish-4-ingredients" if correct != "dish-4-ingredients" else "dish-1-taste"
    result = score(case, observation(case, retrieved=[correct, other], used=[other]))
    assert result["metrics"]["retrieval_hit_at_3"] == "PASS"
    assert result["metrics"]["evidence_relevance"] == "FAIL"
    assert result["metrics"]["grounding_accuracy"] == "PASS"  # Lineage, not semantic relevance.


def test_retrieval_miss_rejected_detects_stage(cases):
    case = positive(cases)
    result = score(case, observation(case, retrieved=["dish-4-ingredients"], answerable=False))
    assert result["metrics"]["retrieval_hit_at_3"] == "FAIL"
    assert result["metrics"]["answerability_accuracy"] == "FAIL"
    assert result["metrics"]["context_answerability_accuracy"] == "PASS"
    assert "RETRIEVAL_INSUFFICIENT_CONTEXT" in result["failureCodes"]


def test_false_answer_safe_refusal(cases):
    case = next(c for c in cases if not c["expected"]["answerable"])
    result = score(case, observation(case, retrieved=["dish-4-taste"], answerable=False))
    assert result["metrics"]["correct_rejection_rate"] == "PASS"
    assert result["values"]["unsupported_answer_rate"] is False


def test_unsupported_answer_not_mislabeled_as_text_hallucination(cases):
    case = next(c for c in cases if not c["expected"]["answerable"])
    result = score(case, observation(case, retrieved=["dish-4-taste"], used=["dish-4-taste"]))
    assert result["metrics"]["answerability_accuracy"] == "FAIL"
    assert result["values"]["unsupported_answer_rate"] is True
    assert result["metrics"]["grounding_accuracy"] == "PASS"


@pytest.mark.parametrize(
    "mutation", ["unknown", "outside_top3", "duplicate", "sold_out", "missing_dish"]
)
def test_used_ids_strict_validation(cases, mutation):
    case = positive(cases)
    obs = observation(case)
    if mutation == "unknown":
        obs["generation"]["usedKnowledgeIds"] = ["unknown"]
    elif mutation == "outside_top3":
        obs["generation"]["usedKnowledgeIds"] = ["dish-7-taste"]
    elif mutation == "duplicate":
        obs["generation"]["usedKnowledgeIds"] *= 2
    elif mutation == "sold_out":
        obs = observation(case, retrieved=["dish-8-taste"], used=["dish-8-taste"])
    else:
        obs["generation"]["dishIds"] = []
    assert score(case, obs)["metrics"]["used_knowledge_ids_validity"] == "FAIL"


def test_evidence_exact_source_not_just_name(cases):
    case = positive(cases)
    obs = observation(case)
    obs["generation"]["evidence"][0]["text"] += "解腻"
    result = score(case, obs)
    assert result["metrics"]["evidence_attribution_accuracy"] == "FAIL"


@pytest.mark.parametrize("text", ["柠檬茶解腻。", "一种合法的不同措辞。", "假如适合就点吧。"])
def test_free_form_prose_is_review_not_asserted_hallucination(cases, text):
    case = positive(cases)
    obs = observation(case)
    obs["generation"]["answer"] = text
    result = score(case, obs)
    assert result["metrics"]["grounding_accuracy"] == "FAIL"
    assert result["metrics"]["unsupported_claim_rate"] == "REVIEW"
    assert "FREE_TEXT_SEMANTICS_UNRESOLVED" in result["reviewReasons"]


def test_error_requests_retain_applicable_denominator(cases):
    case = positive(cases)
    good = score(case, observation(case))
    error = score(case, {"status": "error"})
    s = summarize([good, error])["metrics"]["grounding_accuracy"]
    assert s["applicable"] == 2 and s["pass"] == 1 and s["review"] == 1
    assert s["conservativeAutomaticPassRate"] == 0.5
    assert s["determinateCheckCoverage"] == 0.5


def test_offline_metrics_na_without_real_retrieval(cases):
    case = positive(cases)
    result = evaluate_case(case, observation(case), generation_measured=True)
    assert result["metrics"]["recall_at_3"] is None
    assert result["metrics"]["retrieval_hit_at_3"] is None


def test_safe_report_never_contains_model_prose(cases):
    case = positive(cases)
    obs = observation(case)
    obs["generation"]["answer"] = "private-answer-marker reasoning_content"
    result = score(case, obs)
    text = render({"mode": "offline"}, summarize([result]), [result])
    assert "private-answer-marker" not in text
    assert "reasoning_content" not in text
    assert "UNSAFE_OUTPUT" in text
    assert case["query"] not in text
    assert "embedding" not in text


@pytest.mark.parametrize(
    "payload",
    [
        {"status": "ok", "embedding": [1]},
        {
            "status": "ok",
            "retrieval": [
                {"rank": 1, "knowledgeId": "dish-1-taste", "similarity": 1, "embedding": []}
            ],
        },
        {"status": "ok", "rawResponse": "secret"},
        {"status": "ok", "generation": {"reasoning": "no"}},
    ],
)
def test_untrusted_observation_fields_rejected(payload):
    with pytest.raises(schema.BenchmarkError):
        runner.validate_observation(payload)


def test_export_manifest_checks_before_vectors(tmp_path):
    records = tmp_path / "index.json"
    manifest = tmp_path / "index-manifest.json"
    records.write_text("[]")
    manifest.write_text("{}")
    with pytest.raises(schema.BenchmarkError):
        schema.load_index(records, manifest)


def test_export_validation_full_vector_contract(tmp_path):
    # Synthetic vectors test validation only, never feed benchmark runner or claim real accuracy.
    records = [
        dict(
            row,
            embedding=[1.0] + [0.0] * 511,
            embeddingModel="qwen3.7-text-embedding-flash",
            embeddingDimension=512,
        )
        for row in schema.knowledge().values()
    ]
    path = tmp_path / "records.json"
    mf = tmp_path / "manifest.json"

    def write():
        path.write_text(json.dumps(records))
        mf.write_text(
            json.dumps(
                {
                    "sha256": schema.digest(path),
                    "sourceSha256": schema.digest(schema.BASE / "fixtures/knowledge.json"),
                    "origin": "unicloud-knowledge_chunks-export",
                    "embeddingModel": "qwen3.7-text-embedding-flash",
                    "embeddingDimension": 512,
                }
            )
        )

    write()
    assert len(schema.load_index(path, mf)) == 21
    records[0]["embedding"][0] = float("nan")
    write()
    with pytest.raises(schema.BenchmarkError):
        schema.load_index(path, mf)
    records[0]["embedding"] = [0.0] * 512
    write()
    with pytest.raises(schema.BenchmarkError):
        schema.load_index(path, mf)


def test_live_boundary_does_not_accept_generated_index(tmp_path):
    args = runner.parser().parse_args(
        [
            "--mode",
            "live-retrieval",
            "--live-model",
            "--confirm-live",
            "--index-fixture",
            str(tmp_path / "missing.json"),
            "--index-manifest",
            str(tmp_path / "missing-manifest.json"),
        ]
    )
    with pytest.raises(OSError):
        runner.run(args)


def test_report_cannot_overwrite_dataset():
    with pytest.raises(schema.BenchmarkError):
        runner.validate_options(runner.parser().parse_args(["--report", str(schema.MANIFEST)]))


def test_historical_reports_not_overwritten(tmp_path, monkeypatch):
    monkeypatch.setattr(runner, "BASE", tmp_path)
    report = tmp_path / "reports/test.md"
    report.parent.mkdir()
    report.write_text("historical")
    with pytest.raises(schema.BenchmarkError):
        runner.validate_options(runner.parser().parse_args(["--report", str(report)]))
    assert report.read_text() == "historical"


def test_live_fact_changes_do_not_change_knowledge():
    before = schema.digest(schema.BASE / "fixtures/knowledge.json")
    dishes = schema.live_dishes("lemon_repriced")
    assert next(d for d in dishes if d["_id"] == "dish-4")["price"] == 30.5
    assert schema.digest(schema.BASE / "fixtures/knowledge.json") == before


def test_offline_production_js_contract_without_network(cases):
    case = positive(cases)
    obs = observation(case)
    payload = {
        "operation": "validate",
        "selection": {
            k: obs["generation"][k] for k in ("answerable", "dishIds", "usedKnowledgeIds")
        },
        "knowledge": obs["generation"]["evidence"],
        "dishes": [
            {"dishId": d["_id"], "status": d["status"]} for d in schema.live_dishes("default")
        ],
    }
    child = subprocess.run(
        ["node", str(schema.BASE / "bridge.cjs")],
        input=json.dumps(payload),
        text=True,
        capture_output=True,
        check=True,
    )
    result = json.loads(child.stdout)
    assert result["generation"] == obs["generation"]


def test_bridge_live_without_confirmation_no_network():
    child = subprocess.run(
        ["node", str(schema.BASE / "bridge.cjs")],
        input=json.dumps({"operation": "live-generation", "query": "unused"}),
        text=True,
        capture_output=True,
        check=True,
    )
    assert json.loads(child.stdout) == {
        "status": "error",
        "errorCode": "LIVE_CONFIRMATION_REQUIRED",
    }


def test_empty_metrics_na():
    s = summarize([])
    assert set(s["metrics"]) == set(METRICS)
    assert all(m["value"] is None for m in s["metrics"].values())


@pytest.mark.parametrize("mutation", ["unknown", "duplicate", "bad_rank", "nan", "no_score"])
def test_invalid_retrieval_contract_is_not_accurate(cases, mutation):
    case = positive(cases)
    obs = observation(case)
    if mutation == "unknown":
        obs["retrieval"][0]["knowledgeId"] = "unknown"
    elif mutation == "duplicate":
        obs["retrieval"] *= 2
    elif mutation == "bad_rank":
        obs["retrieval"][0]["rank"] = 2
    elif mutation == "nan":
        obs["retrieval"][0]["similarity"] = float("nan")
    else:
        obs["retrieval"][0]["similarity"] = None
    result = score(case, obs)
    assert result["metrics"]["correct_knowledge_id_retrieval"] == "FAIL"
    assert result["metrics"]["recall_at_3"] == "REVIEW"


def test_selected_evidence_order_controls_answer(cases):
    case = next(c for c in cases if len(c["expected"]["requiredEvidenceGroups"]) == 2)
    used = [g[0] for g in case["expected"]["requiredEvidenceGroups"]][::-1]
    obs = observation(case, used=used)
    result = score(case, obs)
    assert result["metrics"]["grounding_accuracy"] == "PASS"
    obs["generation"]["answer"] = "\n".join(
        e["text"] for e in reversed(obs["generation"]["evidence"])
    )
    assert score(case, obs)["metrics"]["grounding_accuracy"] == "FAIL"


def test_refusal_with_nonempty_evidence_rejected(cases):
    case = next(c for c in cases if not c["expected"]["answerable"])
    obs = observation(case, retrieved=["dish-4-taste"], answerable=False)
    source = schema.knowledge()["dish-4-taste"]
    obs["generation"]["evidence"] = [
        {k: source[k] for k in ("knowledgeId", "dishId", "scope", "type", "title", "text")}
    ]
    result = score(case, obs)
    assert result["metrics"]["grounding_accuracy"] == "FAIL"
    assert result["metrics"]["evidence_attribution_accuracy"] == "FAIL"


def test_missing_observations_do_not_shrink_offline_denominators(tmp_path, cases):
    data = tmp_path / "observations.json"
    case = positive(cases)
    data.write_text(json.dumps([dict(observation(case), id=case["id"])]))
    result = runner.run(
        runner.parser().parse_args(["--mode", "supplied-observations", "--observations", str(data)])
    )
    metric = result["summary"]["metrics"]["answerability_accuracy"]
    assert metric["applicable"] == 30
    assert metric["review"] == 29
    assert metric["conservativeAutomaticPassRate"] == 1 / 30
    assert result["summary"]["metrics"]["recall_at_3"]["applicable"] == 0


def test_manifest_pin_rejects_consistent_forgery(tmp_path, monkeypatch):
    path = tmp_path / "manifest-v1.json"
    path.write_text('{"version": 9}')
    monkeypatch.setattr(schema, "MANIFEST", path)
    with pytest.raises(schema.BenchmarkError, match="manifest hash"):
        schema.load_split("dev")


def test_unknown_error_message_not_saved_in_report(cases):
    case = positive(cases)
    result = score(case, {"status": "error", "errorCode": "private-error-secret-marker"})
    text = render({}, summarize([result]), [result])
    assert "private-error-secret-marker" not in text
    assert "GENERATION_NOT_OBSERVED" in text


def test_unscorable_claim_semantics_is_na_not_zero_hallucinations(cases):
    case = positive(cases)
    obs = observation(case)
    obs["generation"]["answer"] = "different wording"
    result = score(case, obs)
    metric = summarize([result])["metrics"]["unsupported_claim_rate"]
    assert metric["applicable"] == 1 and metric["review"] == 1
    assert metric["value"] is None
    assert metric["conservativeAutomaticPassRate"] == 0

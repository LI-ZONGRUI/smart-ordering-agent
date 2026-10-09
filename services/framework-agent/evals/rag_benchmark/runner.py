"""No network by default. Live execution reuses frozen production JS with a local corpus export."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import time
from pathlib import Path
from typing import Any

from evals.rag_benchmark.metrics import summarize
from evals.rag_benchmark.observability import (
    enrich_dev_result,
    process_failure,
    safe_checkpoint,
    validate_diagnostics,
)
from evals.rag_benchmark.report import render
from evals.rag_benchmark.schema import (
    BASE,
    MANIFEST,
    ROOT,
    BenchmarkError,
    digest,
    live_dishes,
    load_index,
    load_split,
)
from evals.rag_benchmark.validators import evaluate_case

MODES = ("validation-only", "supplied-observations", "live-retrieval", "live-generation")


def parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--split", choices=("dev", "holdout"), default="dev")
    p.add_argument("--confirm-holdout", action="store_true")
    p.add_argument("--mode", choices=MODES, default="validation-only")
    p.add_argument("--live-model", action="store_true")
    p.add_argument("--confirm-live", action="store_true")
    p.add_argument("--observations", type=Path)
    p.add_argument("--index-fixture", type=Path)
    p.add_argument("--index-manifest", type=Path)
    p.add_argument("--report", type=Path)
    return p


def validate_options(args: argparse.Namespace) -> None:
    # Check BEFORE loading any split or constructing an HTTP client.
    if args.split == "holdout" and not args.confirm_holdout:
        raise BenchmarkError("Holdout is frozen and requires explicit confirmation.")
    live = args.mode.startswith("live-")
    if live and not (args.live_model and args.confirm_live):
        raise BenchmarkError("Live mode requires --live-model and --confirm-live.")
    if not live and (args.live_model or args.confirm_live):
        raise BenchmarkError("Live flags require an explicit live mode.")
    if live and (args.index_fixture is None or args.index_manifest is None):
        raise BenchmarkError(
            "Live retrieval requires a complete audited index export and manifest."
        )
    if (args.mode == "supplied-observations") != (args.observations is not None):
        raise BenchmarkError("Observations are allowed only in supplied-observations mode.")
    if args.report is not None:
        target = args.report.resolve()
        if target.suffix != ".md" or not any(
            target.is_relative_to(BASE / d) for d in ("reports", ".local")
        ):
            raise BenchmarkError(
                "Report must be a new markdown file inside benchmark reports or .local."
            )
        if target.exists():
            raise BenchmarkError("Historical report must not be overwritten.")


def validate_observation(row: Any) -> dict[str, Any]:
    if not isinstance(row, dict) or set(row) - {
        "id",
        "status",
        "retrieval",
        "generation",
        "errorCode",
        "diagnostics",
    }:
        raise BenchmarkError("Observation schema invalid; vectors and raw responses are forbidden.")
    if row.get("status") not in {"ok", "error"}:
        raise BenchmarkError("Observation status invalid.")
    if "diagnostics" in row:
        validate_diagnostics(row["diagnostics"])
    # Ignore arbitrary upstream error strings: public report only records fixed failure categories.
    if "retrieval" in row:
        if not isinstance(row["retrieval"], list):
            raise BenchmarkError("Observation retrieval schema invalid.")
        for r in row["retrieval"]:
            if not isinstance(r, dict) or set(r) != {"rank", "knowledgeId", "similarity"}:
                raise BenchmarkError("Observation retrieval fields invalid.")
    if "generation" in row:
        g = row["generation"]
        if not isinstance(g, dict) or set(g) != {
            "answerable",
            "answer",
            "dishIds",
            "usedKnowledgeIds",
            "evidence",
        }:
            raise BenchmarkError("Observation generation fields invalid.")
        if (
            not isinstance(g["answer"], str)
            or len(g["answer"]) > 8000
            or not isinstance(g["evidence"], list)
        ):
            raise BenchmarkError("Observation generation size invalid.")
        for e in g["evidence"]:
            if not isinstance(e, dict) or set(e) != {
                "knowledgeId",
                "dishId",
                "scope",
                "type",
                "title",
                "text",
            }:
                raise BenchmarkError("Observation evidence fields invalid.")
    return row


def fingerprint() -> str:
    h = hashlib.sha256()
    for name in ("retriever.js", "query-retrieval.js", "generator.js"):
        h.update(name.encode())
        h.update((ROOT / "uniCloud-aliyun/cloudfunctions/rag" / name).read_bytes())
    return h.hexdigest()


def checkpoint_from_output(output: str | bytes | None) -> list[dict[str, Any]] | None:
    if isinstance(output, bytes):
        output = output.decode("utf-8", errors="replace")
    if not isinstance(output, str) or len(output) > 1_000_000:
        return None
    checkpoint = None
    for line in output.splitlines():
        try:
            value = json.loads(line)
        except ValueError:
            continue  # A killed process may leave a partial last line.
        if (
            isinstance(value, dict)
            and set(value) == {"kind", "retrieval"}
            and value["kind"] == "retrieval_checkpoint"
        ):
            safe = safe_checkpoint(value["retrieval"])
            if safe is not None:
                checkpoint = safe
    return checkpoint


def invoke_live(case: dict[str, Any], records: list[dict[str, Any]], mode: str) -> dict[str, Any]:
    # Deliberately omit expected labels and case history: no oracle feeds production execution.
    payload = {
        "operation": mode,
        "query": case["query"],
        "records": records,
        "dishes": live_dishes(case["liveProfile"]),
    }
    started = time.monotonic()
    checkpoint = None
    try:
        child = subprocess.run(
            ["node", str(BASE / "bridge.cjs"), "--confirm-live"],
            input=json.dumps(payload),
            text=True,
            capture_output=True,
            timeout=100,
            check=False,
        )
        checkpoint = checkpoint_from_output(child.stdout)
        if child.returncode != 0:
            return process_failure(
                "BRIDGE_PROCESS", "PROCESS_EXIT", time.monotonic() - started, checkpoint
            )
        # New bridge uses checkpoint + final JSON; legacy single JSON remains accepted.
        lines = child.stdout.strip().splitlines()
        observation = validate_observation(json.loads(lines[-1]))
        if checkpoint and "retrieval" not in observation:
            observation["retrieval"] = checkpoint
            if "diagnostics" in observation:
                observation["diagnostics"]["retrievalCompleted"] = True
        return observation
    except subprocess.TimeoutExpired as error:
        return process_failure(
            "TIMEOUT",
            "TIMEOUT",
            time.monotonic() - started,
            checkpoint_from_output(error.stdout),
        )
    except OSError:
        return process_failure("BRIDGE_PROCESS", "PROCESS_START_FAILED", time.monotonic() - started)
    except (ValueError, IndexError):
        return process_failure(
            "BRIDGE_PROCESS", "OUTPUT_INVALID", time.monotonic() - started, checkpoint
        )


def run(args: argparse.Namespace) -> dict[str, Any]:
    validate_options(args)
    cases = load_split(args.split)
    live = args.mode.startswith("live-")
    records = None
    if live:
        records = load_index(args.index_fixture, args.index_manifest)
        # Do not inherit a silently different provider model into this fixed benchmark.
        required = {"EMBEDDING_MODEL": "qwen3.7-text-embedding-flash", "EMBEDDING_DIMENSION": "512"}
        if args.mode == "live-generation":
            required["RAG_LLM_MODEL"] = "qwen3.8-flash"
        if any(os.environ.get(k) != v for k, v in required.items()) or not all(
            os.environ.get(k, "").strip() for k in ("DASHSCOPE_API_KEY", "LLM_BASE_URL")
        ):
            raise BenchmarkError("Live environment configuration missing or incompatible.")
    observations = {}
    if args.observations:
        rows = json.loads(args.observations.read_text())
        if not isinstance(rows, list):
            raise BenchmarkError("Observations must be an array.")
        allowed = {c["id"] for c in cases}
        for row in rows:
            validate_observation(row)
            if (
                not isinstance(row.get("id"), str)
                or row["id"] not in allowed
                or row["id"] in observations
            ):
                raise BenchmarkError("Observation identity invalid or duplicated.")
            observations[row["id"]] = row
    results = []
    for case in cases:
        if args.mode == "validation-only":
            continue
        observation = (
            invoke_live(case, records, args.mode) if live else observations.get(case["id"], {})
        )
        scored = evaluate_case(
            case,
            observation,
            retrieval_measured=live,
            generation_measured=args.mode in {"live-generation", "supplied-observations"},
        )
        results.append(enrich_dev_result(case, observation, scored))
    manifest = json.loads(MANIFEST.read_text())
    metadata = {
        "benchmarkVersion": 1,
        "validatorVersion": 1,
        "observabilityVersion": 2,
        "mode": args.mode,
        "split": args.split,
        "casesInScope": len(cases),
        "splitCounts": manifest["counts"],
        "datasetManifestHash": digest(MANIFEST),
        "knowledgeSourceHash": manifest["sourceSha256"],
        "productionRagFingerprint": fingerprint(),
        "embeddingModel": manifest["embeddingModel"],
        "embeddingDimension": 512,
        "topK": 3,
        "retrievalMeasurement": "real-query-embedding-against-audited-local-export"
        if live
        else "N/A",
        "generationMeasurement": "Qwen-with-frozen-local-live-facts"
        if args.mode == "live-generation"
        else "offline-contract-only"
        if args.mode == "supplied-observations"
        else "N/A",
        "indexSnapshotHash": digest(args.index_fixture) if live else None,
        "indexOriginAttestation": "user-audited-export-not-cryptographic-provider-proof"
        if live
        else None,
    }
    summary = summarize(results)
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        # Never overwrite historical results; output contains neither queries nor answer text.
        with args.report.open("x") as file:
            file.write(render(metadata, summary, results))
    return {"metadata": metadata, "summary": summary}


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    try:
        result = run(args)
    except (BenchmarkError, OSError, ValueError):
        # CLI errors remain fixed categories; never print exception contents from untrusted files.
        # Confirmation messages contain no untrusted input and are useful before loading data.
        try:
            validate_options(args)
        except BenchmarkError as error:
            print(str(error))
            return 2
        print("Benchmark validation or execution failed; check local fixture contracts.")
        return 2
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

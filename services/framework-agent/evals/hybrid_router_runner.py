"""Hybrid Router split evaluation with explicit live-model and Holdout opt-ins."""

from __future__ import annotations

import argparse
import asyncio
import json
from pathlib import Path
from typing import Any

from app.graph.router import (
    HybridRouter,
    SemanticRouteClassifier,
    build_production_semantic_router,
    classify_high_confidence,
)
from app.graph.state import FRAMEWORK_ROUTES, FrameworkRoute
from evals.metrics import aggregate_metrics
from evals.report import render_report
from evals.schema import (
    DATASET_DIR,
    SPLIT_COUNTS,
    BenchmarkSchemaError,
    load_jsonl,
    sha256_file,
    validate_dataset,
)
from evals.validators import evaluate_case

REPORT_DIR = Path(__file__).resolve().parent / "reports"
OFFLINE_REPORT = REPORT_DIR / "hybrid-router-dev-v1.md"
LIVE_REPORT = REPORT_DIR / "hybrid-router-dev-live-v1.md"
HOLDOUT_OFFLINE_REPORT = REPORT_DIR / "hybrid-router-holdout-v1.md"
HOLDOUT_LIVE_REPORT = REPORT_DIR / "hybrid-router-holdout-live-v1.md"
HOLDOUT_V2_DATASET = DATASET_DIR / "holdout-v2.jsonl"
HOLDOUT_V2_MANIFEST = DATASET_DIR / "holdout-v2-manifest.json"
HOLDOUT_V2_OFFLINE_REPORT = REPORT_DIR / "hybrid-router-holdout-v2-v1.md"
HOLDOUT_V2_LIVE_REPORT = REPORT_DIR / "hybrid-router-holdout-v2-live-v1.md"
HOLDOUT_V2_COUNT = 40


def _router_input(case: dict[str, Any]) -> str:
    return case["expected"]["expectedResolvedQuery"] or case["input"]["query"]


def _render(
    cases: list[dict[str, Any]],
    observations: list[dict[str, Any]],
    *,
    split: str,
    mode: str,
    note: str,
) -> str:
    results = [
        evaluate_case(
            case,
            {key: observation[key] for key in ("id", "route") if key in observation},
        )
        for case, observation in zip(cases, observations, strict=True)
    ]
    body = render_report(
        cases=cases,
        results=results,
        metrics=aggregate_metrics(results),
        mode=mode,
        snapshot_assumptions=(
            f"{split.capitalize()} labels only; Router receives the post-contextualization query"
        ),
    )
    # Only enumerated route metadata enters the diagnostic report. Queries, histories, provider
    # responses, prompts and exceptions are never serialized here.
    failure_rows = []
    for case, observation, result in zip(cases, observations, results, strict=True):
        if not result["failures"]:
            continue
        actual = observation.get("route")
        actual_route = actual if isinstance(actual, str) and actual in FRAMEWORK_ROUTES else "N/A"
        source = observation.get("routing_source")
        routing_source = (
            source
            if isinstance(source, str) and source in {"deterministic", "semantic", "fallback"}
            else "N/A"
        )
        failure_rows.append(
            "| "
            + " | ".join(
                (
                    case["id"],
                    case["category"],
                    ", ".join(case["expected"]["allowedRoutes"]),
                    actual_route,
                    routing_source,
                    ", ".join(result["failures"]),
                )
            )
            + " |"
        )
    details = "\n".join(
        (
            "## Route failure details",
            "",
            "| Case ID | Category | Allowed routes | Actual route | Routing source | Failures |",
            "| --- | --- | --- | --- | --- | --- |",
            *(failure_rows or ["| none | — | — | — | — | — |"]),
            "",
        )
    )
    return "\n".join(
        (body, "## Hybrid Router coverage", "", f"- Split: `{split}`", note, "", details)
    )


class _ObservedSemanticClassifier:
    """Track only whether Qwen classification ran or safely fell back."""

    def __init__(self, delegate: SemanticRouteClassifier) -> None:
        self.delegate = delegate
        self.calls = 0
        self.last_failed = False

    async def classify(self, query: str) -> FrameworkRoute:
        self.calls += 1
        self.last_failed = False
        try:
            return await self.delegate.classify(query)
        except Exception:
            self.last_failed = True
            raise


def _coverage_case_ids(cases: list[dict[str, Any]]) -> tuple[list[str], list[str]]:
    deterministic: list[str] = []
    semantic: list[str] = []
    for case in cases:
        target = (
            deterministic if classify_high_confidence(_router_input(case)) is not None else semantic
        )
        target.append(case["id"])
    return deterministic, semantic


def run_offline(cases: list[dict[str, Any]], *, split: str = "dev") -> str:
    observations: list[dict[str, Any]] = []
    resolved = 0
    correct = 0
    resolved_ids: list[str] = []
    unresolved: list[str] = []
    for case in cases:
        route = classify_high_confidence(_router_input(case))
        observation: dict[str, Any] = {"id": case["id"]}
        if route is None:
            unresolved.append(case["id"])
        else:
            resolved += 1
            resolved_ids.append(case["id"])
            correct += route in case["expected"]["allowedRoutes"]
            observation["route"] = route
            observation["routing_source"] = "deterministic"
        observations.append(observation)
    note = "\n".join(
        (
            f"- Deterministic high-confidence coverage: {resolved}/{len(cases)}",
            f"- Deterministic rule case IDs: {', '.join(resolved_ids) or 'none'}",
            f"- Correct among deterministically resolved cases: {correct}/{resolved}",
            f"- Semantic-model cases left N/A: {', '.join(unresolved) if unresolved else 'none'}",
            "- No Qwen, Gateway, uniCloud, RAG, Tool, or database request was made.",
            (
                f"- This is not the final Hybrid Router {split.capitalize()} accuracy "
                "when unresolved cases remain."
            ),
        )
    )
    return _render(
        cases,
        observations,
        split=split,
        mode=_mode_name(split=split, live_model=False),
        note=note,
    )


async def run_live(cases: list[dict[str, Any]], *, split: str = "dev") -> str:
    classifier = _ObservedSemanticClassifier(build_production_semantic_router())
    router = HybridRouter(classifier)
    observations = []
    for case in cases:
        calls_before = classifier.calls
        route = await router.route(_router_input(case))
        source = (
            "deterministic"
            if classifier.calls == calls_before
            else "fallback"
            if classifier.last_failed
            else "semantic"
        )
        observations.append({"id": case["id"], "route": route, "routing_source": source})
    deterministic_ids, semantic_ids = _coverage_case_ids(cases)
    note = "\n".join(
        (
            f"- Hybrid routes observed: {len(observations)}/{len(cases)}",
            f"- Deterministic rule coverage: {len(deterministic_ids)}/{len(cases)}",
            f"- Deterministic rule case IDs: {', '.join(deterministic_ids) or 'none'}",
            f"- Semantic Router coverage: {len(semantic_ids)}/{len(cases)}",
            f"- Semantic Router case IDs: {', '.join(semantic_ids) or 'none'}",
            "- Qwen was eligible only when deterministic rules returned unresolved.",
            "- This command does not call Gateway, uniCloud, Tools, RAG, or a database.",
        )
    )
    return _render(
        cases,
        observations,
        split=split,
        mode=_mode_name(split=split, live_model=True),
        note=note,
    )


def _mode_name(*, split: str, live_model: bool) -> str:
    if split == "dev":
        return "hybrid-router-live-model" if live_model else "hybrid-router-deterministic-only"
    suffix = "live-model" if live_model else "deterministic-only"
    return f"hybrid-router-{split}-{suffix}"


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Evaluate Hybrid Router on a frozen benchmark split"
    )
    parser.add_argument("--split", choices=("dev", "holdout", "holdout-v2"), default="dev")
    parser.add_argument("--confirm-holdout", action="store_true")
    parser.add_argument("--confirm-holdout-v2", action="store_true")
    parser.add_argument("--live-model", action="store_true")
    parser.add_argument("--confirm-live", action="store_true")
    parser.add_argument("--report", type=Path)
    return parser.parse_args(argv)


def validate_options(args: argparse.Namespace) -> None:
    if args.split == "holdout" and not args.confirm_holdout:
        raise SystemExit("Holdout is frozen and requires explicit confirmation.")
    if args.split == "holdout-v2" and not args.confirm_holdout_v2:
        raise SystemExit("Holdout v2 is frozen and requires explicit confirmation.")
    if args.live_model and not args.confirm_live:
        raise SystemExit("--live-model requires --confirm-live")


def verify_holdout_v2_freeze(
    *, dataset_path: Path = HOLDOUT_V2_DATASET, manifest_path: Path = HOLDOUT_V2_MANIFEST
) -> dict[str, Any]:
    if not dataset_path.is_file():
        raise BenchmarkSchemaError("Holdout v2 dataset is missing")
    if not manifest_path.is_file():
        raise BenchmarkSchemaError("Holdout v2 manifest is missing")
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as error:
        raise BenchmarkSchemaError("Holdout v2 manifest is invalid") from error
    if not isinstance(manifest, dict):
        raise BenchmarkSchemaError("Holdout v2 manifest is invalid")
    hashes = manifest.get("sha256")
    expected_hash = hashes.get(dataset_path.name) if isinstance(hashes, dict) else None
    if (
        manifest.get("benchmarkName") != "hybrid-router-holdout-v2"
        or manifest.get("holdoutVersion") != 2
        or manifest.get("totalCases") != HOLDOUT_V2_COUNT
        or not isinstance(expected_hash, str)
    ):
        raise BenchmarkSchemaError("Holdout v2 manifest does not match the frozen contract")
    if sha256_file(dataset_path) != expected_hash:
        raise BenchmarkSchemaError("Holdout v2 freeze hash mismatch")
    return manifest


def load_split(split: str) -> list[dict[str, Any]]:
    if split == "holdout-v2":
        verify_holdout_v2_freeze()
        cases = load_jsonl(HOLDOUT_V2_DATASET)
        expected_count = HOLDOUT_V2_COUNT
        expected_case_split = "holdout"
        contract = "frozen Holdout v2 contract"
    else:
        cases = load_jsonl(DATASET_DIR / f"{split}.jsonl")
        expected_count = SPLIT_COUNTS[split]
        expected_case_split = split
        contract = "frozen v1 contract"
    validate_dataset(cases, enforce_totals=False)
    if len(cases) != expected_count or any(case["split"] != expected_case_split for case in cases):
        raise BenchmarkSchemaError(f"{split} split does not match the {contract}")
    return cases


def default_report_path(*, split: str, live_model: bool) -> Path:
    return {
        ("dev", False): OFFLINE_REPORT,
        ("dev", True): LIVE_REPORT,
        ("holdout", False): HOLDOUT_OFFLINE_REPORT,
        ("holdout", True): HOLDOUT_LIVE_REPORT,
        ("holdout-v2", False): HOLDOUT_V2_OFFLINE_REPORT,
        ("holdout-v2", True): HOLDOUT_V2_LIVE_REPORT,
    }[(split, live_model)]


def main() -> None:
    args = parse_args()
    validate_options(args)

    cases = load_split(args.split)
    report = (
        asyncio.run(run_live(cases, split=args.split))
        if args.live_model
        else run_offline(cases, split=args.split)
    )
    report_path = args.report or default_report_path(split=args.split, live_model=args.live_model)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(report, encoding="utf-8")
    print(
        json.dumps(
            {"report": str(report_path), "live": args.live_model, "split": args.split},
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()

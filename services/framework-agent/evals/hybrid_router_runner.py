"""Dev-only Hybrid Router evaluation; remote Qwen requires explicit double opt-in."""

from __future__ import annotations

import argparse
import asyncio
import json
from pathlib import Path
from typing import Any

from app.graph.router import (
    HybridRouter,
    build_production_semantic_router,
    classify_high_confidence,
)
from evals.metrics import aggregate_metrics
from evals.report import render_report
from evals.schema import DATASET_DIR, load_jsonl
from evals.validators import evaluate_case

REPORT_DIR = Path(__file__).resolve().parent / "reports"
OFFLINE_REPORT = REPORT_DIR / "hybrid-router-dev-v1.md"
LIVE_REPORT = REPORT_DIR / "hybrid-router-dev-live-v1.md"


def _router_input(case: dict[str, Any]) -> str:
    return case["expected"]["expectedResolvedQuery"] or case["input"]["query"]


def _render(
    cases: list[dict[str, Any]],
    observations: list[dict[str, Any]],
    *,
    mode: str,
    note: str,
) -> str:
    results = [
        evaluate_case(case, observation)
        for case, observation in zip(cases, observations, strict=True)
    ]
    body = render_report(
        cases=cases,
        results=results,
        metrics=aggregate_metrics(results),
        mode=mode,
        snapshot_assumptions="Dev labels only; Router receives the post-contextualization query",
    )
    return "\n".join((body, "## Hybrid Router coverage", "", note, ""))


def run_offline(cases: list[dict[str, Any]]) -> str:
    observations: list[dict[str, Any]] = []
    resolved = 0
    correct = 0
    unresolved: list[str] = []
    for case in cases:
        route = classify_high_confidence(_router_input(case))
        observation: dict[str, Any] = {"id": case["id"]}
        if route is None:
            unresolved.append(case["id"])
        else:
            resolved += 1
            correct += route in case["expected"]["allowedRoutes"]
            observation["route"] = route
        observations.append(observation)
    note = "\n".join(
        (
            f"- Deterministic high-confidence coverage: {resolved}/{len(cases)}",
            f"- Correct among deterministically resolved cases: {correct}/{resolved}",
            f"- Semantic-model cases left N/A: {', '.join(unresolved) if unresolved else 'none'}",
            "- No Qwen, Gateway, uniCloud, RAG, Tool, or database request was made.",
            "- This is not the final Hybrid Router Dev accuracy when unresolved cases remain.",
        )
    )
    return _render(
        cases,
        observations,
        mode="hybrid-router-deterministic-only",
        note=note,
    )


async def run_live(cases: list[dict[str, Any]]) -> str:
    router = HybridRouter(build_production_semantic_router())
    observations = [
        {"id": case["id"], "route": await router.route(_router_input(case))} for case in cases
    ]
    note = "\n".join(
        (
            f"- Hybrid routes observed: {len(observations)}/{len(cases)}",
            "- Qwen was eligible only when deterministic rules returned unresolved.",
            "- This command does not call Gateway, uniCloud, Tools, RAG, or a database.",
        )
    )
    return _render(cases, observations, mode="hybrid-router-live-model", note=note)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Evaluate Hybrid Router on the 80-case Dev split")
    parser.add_argument("--live-model", action="store_true")
    parser.add_argument("--confirm-live", action="store_true")
    parser.add_argument("--report", type=Path)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.live_model and not args.confirm_live:
        raise SystemExit("--live-model requires --confirm-live")

    # Intentionally load only Dev. This module has no Holdout option or Holdout file access.
    cases = load_jsonl(DATASET_DIR / "dev.jsonl")
    report = asyncio.run(run_live(cases)) if args.live_model else run_offline(cases)
    report_path = args.report or (LIVE_REPORT if args.live_model else OFFLINE_REPORT)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(report, encoding="utf-8")
    print(json.dumps({"report": str(report_path), "live": args.live_model}, ensure_ascii=False))


if __name__ == "__main__":
    main()

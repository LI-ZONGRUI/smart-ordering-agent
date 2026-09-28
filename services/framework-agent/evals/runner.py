"""Offline-first CLI for agent-benchmark-v1.

Imports and the default command never access the network. Live Golden E2E requires both explicit
flags plus a separately running, configured Framework Agent service.
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import Any

import httpx

from app.graph.router import classify_request
from evals.metrics import aggregate_metrics
from evals.report import render_report
from evals.schema import DATASET_DIR, load_benchmark, load_jsonl, verify_frozen_artifacts
from evals.validators import evaluate_case

# The committed v1 baseline is historical evidence. Current runs must never overwrite it.
DEFAULT_REPORT = Path(__file__).resolve().parent / "reports" / "deterministic-dev-current.md"


def _offline_observation(case: dict[str, Any]) -> dict[str, Any]:
    expected_resolved = case["expected"]["expectedResolvedQuery"]
    # Multi-turn Contextualizer behavior is model-dependent. Level 1 checks only the deterministic
    # Router contract after the expected standalone query, never pretends to evaluate resolution.
    router_input = expected_resolved or case["input"]["query"]
    return {"id": case["id"], "route": classify_request(router_input)}


def run_deterministic(cases: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], str]:
    results = [evaluate_case(case, _offline_observation(case)) for case in cases]
    report = render_report(
        cases=cases,
        results=results,
        metrics=aggregate_metrics(results),
        mode="deterministic-offline",
        executed_at="2026-09-28T00:00:00+00:00",
        snapshot_assumptions="frozen v1 menu/knowledge fixtures; Router-only observation",
    )
    return results, report


def evaluate_observations(
    cases: list[dict[str, Any]], observations: list[dict[str, Any]], *, mode: str
) -> tuple[list[dict[str, Any]], str]:
    by_id = {item.get("id"): item for item in observations}
    results = [evaluate_case(case, by_id[case["id"]]) for case in cases if case["id"] in by_id]
    report = render_report(
        cases=[case for case in cases if case["id"] in by_id],
        results=results,
        metrics=aggregate_metrics(results),
        mode=mode,
        snapshot_assumptions="observations supplied by caller; compare live facts to run timestamp",
    )
    return results, report


def _safe_public_response(data: Any, case_id: str) -> dict[str, Any]:
    if not isinstance(data, dict) or data.get("errCode") != 0:
        return {"id": case_id, "answer": "", "safeRejection": True, "pendingAction": None}
    allowed = {"answer", "pendingAction"}
    return {"id": case_id, **{key: data[key] for key in allowed if key in data}}


def run_live_golden(cases: list[dict[str, Any]], base_url: str) -> list[dict[str, Any]]:
    """Call only the formal local API; never persist or print conversation capability tokens."""

    observations: list[dict[str, Any]] = []
    sessions: dict[str, tuple[str, str]] = {}
    with httpx.Client(base_url=base_url.rstrip("/"), timeout=45.0) as client:
        for case in cases:
            payload: dict[str, Any] = {"query": case["input"]["query"]}
            headers: dict[str, str] = {}
            # v1 stores group/turn in expected metadata through expectedResolvedQuery/history;
            # one session per nonempty multi-turn history prefix keeps capability data in memory.
            if case["category"] == "multi_turn":
                group = case["id"].rsplit("_", 1)[0]
                if group not in sessions:
                    created = client.post("/v1/conversations", json={}).json()
                    if created.get("errCode") != 0:
                        observations.append({"id": case["id"], "answer": "", "safeRejection": True})
                        continue
                    sessions[group] = (created["threadId"], created["conversationToken"])
                thread_id, token = sessions[group]
                payload["threadId"] = thread_id
                headers["X-Conversation-Token"] = token
            response = client.post("/v1/agent/run", json=payload, headers=headers)
            observations.append(_safe_public_response(response.json(), case["id"]))
    return observations


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run agent-benchmark-v1")
    parser.add_argument("--observations", type=Path)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    parser.add_argument("--split", choices=("dev", "holdout", "all"), default="dev")
    parser.add_argument("--confirm-holdout", action="store_true")
    parser.add_argument("--live-model", action="store_true")
    parser.add_argument("--confirm-live", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    verify_frozen_artifacts()
    cases = load_benchmark()
    if args.live_model:
        if not args.confirm_live:
            raise SystemExit("--live-model requires --confirm-live")
        base_url = os.getenv("FRAMEWORK_AGENT_EVAL_BASE_URL", "").strip()
        if not base_url:
            raise SystemExit("FRAMEWORK_AGENT_EVAL_BASE_URL is required for explicit live mode")
        golden = load_jsonl(DATASET_DIR / "golden-e2e.jsonl")
        observations = run_live_golden(golden, base_url)
        _, report = evaluate_observations(golden, observations, mode="golden-e2e-live")
    else:
        if args.split in {"holdout", "all"} and not args.confirm_holdout:
            raise SystemExit("holdout evaluation requires --confirm-holdout")
        selected = cases if args.split == "all" else [c for c in cases if c["split"] == args.split]
        if args.observations:
            observations = load_jsonl(args.observations)
            _, report = evaluate_observations(selected, observations, mode="supplied-observations")
        else:
            _, report = run_deterministic(selected)
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(report, encoding="utf-8")
    print(json.dumps({"report": str(args.report), "live": args.live_model}, ensure_ascii=False))


if __name__ == "__main__":
    main()

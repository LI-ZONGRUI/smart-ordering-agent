"""Offline-first runner for Contextualizer Benchmark v1.

Importing this module and the default command do not construct a model or access the network.
"""

from __future__ import annotations

import argparse
import asyncio
import json
from pathlib import Path
from typing import Any, Protocol

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage

from evals.contextualizer.metrics import aggregate_metrics
from evals.contextualizer.report import render_report
from evals.contextualizer.schema import (
    DEV_DATASET,
    HOLDOUT_DATASET,
    ContextualizerBenchmarkError,
    load_jsonl,
    validate_dataset,
    verify_frozen_artifacts,
)
from evals.contextualizer.validators import evaluate_case

DEFAULT_REPORT = Path(__file__).resolve().parent / "reports" / "dev-validation-v1.md"


class Resolver(Protocol):
    async def resolve(self, query: str, history: tuple[BaseMessage, ...]) -> str: ...


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run Contextualizer Benchmark v1")
    parser.add_argument("--split", choices=("dev", "holdout"), default="dev")
    parser.add_argument("--observations", type=Path)
    parser.add_argument("--live-model", action="store_true")
    parser.add_argument("--confirm-live", action="store_true")
    parser.add_argument("--confirm-holdout", action="store_true")
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    return parser.parse_args(argv)


def validate_options(args: argparse.Namespace) -> None:
    if args.live_model and not args.confirm_live:
        raise SystemExit("--live-model requires --confirm-live")
    if args.split == "holdout" and not args.confirm_holdout:
        raise SystemExit("Holdout is frozen and requires --confirm-holdout")
    if args.live_model and args.observations is not None:
        raise SystemExit("--live-model and --observations are mutually exclusive")


def load_split(split: str) -> list[dict[str, Any]]:
    verify_frozen_artifacts()
    path = DEV_DATASET if split == "dev" else HOLDOUT_DATASET
    cases = load_jsonl(path)
    validate_dataset(cases, enforce_totals=False)
    expected_count = 30 if split == "dev" else 10
    if len(cases) != expected_count or any(case["split"] != split for case in cases):
        raise ContextualizerBenchmarkError(f"{split} split does not match frozen v1")
    return cases


def _history_messages(case: dict[str, Any]) -> tuple[BaseMessage, ...]:
    messages: list[BaseMessage] = []
    for item in case["history"]:
        message_type = HumanMessage if item["role"] == "user" else AIMessage
        messages.append(message_type(content=item["content"]))
    return tuple(messages)


async def run_live(cases: list[dict[str, Any]], resolver: Resolver) -> list[dict[str, Any]]:
    """Exercise the production gate and resolver; expected labels stay local."""

    from app.contextualizer import needs_contextualization
    from app.errors import FrameworkError

    observations: list[dict[str, Any]] = []
    for case in cases:
        history = _history_messages(case)
        if not needs_contextualization(case["query"], has_history=bool(history)):
            observations.append({"id": case["id"], "standaloneQuery": case["query"]})
            continue
        try:
            standalone = await resolver.resolve(case["query"], history)
        except FrameworkError:
            observations.append({"id": case["id"], "modelOutputInvalid": True})
        else:
            observations.append({"id": case["id"], "standaloneQuery": standalone})
    return observations


def evaluate_observations(
    cases: list[dict[str, Any]], observations: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    by_id: dict[str, dict[str, Any]] = {}
    for observation in observations:
        observation_id = observation.get("id")
        if not isinstance(observation_id, str) or observation_id in by_id:
            raise ContextualizerBenchmarkError("observation IDs must be unique strings")
        by_id[observation_id] = observation
    unknown = set(by_id) - {case["id"] for case in cases}
    if unknown:
        raise ContextualizerBenchmarkError("observations contain IDs outside the selected split")
    return [evaluate_case(case, by_id[case["id"]]) for case in cases if case["id"] in by_id]


def _build_live_resolver() -> Resolver:
    # Lazy import is part of the live boundary: default execution cannot even construct Qwen.
    from app.contextualizer import build_production_contextualizer

    return build_production_contextualizer()


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    validate_options(args)
    cases = load_split(args.split)
    if args.live_model:
        observations = asyncio.run(run_live(cases, _build_live_resolver()))
        mode = "live-model"
    elif args.observations is not None:
        observations = load_jsonl(args.observations)
        mode = "supplied-observations"
    else:
        observations = []
        mode = "validation-only"

    results = evaluate_observations(cases, observations)
    report = render_report(
        cases=cases,
        results=results,
        metrics=aggregate_metrics(results),
        mode=mode,
        split=args.split,
    )
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(report, encoding="utf-8")
    print(
        json.dumps(
            {
                "report": str(args.report),
                "split": args.split,
                "live": args.live_model,
                "evaluated": len(results),
            },
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()

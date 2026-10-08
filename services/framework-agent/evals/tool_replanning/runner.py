"""Offline-first runner for Tool Selection + Sequential Replanning Benchmark v1."""

from __future__ import annotations

import argparse
import asyncio
import json
from pathlib import Path
from typing import Any

from evals.tool_replanning.metrics import aggregate_metrics
from evals.tool_replanning.report import render_report
from evals.tool_replanning.schema import (
    DEV_DATASET,
    HOLDOUT_DATASET,
    ToolBenchmarkError,
    load_jsonl,
    validate_dataset,
    verify_frozen_artifacts,
)
from evals.tool_replanning.validators import evaluate_case

DEFAULT_REPORT = Path(__file__).resolve().parent / "reports" / "dev-validation-v1.md"


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run Tool Selection + Sequential Replanning Benchmark v1"
    )
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
        raise ToolBenchmarkError(f"{split} split does not match frozen v1")
    return cases


def normalize_agent_trace(
    trace: tuple[dict[str, Any], ...], answer: str, *, completed: bool
) -> list[dict[str, Any]]:
    """Map the existing safe Agent trace to the benchmark's planning-step contract.

    Consecutive calls before any Tool result belong to one AIMessage/model decision. A call that
    appears after result events starts a later decision. This preserves observable parallelism.
    """

    events: list[dict[str, Any]] = []
    step = 1
    saw_result = False
    for item in trace:
        if item.get("type") == "tool_call":
            if saw_result:
                step += 1
                saw_result = False
            events.append(
                {
                    "step": step,
                    "eventType": "assistant_tool_call",
                    "toolName": item.get("toolName", ""),
                    "arguments": item.get("arguments", {}),
                }
            )
        elif item.get("type") == "tool_result":
            summary = item.get("summary", {})
            events.append(
                {
                    "step": step,
                    "eventType": "tool_result",
                    "toolName": item.get("toolName", ""),
                    "resultClass": _result_class(summary),
                    "summary": summary,
                }
            )
            saw_result = True
    final_step = step + 1 if events else 1
    events.append(
        {
            "step": final_step,
            "eventType": "assistant_final",
            "answer": answer,
            "completed": completed,
        }
    )
    return events


def _result_class(summary: object) -> str:
    if not isinstance(summary, dict) or not summary:
        return "invalid"
    if type(summary.get("count")) is int:
        return "empty" if summary["count"] == 0 else "success"
    if type(summary.get("found")) is bool:
        return "success" if summary["found"] else "missing"
    return "invalid"


async def run_model_cases(cases: list[dict[str, Any]], model: Any) -> list[dict[str, Any]]:
    """Use the production LangChain loop with the local fixture Gateway only.

    This function is reached only behind explicit live confirmation. It calls Qwen, but never a
    remote Gateway, uniCloud, or database.
    """

    from app.agent import FrameworkAgent
    from app.errors import FrameworkError, tool_execution_failed
    from app.gateways.memory import InMemoryMenuGateway
    from evals.tool_replanning.observer import ToolTraceObserver

    class ScenarioGateway(InMemoryMenuGateway):
        # Evaluation-only fault injection; it never chooses or schedules another Tool.
        def __init__(self, scenario: str | None) -> None:
            self.scenario = scenario

        def inject_failure(self) -> bool:
            if self.scenario == "safe_error":
                raise tool_execution_failed()
            return self.scenario == "invalid"

        async def search_menu(self, query: str) -> dict[str, Any]:
            return {} if self.inject_failure() else await super().search_menu(query)

        async def list_available_drinks(self) -> dict[str, Any]:
            return {} if self.inject_failure() else await super().list_available_drinks()

        async def get_dish_detail(self, dish_id: str) -> dict[str, Any]:
            return {} if self.inject_failure() else await super().get_dish_detail(dish_id)

    observations: list[dict[str, Any]] = []
    for case in cases:
        context = case.get("context") or {}
        agent = FrameworkAgent(model, ScenarioGateway(context.get("simulatedResultClass")))
        observer = ToolTraceObserver()
        # Attach observation to the already-built production graph; no replacement loop or Prompt.
        # FrameworkAgent.run() still owns execution limits, validation and error mapping.
        agent._graph = agent._graph.with_config({"callbacks": [observer]})
        observation: dict[str, Any] = {"id": case["id"], "trace": observer.events}
        try:
            await agent.run(case["query"])
        except FrameworkError as error:
            safe_tool_error = (
                error.code == "FRAMEWORK_TOOL_EXECUTION_FAILED"
                and bool(observer.events)
                and observer.events[-1].get("resultClass") == "safe_error"
            )
            observation["termination"] = "safe_tool_error" if safe_tool_error else "model_error"
            observation["modelOutputInvalid"] = not safe_tool_error
        if observer.invalid:
            observation["modelOutputInvalid"] = True
        observations.append(observation)
    return observations


async def run_live(cases: list[dict[str, Any]]) -> list[dict[str, Any]]:
    from app.llm import build_qwen_model

    return await run_model_cases(cases, build_qwen_model())


def evaluate_observations(
    cases: list[dict[str, Any]], observations: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    by_id: dict[str, dict[str, Any]] = {}
    for observation in observations:
        observation_id = observation.get("id")
        if not isinstance(observation_id, str) or observation_id in by_id:
            raise ToolBenchmarkError("observation IDs must be unique strings")
        by_id[observation_id] = observation
    unknown = set(by_id) - {case["id"] for case in cases}
    if unknown:
        raise ToolBenchmarkError("observations contain IDs outside the selected split")
    return [evaluate_case(case, by_id[case["id"]]) for case in cases if case["id"] in by_id]


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    validate_options(args)
    # A custom report path must never overwrite a frozen fixture, source or existing baseline.
    report_path = args.report.resolve()
    if report_path.suffix != ".md" or report_path.exists():
        raise SystemExit("Choose a new .md report path; existing artifacts are never overwritten")
    cases = load_split(args.split)
    if args.live_model:
        observations = asyncio.run(run_live(cases))
        mode = "live-model-local-fixture"
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

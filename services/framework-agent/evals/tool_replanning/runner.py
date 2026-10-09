"""Offline-first runner for Tool Selection + Sequential Replanning Benchmark v1."""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
from pathlib import Path
from typing import Any

from evals.tool_replanning.metrics import aggregate_metrics
from evals.tool_replanning.report import render_report
from evals.tool_replanning.schema import (
    DEV_DATASET,
    HOLDOUT_DATASET,
    MANIFEST,
    ToolBenchmarkError,
    load_jsonl,
    validate_dataset,
    verify_frozen_artifacts,
)
from evals.tool_replanning.validators import evaluate_case

DEFAULT_REPORT = Path(__file__).resolve().parent / "reports" / "dev-validation-validator-v2.md"


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run Tool Selection + Sequential Replanning Benchmark v1"
    )
    parser.add_argument("--split", choices=("dev", "holdout"), default="dev")
    parser.add_argument("--observations", type=Path)
    parser.add_argument("--live-model", action="store_true")
    parser.add_argument("--confirm-live", action="store_true")
    parser.add_argument("--confirm-holdout", action="store_true")
    parser.add_argument("--diagnose-dev", action="store_true")
    parser.add_argument("--case-ids", nargs="+", metavar="DEV_CASE_ID")
    parser.add_argument("--validator-version", type=int, choices=(1, 2, 3), default=2)
    parser.add_argument("--shadow-validator-version", type=int, choices=(2,))
    parser.add_argument("--report", type=Path)
    args = parser.parse_args(argv)
    if args.report is None:
        args.report = DEFAULT_REPORT.with_name(
            f"{args.split}-validation-validator-v{args.validator_version}.md"
        )
    return args


def validate_options(args: argparse.Namespace) -> None:
    if args.shadow_validator_version is not None:
        if args.split != "dev" or args.validator_version != 3:
            raise SystemExit("Shadow scoring requires Dev primary Validator v3 and shadow v2")
        if not args.live_model and args.observations is None:
            raise SystemExit("Shadow scoring requires observed outputs")
    if args.live_model and not args.confirm_live:
        raise SystemExit("--live-model requires --confirm-live")
    if args.split == "holdout" and not args.confirm_holdout:
        raise SystemExit("Holdout is frozen and requires --confirm-holdout")
    if args.live_model and args.observations is not None:
        raise SystemExit("--live-model and --observations are mutually exclusive")
    if args.diagnose_dev and args.split != "dev":
        raise SystemExit("Dev diagnostics are forbidden on Holdout")
    if args.case_ids and not args.diagnose_dev:
        raise SystemExit("--case-ids requires --diagnose-dev")
    if args.diagnose_dev and (not args.live_model or args.observations is not None):
        raise SystemExit("--diagnose-dev requires --live-model and --confirm-live")


def load_split(split: str) -> list[dict[str, Any]]:
    if split == "dev":
        return load_dev_diagnostic_cases(None)
    verify_frozen_artifacts()
    path = DEV_DATASET if split == "dev" else HOLDOUT_DATASET
    cases = load_jsonl(path)
    validate_dataset(cases, enforce_totals=False)
    expected_count = 30 if split == "dev" else 10
    if len(cases) != expected_count or any(case["split"] != split for case in cases):
        raise ToolBenchmarkError(f"{split} split does not match frozen v1")
    return cases


def load_dev_diagnostic_cases(case_ids: list[str] | None) -> list[dict[str, Any]]:
    """Load only the Dev fixture. The normal frozen check also opens Holdout, so skip it here."""

    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    if hashlib.sha256(DEV_DATASET.read_bytes()).hexdigest() != manifest["sha256"]["dev.jsonl"]:
        raise ToolBenchmarkError("frozen Dev artifact changed")
    cases = load_jsonl(DEV_DATASET)
    validate_dataset(cases, enforce_totals=False)
    if len(cases) != 30 or any(case["split"] != "dev" for case in cases):
        raise ToolBenchmarkError("Dev split does not match frozen v1")
    if case_ids is None:
        return cases
    if len(set(case_ids)) != len(case_ids) or set(case_ids) - {case["id"] for case in cases}:
        raise ToolBenchmarkError("--case-ids must list unique Dev case IDs")
    selected = set(case_ids)
    return [case for case in cases if case["id"] in selected]


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
    cases: list[dict[str, Any]], observations: list[dict[str, Any]], *, validator_version: int = 2
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
    scorer = evaluate_case
    if validator_version == 1:
        from evals.tool_replanning.validators_v1 import evaluate_case as legacy_scorer

        scorer = legacy_scorer
    elif validator_version == 3:
        from evals.tool_replanning.validators_v3 import evaluate_case as v3_scorer

        scorer = v3_scorer
    elif validator_version != 2:
        raise ToolBenchmarkError("unsupported Validator version")
    return [scorer(case, by_id[case["id"]]) for case in cases if case["id"] in by_id]


def production_agent_source_hash() -> str:
    """Fingerprint code only; never inspect settings, credentials or environment files."""

    root = Path(__file__).resolve().parents[2]
    digest = hashlib.sha256()
    for name in ("app/agent.py", "app/tools/menu.py", "app/trace.py"):
        digest.update(name.encode())
        digest.update((root / name).read_bytes())
    return digest.hexdigest()


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    validate_options(args)
    # A custom report path must never overwrite a frozen fixture, source or existing baseline.
    report_path = args.report.resolve()
    if report_path.suffix != ".md" or report_path.exists():
        raise SystemExit("Choose a new .md report path; existing artifacts are never overwritten")
    cases = (
        load_dev_diagnostic_cases(args.case_ids) if args.diagnose_dev else load_split(args.split)
    )
    if args.live_model:
        observations = asyncio.run(run_live(cases))
        mode = "live-model-local-fixture"
    elif args.observations is not None:
        observations = load_jsonl(args.observations)
        mode = "supplied-observations"
    else:
        observations = []
        mode = "validation-only"
    results = evaluate_observations(cases, observations, validator_version=args.validator_version)
    # The exact same observations list is scored twice; no second run_live/model call.
    shadow_results = (
        evaluate_observations(cases, observations, validator_version=args.shadow_validator_version)
        if args.shadow_validator_version is not None
        else None
    )
    diagnostic_path = None
    if args.diagnose_dev:
        from evals.tool_replanning.diagnostics import (
            build_dev_diagnostic,
            write_private_diagnostic,
        )

        diagnostic_path = write_private_diagnostic(
            build_dev_diagnostic(cases, observations, results)
        )
    report = render_report(
        cases=cases,
        results=results,
        metrics=aggregate_metrics(results),
        mode=mode,
        split=args.split,
        validator_version=args.validator_version,
        agent_source_hash=production_agent_source_hash(),
        dataset_manifest_hash=hashlib.sha256(MANIFEST.read_bytes()).hexdigest(),
        shadow_results=shadow_results,
        shadow_validator_version=args.shadow_validator_version,
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
                **({"privateDiagnostic": str(diagnostic_path)} if diagnostic_path else {}),
            },
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()

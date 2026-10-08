"""Deterministic trace and answer validators for Tool Benchmark v1."""

from __future__ import annotations

import re
import unicodedata
from collections import Counter
from typing import Any

from evals.tool_replanning.schema import READ_ONLY_TOOLS, ToolBenchmarkError, validate_observation

FAILURES = frozenset(
    {
        "WRONG_TOOL",
        "MISSING_TOOL_CALL",
        "UNNECESSARY_TOOL_CALL",
        "WRONG_TOOL_ARGUMENT",
        "PREMATURE_PARALLEL_CALL",
        "REPLANNING_MISSED",
        "WRONG_SECOND_TOOL",
        "TOOL_RESULT_IGNORED",
        "FINAL_ANSWER_CONTRADICTS_TOOL",
        "UNAUTHORIZED_TOOL_CALL",
        "TRACE_ORDER_ERROR",
        "MODEL_OUTPUT_INVALID",
    }
)


def normalize_text(value: str) -> str:
    normalized = unicodedata.normalize("NFKC", value).casefold()
    return re.sub(r"[\s，。！？、；：,.!?;:'\"“”‘’（）()\-_]+", "", normalized)


def _trace_token(event: dict[str, Any]) -> str:
    if event["eventType"] == "assistant_final":
        return "assistant_final"
    return f"{event['eventType']}:{event['toolName']}"


def validate_required_trace_order(trace: list[dict[str, Any]], expected: list[str]) -> bool:
    """Require the specified events in order, while allowing unrelated safe diagnostics."""

    actual = [_trace_token(event) for event in trace]
    position = 0
    for token in expected:
        try:
            position = actual.index(token, position) + 1
        except ValueError:
            return False
    return True


def validate_sequential_replanning(
    trace: list[dict[str, Any]], first_tool: str, result_class: str, next_tool: str
) -> bool:
    """Validate call A < result A < later call B, with B in a later model step."""

    first_call_index = next(
        (
            index
            for index, event in enumerate(trace)
            if event["eventType"] == "assistant_tool_call" and event["toolName"] == first_tool
        ),
        None,
    )
    if first_call_index is None:
        return False
    if has_premature_call(trace, first_tool, [next_tool]):
        return False
    first_step = trace[first_call_index]["step"]
    result_index = next(
        (
            index
            for index, event in enumerate(trace[first_call_index + 1 :], first_call_index + 1)
            if event["eventType"] == "tool_result"
            and event["toolName"] == first_tool
            and event["resultClass"] == result_class
        ),
        None,
    )
    if result_index is None:
        return False
    next_call_index = next(
        (
            index
            for index, event in enumerate(trace[result_index + 1 :], result_index + 1)
            if event["eventType"] == "assistant_tool_call" and event["toolName"] == next_tool
        ),
        None,
    )
    if next_call_index is None:
        return False
    next_step = trace[next_call_index]["step"]
    if trace[result_index]["step"] != first_step:
        return False
    next_result_index = next(
        (
            index
            for index, event in enumerate(trace[next_call_index + 1 :], next_call_index + 1)
            if event["eventType"] == "tool_result" and event["toolName"] == next_tool
        ),
        None,
    )
    return (
        first_call_index < result_index < next_call_index
        and next_result_index is not None
        and next_call_index < next_result_index
        and trace[next_result_index]["step"] == next_step
        and next_step > first_step
    )


def has_premature_call(
    trace: list[dict[str, Any]], first_tool: str, forbidden_next_tools: list[str]
) -> bool:
    first_call = next(
        (
            (index, event)
            for index, event in enumerate(trace)
            if event["eventType"] == "assistant_tool_call" and event["toolName"] == first_tool
        ),
        None,
    )
    if first_call is None:
        return False
    first_index, first_event = first_call
    result_index = next(
        (
            index
            for index, event in enumerate(trace[first_index + 1 :], first_index + 1)
            if event["eventType"] == "tool_result" and event["toolName"] == first_tool
        ),
        len(trace),
    )
    return any(
        event["eventType"] == "assistant_tool_call"
        and event["toolName"] in forbidden_next_tools
        and (index < result_index or event["step"] <= first_event["step"])
        for index, event in enumerate(trace)
    )


def _argument_matches(actual: Any, expected: Any) -> bool:
    if isinstance(expected, str):
        return isinstance(actual, str) and normalize_text(actual) == normalize_text(expected)
    if type(expected) in {int, bool} or expected is None:
        return actual == expected
    if isinstance(expected, dict):
        return (
            isinstance(actual, dict)
            and set(actual) == set(expected)
            and all(_argument_matches(actual[key], value) for key, value in expected.items())
        )
    if isinstance(expected, list):
        return (
            isinstance(actual, list)
            and len(actual) == len(expected)
            and all(
                _argument_matches(left, right) for left, right in zip(actual, expected, strict=True)
            )
        )
    return actual == expected


def validate_arguments(trace: list[dict[str, Any]], expectations: list[dict[str, Any]]) -> bool:
    for expectation in expectations:
        calls = [
            event
            for event in trace
            if event["eventType"] == "assistant_tool_call"
            and event["toolName"] == expectation["toolName"]
        ]
        occurrence = expectation["occurrence"]
        if len(calls) < occurrence:
            return False
        call = calls[occurrence - 1]
        if call.get("argumentsInvalid"):
            return False
        if expectation["toolName"] == "get_dish_detail":
            # Identifiers are opaque and case-sensitive; punctuation removal would change identity.
            actual = call["arguments"]
            if (
                set(actual) != {"dish_id"}
                or actual["dish_id"].strip() != expectation["arguments"]["dish_id"]
            ):
                return False
        elif not _argument_matches(call["arguments"], expectation["arguments"]):
            return False
    return True


def validate_lifecycle(trace: list[dict[str, Any]], *, aborted: bool = False) -> bool:
    """Every result must match a pending call; a decision cannot bypass pending Tool results."""

    pending: Counter[tuple[int, str]] = Counter()
    last_step = 0
    result_started = False
    for index, event in enumerate(trace):
        step = event["step"]
        if step < last_step:
            return False
        if step > last_step:
            if any(pending.values()):
                return False
            result_started = False
        if event["eventType"] == "assistant_tool_call":
            if result_started:
                return False
            pending[(step, event["toolName"])] += 1
        elif event["eventType"] == "tool_result":
            key = (step, event["toolName"])
            if pending[key] <= 0:
                return False
            pending[key] -= 1
            result_started = True
        else:
            if index != len(trace) - 1 or any(pending.values()) or step <= last_step:
                return False
        last_step = step
    if not trace or any(pending.values()):
        return False
    return trace[-1]["eventType"] == "assistant_final" or (
        aborted and trace[-1].get("resultClass") == "safe_error"
    )


def _final_event(trace: list[dict[str, Any]]) -> dict[str, Any] | None:
    finals = [event for event in trace if event["eventType"] == "assistant_final"]
    return finals[-1] if len(finals) == 1 else None


def _source_results(trace: list[dict[str, Any]], tools: list[str]) -> list[dict[str, Any]]:
    return [
        event
        for event in trace
        if event["eventType"] == "tool_result" and event["toolName"] in tools
    ]


def _observed_names(results: list[dict[str, Any]]) -> list[str]:
    names: list[str] = []
    for event in results:
        summary = event["summary"]
        items = summary.get("items", [])
        if isinstance(items, list):
            names.extend(
                item["name"]
                for item in items
                if isinstance(item, dict) and isinstance(item.get("name"), str)
            )
        item = summary.get("item")
        if isinstance(item, dict) and isinstance(item.get("name"), str):
            names.append(item["name"])
    return names


def _tool_results_not_contradicted(trace: list[dict[str, Any]], answer: str) -> bool:
    all_names = _observed_names([event for event in trace if event["eventType"] == "tool_result"])
    for index, event in enumerate(trace):
        if event["eventType"] != "tool_result":
            continue
        summary = event["summary"]
        values: list[dict[str, Any]] = []
        if isinstance(summary.get("items"), list):
            values.extend(item for item in summary["items"] if isinstance(item, dict))
        if isinstance(summary.get("item"), dict):
            values.append(summary["item"])
        for item in values:
            name = item.get("name")
            if not isinstance(name, str) or name not in answer:
                continue
            # Compare facts in the clause belonging to this item, not the whole mixed-item answer.
            active_name = None
            for clause in re.split(r"[，,。；;\n、]", answer):
                mentioned = {candidate for candidate in all_names if candidate in clause}
                if mentioned:
                    active_name = next(iter(mentioned)) if len(mentioned) == 1 else None
                if active_name != name:
                    continue
                status = item.get("status")
                if status == "on_sale" and re.search(r"(?<!未)(?<!不)(?<!没有)已售罄", clause):
                    return False
                if status == "sold_out" and re.search(r"(?<!不)(?<!未)(?<!非)在售", clause):
                    return False
                # Explicit single-item price claims only; total-price arithmetic is a separate task.
                if not any(word in clause for word in ("合计", "总共", "总价", "两杯", "两份")):
                    prices = re.findall(r"(?:单价|价格|售价)?\s*(\d+(?:\.\d+)?)\s*元", clause)
                    if any(float(price) != item.get("price") for price in prices):
                        return False
        if event["toolName"] == "search_menu" and event["resultClass"] == "empty":
            prior_calls = [
                candidate
                for candidate in trace[:index]
                if candidate["eventType"] == "assistant_tool_call"
                and candidate["toolName"] == "search_menu"
            ]
            query = prior_calls[-1]["arguments"].get("query") if prior_calls else None
            if isinstance(query, str) and any(
                phrase in normalize_text(answer)
                for phrase in (f"有{normalize_text(query)}", f"{normalize_text(query)}在售")
            ):
                return False
    return True


def _result_usage_consistent(
    trace: list[dict[str, Any]], mode: str, source_tools: list[str]
) -> bool | None:
    if mode == "none":
        return None
    final = _final_event(trace)
    if final is None:
        return False
    answer = final["answer"]
    if not _tool_results_not_contradicted(trace, answer):
        return False
    if mode == "refuse_write":
        return None
    results = _source_results(trace, source_tools)
    if not results:
        return False
    if mode == "safe_failure":
        return any(
            event["resultClass"] in {"safe_error", "missing", "invalid"} for event in results
        )
    if mode == "report_empty_cautiously":
        return any(event["resultClass"] == "empty" for event in results) and any(
            term in answer for term in ("没查到", "未查到", "没有查到", "未找到", "没有找到")
        )
    names = _observed_names(results)
    if mode == "recommend_observed_item_after_empty":
        has_empty = any(event["resultClass"] == "empty" for event in results)
        return has_empty and bool(names) and any(name in answer for name in names)
    if mode in {"report_observed_item", "report_observed_detail"}:
        return bool(names) and any(name in answer for name in names)
    return False


def _final_meaning_consistent(trace: list[dict[str, Any]], expectation: dict[str, Any]) -> bool:
    final = _final_event(trace)
    if final is None or final["completed"] is not True:
        return False
    answer = final["answer"]
    required = all(any(term in answer for term in group) for group in expectation["requiredAny"])
    forbidden = any(term in answer for term in expectation["forbidden"])
    return required and not forbidden


def _expected_call_names(expected: dict[str, Any]) -> list[str]:
    names: list[str] = []
    for token in expected["requiredTraceOrder"]:
        event, separator, tool_name = token.partition(":")
        if event == "assistant_tool_call" and separator:
            names.append(tool_name)
    return names


def evaluate_case(case: dict[str, Any], observation: dict[str, Any]) -> dict[str, Any]:
    """Score one trace with explicit N/A values and a stable failure taxonomy."""

    metrics: dict[str, bool | None] = {
        "tool_selection_accuracy": None,
        "tool_argument_accuracy": None,
        "required_tool_call_accuracy": None,
        "unnecessary_tool_call_rate": None,
        "sequential_replanning_accuracy": None,
        "premature_parallel_call_rate": None,
        "tool_result_utilization_accuracy": None,
        "final_answer_consistency": None,
        "unauthorized_tool_call_rate": None,
        "trace_contract_accuracy": False,
    }
    failures: list[str] = []
    # Detect attempts even when another malformed field would otherwise short-circuit scoring.
    if isinstance(observation, dict) and isinstance(observation.get("trace"), list):
        attempts = [
            event
            for event in observation["trace"]
            if isinstance(event, dict) and event.get("eventType") == "assistant_tool_call"
        ]
        unauthorized = any(event.get("toolName") not in READ_ONLY_TOOLS for event in attempts)
        metrics["unauthorized_tool_call_rate"] = unauthorized
        if unauthorized:
            failures.append("UNAUTHORIZED_TOOL_CALL")
    try:
        validate_observation(observation)
    except ToolBenchmarkError:
        failures.extend(["MODEL_OUTPUT_INVALID", "TRACE_ORDER_ERROR"])
        return _result(case, metrics, failures)
    if observation["id"] != case["id"]:
        failures.append("MODEL_OUTPUT_INVALID")
        return _result(case, metrics, failures)

    trace = observation["trace"]
    expected = case["expected"]
    aborted = observation.get("termination") == "safe_tool_error"
    expected_safe_abort = aborted and expected["expectedResultUsage"]["mode"] == "safe_failure"
    order = expected["requiredTraceOrder"]
    if expected_safe_abort:
        # Production aborts on a FrameworkError; never invent an assistant answer for this case.
        order = [token for token in order if token != "assistant_final"]
    trace_ok = validate_lifecycle(trace, aborted=aborted) and validate_required_trace_order(
        trace, order
    )
    metrics["trace_contract_accuracy"] = trace_ok
    if not trace_ok:
        failures.append("TRACE_ORDER_ERROR")

    calls = [event for event in trace if event["eventType"] == "assistant_tool_call"]
    call_names = [event["toolName"] for event in calls]
    unauthorized = any(name not in READ_ONLY_TOOLS for name in call_names)
    metrics["unauthorized_tool_call_rate"] = unauthorized
    if unauthorized:
        failures.append("UNAUTHORIZED_TOOL_CALL")

    requires_tool = expected["requiresTool"]
    expected_calls = _expected_call_names(expected)
    required_call_ok = (
        not (Counter(expected_calls) - Counter(call_names)) if requires_tool else not calls
    )
    metrics["required_tool_call_accuracy"] = required_call_ok
    if requires_tool and not required_call_ok:
        failures.append("MISSING_TOOL_CALL")

    if expected["initialTool"] is not None:
        initial_ok = bool(calls) and all(
            call["toolName"] in expected["allowedInitialTools"]
            and call["toolName"] not in expected["forbiddenInitialTools"]
            for call in calls
            if call["step"] == calls[0]["step"]
        )
        metrics["tool_selection_accuracy"] = initial_ok
        if not initial_ok and calls:
            failures.append("WRONG_TOOL")

    if expected["expectedArguments"]:
        arguments_ok = validate_arguments(trace, expected["expectedArguments"])
        metrics["tool_argument_accuracy"] = arguments_ok
        if not arguments_ok:
            failures.append("WRONG_TOOL_ARGUMENT")

    unnecessary = any(
        name in READ_ONLY_TOOLS and call_names.count(name) > expected_calls.count(name)
        for name in set(call_names)
    ) or (not requires_tool and bool(calls))
    metrics["unnecessary_tool_call_rate"] = unnecessary
    if unnecessary:
        failures.append("UNNECESSARY_TOOL_CALL")

    condition = expected["replanningCondition"]
    if condition is not None:
        sequential = validate_sequential_replanning(
            trace,
            condition["afterTool"],
            condition["resultClass"],
            condition["nextTool"],
        )
        metrics["sequential_replanning_accuracy"] = sequential
        if not sequential:
            later_calls = call_names[1:]
            failures.append(
                "WRONG_SECOND_TOOL"
                if later_calls and condition["nextTool"] not in later_calls
                else "REPLANNING_MISSED"
            )

    if expected["forbiddenPrematureCalls"]:
        premature = has_premature_call(
            trace, expected["initialTool"], expected["forbiddenPrematureCalls"]
        )
        metrics["premature_parallel_call_rate"] = premature
        if premature:
            failures.append("PREMATURE_PARALLEL_CALL")

    usage = expected["expectedResultUsage"]
    utilization = _result_usage_consistent(trace, usage["mode"], usage["sourceTools"])
    if expected_safe_abort:
        # The Tool exception terminates the production graph before another model decision.
        utilization = None
    metrics["tool_result_utilization_accuracy"] = utilization
    if utilization is False:
        failures.append("TOOL_RESULT_IGNORED")

    final = _final_event(trace)
    final_ok = _final_meaning_consistent(
        trace, expected["allowedFinalMeaning"]
    ) and _tool_results_not_contradicted(trace, final["answer"] if final else "")
    metrics["final_answer_consistency"] = (
        None if expected_safe_abort and final is None else final_ok
    )
    if not final_ok and not expected_safe_abort:
        failures.append("FINAL_ANSWER_CONTRADICTS_TOOL")
    if observation.get("modelOutputInvalid") is True:
        failures.append("MODEL_OUTPUT_INVALID")
    return _result(case, metrics, failures)


def _result(
    case: dict[str, Any], metrics: dict[str, bool | None], failures: list[str]
) -> dict[str, Any]:
    unique = list(dict.fromkeys(failures))
    if any(item not in FAILURES for item in unique):
        raise AssertionError("unknown failure taxonomy")
    return {
        "id": case["id"],
        "category": case["category"],
        "split": case["split"],
        "metrics": metrics,
        "failures": unique,
        "primaryFailure": unique[0] if unique else None,
    }

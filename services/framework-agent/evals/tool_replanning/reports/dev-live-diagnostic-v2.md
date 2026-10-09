# Tool Selection + Sequential Replanning Benchmark v1 Report

- Mode: `live-model-local-fixture`
- Split: `dev`
- Generated at: `2026-10-09T02:10:13.967469+00:00`
- Cases in scope: 6
- Cases evaluated: 6
- Allowed production Tools: search_menu, list_available_drinks, get_dish_detail
- Side-effect Tools: forbidden

> N/A means this run did not observe the data required for the metric. It is not a pass.
> Validation-only mode checks frozen artifacts and performs no model or network call.

## Category counts

| Category | Cases |
| --- | ---: |
| single_tool_selection | 4 |
| tool_argument_accuracy | 2 |

## Metrics

| Metric | Result |
| --- | ---: |
| Tool Selection Accuracy | 100.00% (6/6) |
| Tool Argument Accuracy | 100.00% (6/6) |
| Required Tool Call Accuracy | 100.00% (6/6) |
| Sequential Replanning Accuracy | N/A |
| Tool Result Utilization Accuracy | 33.33% (2/6) |
| Final Answer Consistency | 33.33% (2/6) |
| Trace Contract Accuracy | 100.00% (6/6) |
| Unnecessary Tool Call Rate | 16.67% (1/6) |
| Premature Parallel Call Rate | N/A |
| Unauthorized Tool Call Rate | 0.00% (0/6) |

## Failures

- Failed case IDs: tool_single_tool_selection_002, tool_single_tool_selection_007, tool_single_tool_selection_009, tool_tool_argument_accuracy_002, tool_tool_argument_accuracy_005
- Failure distribution: FINAL_ANSWER_CONTRADICTS_TOOL=4, TOOL_RESULT_IGNORED=4, UNNECESSARY_TOOL_CALL=1

No prompt, raw provider response, reasoning, credential, or full Tool payload is included.

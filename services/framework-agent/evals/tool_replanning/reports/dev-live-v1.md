# Tool Selection + Sequential Replanning Benchmark v1 Report

- Mode: `live-model-local-fixture`
- Split: `dev`
- Generated at: `2026-10-08T08:34:37.784337+00:00`
- Cases in scope: 30
- Cases evaluated: 30
- Allowed production Tools: search_menu, list_available_drinks, get_dish_detail
- Side-effect Tools: forbidden

> N/A means this run did not observe the data required for the metric. It is not a pass.
> Validation-only mode checks frozen artifacts and performs no model or network call.

## Category counts

| Category | Cases |
| --- | ---: |
| no_premature_parallelism | 3 |
| no_tool_needed | 4 |
| sequential_replanning | 6 |
| single_tool_selection | 9 |
| tool_argument_accuracy | 6 |
| tool_empty_or_failure | 2 |

## Metrics

| Metric | Result |
| --- | ---: |
| Tool Selection Accuracy | 100.00% (26/26) |
| Tool Argument Accuracy | 100.00% (26/26) |
| Required Tool Call Accuracy | 100.00% (30/30) |
| Sequential Replanning Accuracy | 100.00% (8/8) |
| Tool Result Utilization Accuracy | 80.00% (20/25) |
| Final Answer Consistency | 82.76% (24/29) |
| Trace Contract Accuracy | 100.00% (30/30) |
| Unnecessary Tool Call Rate | 3.33% (1/30) |
| Premature Parallel Call Rate | 0.00% (0/11) |
| Unauthorized Tool Call Rate | 0.00% (0/30) |

## Failures

- Failed case IDs: tool_single_tool_selection_002, tool_single_tool_selection_006, tool_single_tool_selection_007, tool_single_tool_selection_009, tool_tool_argument_accuracy_002, tool_tool_argument_accuracy_005
- Failure distribution: FINAL_ANSWER_CONTRADICTS_TOOL=5, TOOL_RESULT_IGNORED=5, UNNECESSARY_TOOL_CALL=1

No prompt, raw provider response, reasoning, credential, or full Tool payload is included.
